"""Request-local filing resolution, source evidence and Decimal arithmetic."""

import ast
import hashlib
import json
import operator
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Context, Decimal, DecimalException, localcontext

from ..accounting.automated_extraction import parse_vietnamese_number
from ..evidence.graph import graph_id
from ..evidence.json_catalog import (
    json_cell_observation,
    json_document_composition,
    json_evidence_bound,
    json_fact_bound,
    json_filing_issuer,
    json_table_cells,
    load_json_corpus_document,
    resolve_pointer,
)
from ..evidence.search import _cells, normalize_search, rank_search_candidates
from .financial_qa import QADocument
from .graph_retrieval import GetSnapshotGraphContextRequest, GraphRetrievalTools
from .hybrid_rag import SearchHybridEvidenceRequest

CELL = re.compile(r"(T[0-9]+)R([1-9][0-9]*)C([1-9][0-9]*)")
SOURCE_ID = re.compile(r"\b(?:T\d+(?:\s*R\d+(?:\s*C\d+)?)?|[DF]\d+)\b", re.I)
NUMBER = re.compile(r"(?<![\w.,/])[-−]?\d+(?:[.,]\d+)*(?![\w/])")
UNIT = re.compile(r"^\s*(%|VND\b|VNĐ\b|đồng\b|lần\b|ngày\b|điểm\b|cổ phiếu\b|cổ phần\b)", re.I)
ROW = re.compile(r"(T[0-9]+)R([1-9][0-9]*)(?:C([1-9][0-9]*))?")
MATH = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
STANDARD_CONSTANTS = {0, 1, 2, 4, 12, 100, 360, 365, 366, 1000, 1_000_000, 1_000_000_000}


def location(record):
    ref = record.sources[0].reference
    return ref.anchor.page.page, ref.source_pointer


def citation_key(citation):
    return tuple(citation[key] for key in ("document_id", "snapshot_id", "page", "pointer"))


def dump(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def source_ids(text):
    return list(dict.fromkeys(re.sub(r"\s+", "", item.upper()) for item in SOURCE_ID.findall(text)))


def number(token):
    token = token.replace("−", "-")
    if "." in token and "," in token:
        group = "." if token.rfind(",") > token.rfind(".") else ","
        token = token.replace(group, "")
    elif re.fullmatch(r"-?\d{1,3}(?:[.,]\d{3})+", token):
        token = token.replace(".", "").replace(",", "")
    return Decimal(token.replace(",", "."))


def quantities(text, result_unit="", entities=()):
    """Read financial amounts while keeping named entities and locator numbers separate."""
    text = text.replace("**", "").replace(r"\%", "%")
    for name in entities:
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", " ", text, flags=re.I)
    for match in NUMBER.finditer(text):
        before, after = text[: match.start()], text[match.end() :]
        suffix = UNIT.match(after.lstrip(")"))
        if not suffix and re.search(
            r"\b(?:năm|trang|mã(?:\s+số)?|dòng|cột)\s*[:#]?\s*$", before, re.I
        ):
            continue
        try:
            value = number(match[0])
        except DecimalException:
            continue
        if before.endswith("(") and after[
            (suffix.end() if suffix and not after.startswith(")") else 0) :
        ].startswith(")"):
            value = -abs(value)
        if suffix or abs(value) >= 1000:
            unit = suffix[1].casefold() if suffix else ""
            yield value, "vnd" if unit in {"đồng", "vnđ"} else unit
        elif result_unit and re.fullmatch(r"-?\d+[.,]\d{1,2}", match[0]):
            yield value, result_unit


class DocumentResolver:
    def __init__(self, metadata, refined, corpus):
        self.refined, self.corpus = refined, corpus
        self.metadata = json.loads(metadata.read_bytes())
        index = json.loads((corpus / "catalog-index.json").read_bytes())["documents"]
        self.index = {key: index[key] for key in self.metadata}
        self.names = {}
        for key, row in self.metadata.items():
            if key != f"{row['ticker']}_{row['fiscal_year']}":
                raise ValueError("metadata_filing_key_mismatch")
            self.names.setdefault(row["ticker"], set()).update(
                normalize_search(name)
                for name in [row["ticker"], row["company_name"], *row["aliases"]]
            )

    def shortlist(self, question, override=None):
        query = f" {normalize_search(question)} "
        mentions = {
            ticker: sorted(name for name in names if f" {name} " in query)
            for ticker, names in self.names.items()
        }
        mentions = {ticker: names for ticker, names in mentions.items() if names}
        years = {int(year) for year in re.findall(r"\b20[0-9]{2}\b", query)}
        scope_hints = {
            scope
            for phrase, scope in (
                ("hop nhat", "consolidated"),
                ("bao cao rieng", "separate"),
                ("tai chinh rieng", "separate"),
                ("bctc rieng", "separate"),
            )
            if f" {phrase} " in query
        }
        candidates = {
            key: row
            for key, row in self.metadata.items()
            if not mentions or row["ticker"] in mentions
        }
        # Keep alternative years for ambiguous issuer/comparative mentions. A
        # single issuer with a single exact year needs no model selection.
        single = []
        exact = [key for key, row in candidates.items() if row["fiscal_year"] in years]
        if override:
            if override in self.metadata:
                single = [override]
                candidates = {override: self.metadata[override]}
            else:
                candidates = {}
        elif len(mentions) == 1 and len(years) == 1 and len(exact) == 1:
            supplied = self.metadata[exact[0]]["statement_scope"]
            if supplied == "unknown" or not scope_hints or supplied in scope_hints:
                single = exact
        elif len(mentions) == 1 and not years and len(candidates) == 1:
            single = list(candidates)
        return dict(
            override=override,
            mentions=mentions,
            years=sorted(years),
            scope_hints=sorted(scope_hints),
            options=candidates,
            selected=single,
        )

    def from_plan(self, resolution, obligations):
        """Match an issuer named as the owner of a report in the Coordinator's plan."""
        possible = set()
        for goal in obligations:
            for text in [goal["goal"], *goal["needs"]]:
                text = normalize_search(text)
                for match in re.finditer(
                    r"\bbao cao(?: tai chinh)?((?: rieng| hop nhat| nam 20\d{2})*) cua ", text
                ):
                    owner = text[match.end() :] + " "
                    names = [
                        (len(name), ticker)
                        for ticker, aliases in self.names.items()
                        for name in aliases
                        if owner.startswith(name + " ")
                    ]
                    if not names:
                        continue
                    longest = max(length for length, _ in names)
                    issuers = {ticker for length, ticker in names if length == longest}
                    if len(issuers) != 1:
                        return []
                    years = set(map(int, re.findall(r"20\d{2}", match[1]))) or set(
                        resolution["years"]
                    )
                    possible.update(
                        key
                        for key, row in resolution["options"].items()
                        if row["ticker"] in issuers
                        and (not years or row["fiscal_year"] in years)
                        and (
                            not resolution["scope_hints"]
                            or row["statement_scope"] in {*resolution["scope_hints"], "unknown"}
                        )
                    )
        return sorted(possible) if len(possible) == 1 else []

    def load(self, alias):
        catalog = load_json_corpus_document(self.refined, self.corpus, alias)
        (descriptor,) = catalog.descriptors
        pins = dict(document_id=descriptor.document_id, snapshot_id=descriptor.snapshot_id)
        company = QADocument.from_json_corpus(catalog).company_id
        _, issuer = json_filing_issuer(catalog, descriptor, company)
        scope = catalog.get_reporting_scope(**pins)
        available = scope.reporting_scope
        scope_locator = None
        if available not in {"consolidated", "separate"}:
            scope_labels = {"rieng": "separate", "hop nhat": "consolidated"}
            reports = []
            for page, digest in sorted(descriptor.json_pages.items())[:5]:
                for i, block in enumerate(catalog.json_sources[digest]["blocks"]):
                    if block.get("uncertain"):
                        continue
                    for line in block.get("text", "").splitlines():
                        text = normalize_search(line)
                        checked = re.match(r"^\s*(?:☑|✓|\[[xXvV]\s*\])", line)
                        if not checked and line.lstrip().startswith(("[", "☐", "□")):
                            continue
                        match = re.match(
                            r"(?:x |v )?(?:bctc|bao cao tai chinh) (rieng|hop nhat)\b", text
                        )
                        if match:
                            locator = dict(
                                page=page, pointer=f"/blocks/{i}/text", page_sha256=digest
                            )
                            reports.append((bool(checked), scope_labels[match[1]], locator))
            preferred = [item for item in reports if item[0]] or reports
            if len({item[1] for item in preferred}) == 1:
                _, available, scope_locator = preferred[0]
        return Filing(
            alias,
            catalog.request_snapshot(),
            descriptor,
            company,
            issuer,
            scope,
            {
                **self.metadata[alias],
                **pins,
                "source_scope": available,
                "scope_locator": scope_locator,
            },
        )


@dataclass
class Filing:
    alias: str
    catalog: object
    descriptor: object
    company: str
    issuer: dict | None
    scope: object
    details: dict
    graph: object = None
    lexical: dict = field(default_factory=dict)
    composition: object = None

    @property
    def pins(self):
        return {key: self.details[key] for key in ("document_id", "snapshot_id")}


class EvidenceWorkspace:
    def __init__(self, resolver, hybrid):
        self.resolver = resolver
        self.hybrid = hybrid
        self.filings = {}
        self.active = []
        self.ids = {}
        self.entries = {}
        self.overlay = {}
        self.searches = {}
        self.traces = []
        self.cell_metadata = {}

    def select(self, aliases):
        for alias in aliases:
            if alias not in self.filings:
                self.filings[alias] = self.resolver.load(alias)
        self.active = list(dict.fromkeys(aliases))

    def filings_context(self):
        return {key: self.filings[key].details for key in self.active}

    def add(self, filing, record, origin):
        page, pointer = location(record)
        kind = getattr(record, "kind", "fact")
        key = (*filing.pins.values(), page, pointer, kind)
        if key in self.ids:
            return self.ids[key]
        prefix = {"table": "T", "text": "D", "fact": "F"}[kind]
        catalog, descriptor = filing.catalog, filing.descriptor
        if prefix == "F":
            if record.company_id != filing.company or not json_fact_bound(catalog, record):
                return None
            content = dict(
                label=record.context.raw_item_label,
                column=record.raw_header,
                period=record.context.period,
                value=record.value.raw_value,
                unit=record.value.unit,
                scale=str(record.context.scale),
            )
        else:
            if record.source_metadata.get("uncertain") or not json_evidence_bound(
                catalog, descriptor, record
            ):
                return None
            if prefix == "T":
                table = record.source_metadata["original_table"]
                blocks = catalog.json_sources[descriptor.json_pages[page]]["blocks"]
                block_index = int(pointer.split("/")[2])
                nearby = [
                    block["text"]
                    for block in blocks[max(0, block_index - 3) : block_index]
                    if block.get("text") and not block.get("uncertain")
                ]
                content = dict(
                    title=table.get("title"),
                    columns=table["columns"],
                    preceding_text=nearby,
                    rows={f"R{i}": row for i, row in enumerate(table["rows"], 1)},
                )
            else:
                content = dict(text=record.raw_text)
        source_id = self.ids[key] = f"{prefix}{len(self.ids) + 1}"
        self.entries[source_id] = dict(
            filing=filing.alias,
            record=record,
            origin=origin,
            view=dict(filing=filing.alias, page=page, pointer=pointer, **content),
        )
        return source_id

    def section_tables(self, section, query):
        """Retrieve tables by real headings/form codes before general retrieval (not a release gate)."""
        heading = normalize_search(section)
        # Canonical accounting form names, including OCR spacing in the form number.
        forms = {
            "b01": "bang can doi ke toan",
            "b02": "bao cao ket qua hoat dong kinh doanh",
            "b03": "bao cao luu chuyen tien te",
        }
        aliases = {heading}
        for code, name in forms.items():
            if heading.replace(" ", "").startswith(code) or name in heading:
                aliases.update((code, f"b {code[1:]}", name))
        results = []
        for alias in self.active:
            filing = self.filings[alias]
            candidates, records = {}, {}
            for record in filing.catalog.evidence:
                if record.kind != "table" or record.source_metadata.get("uncertain"):
                    continue
                page, pointer = location(record)
                table = record.source_metadata["original_table"]
                blocks = filing.catalog.json_sources[filing.descriptor.json_pages[page]]["blocks"]
                index = int(pointer.split("/")[2])
                text = normalize_search(
                    " ".join(
                        [
                            table.get("title") or "",
                            *[
                                block["text"]
                                for block in blocks[max(0, index - 3) : index]
                                if block.get("text") and not block.get("uncertain")
                            ],
                        ]
                    )
                )
                if not any(f" {name} " in f" {text} " for name in aliases if name):
                    continue
                k = (page, pointer)
                records[k] = record
                candidates[k] = " ".join(
                    [text, *[" ".join(map(str, row[:3])) for row in table["rows"]]]
                )
            for k in rank_search_candidates(candidates, [query], top_k=2):
                if source := self.add(filing, records[k], "section"):
                    results.append(source)
        return results[:3]

    def lookup(self, filing, query):
        if not filing.lexical:
            for record in filing.catalog.evidence:
                if record.kind in {"table", "text"} and not record.source_metadata.get("uncertain"):
                    table = record.source_metadata.get("original_table") or {}
                    labels = [
                        " ".join(x for x in row[:3] if isinstance(x, str))
                        for row in table.get("rows", [])
                    ]
                    body = " ".join(
                        filter(
                            None, [table.get("title"), getattr(record, "raw_text", None), *labels]
                        )
                    )
                    filing.lexical[record.evidence_identity()] = record, normalize_search(body)
        term = normalize_search(query)
        candidates = {key: body for key, (_, body) in filing.lexical.items()}
        exact = [key for key, body in candidates.items() if f" {term} " in f" {body} "]
        ranked = rank_search_candidates(candidates, [query], top_k=5)
        found = list(dict.fromkeys([*exact, *ranked]))[:5]
        return [
            source
            for key in found
            if (source := self.add(filing, filing.lexical[key][0], "lexical"))
        ], len(exact)

    def search(self, query, *, alias="", mode="search"):
        filings = [alias] if alias in self.active else self.active
        results = []
        for key in filings:
            filing = self.filings[key]
            cache = (key, normalize_search(query), mode)
            if cache in self.searches:
                results.append(self.searches[cache])
                continue
            scoped = query
            for name in sorted(
                [filing.details["company_name"], *filing.details["aliases"]], key=len, reverse=True
            ):
                scoped = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", " ", scoped, flags=re.I)
            scoped = re.sub(rf"\bnăm\s+{filing.details['fiscal_year']}\b", " ", scoped, flags=re.I)
            scoped = re.sub(
                r"\b(?:của|trong báo cáo tài chính(?: hợp nhất| riêng)?)\s*$",
                "",
                scoped.strip(" .?,"),
            )
            scoped = " ".join(scoped.split()) or query
            lexical, exact = self.lookup(filing, scoped)
            self.traces.append(
                dict(
                    tool="lexical",
                    query=query,
                    scoped_query=scoped,
                    filing=key,
                    evidence=lexical,
                    exact=exact,
                )
            )
            hybrid, facts = [], []
            if mode != "lexical":
                if filing.composition is None:
                    filing.composition = json_document_composition(filing.catalog)
                response = self.hybrid.search(
                    SearchHybridEvidenceRequest(**filing.pins, query=scoped, top_k=7),
                    filing.catalog,
                    filing.composition,
                )
                hybrid = [
                    source
                    for match in response.documents.matches
                    if (source := self.add(filing, match.evidence.record, "document"))
                ]
                facts = [
                    source
                    for match in response.facts
                    if (source := self.add(filing, match.record, "ef_eg"))
                ]
                self.traces.append(
                    dict(
                        tool="hybrid",
                        query=query,
                        filing=key,
                        evidence=hybrid,
                        facts=facts,
                        hits=response.hits,
                        timing_ms=response.timing_ms,
                    )
                )
            first, second = (lexical, hybrid) if exact else (hybrid, lexical)
            ranked = [*first[:1], *second[:1], *first[1:], *second[1:], *facts]
            self.searches[cache] = result = list(dict.fromkeys(ranked))
            results.append(result)
        return list(
            dict.fromkeys(
                source
                for i in range(max(map(len, results), default=0))
                for result in results
                if i < len(result)
                for source in [result[i]]
            )
        )

    def traverse(self, filing, source):
        record = self.entries[source]["record"]
        fact = source.startswith("F")
        identity = record.observation_identity() if fact else record.evidence_identity()
        kind = "source_fact" if fact else identity.kind
        seed = graph_id(kind, identity.model_dump())
        graph_key = (filing.alias, seed)
        if graph_key in self.searches:
            return self.searches[graph_key]
        if filing.graph is None:
            filing.graph = GraphRetrievalTools.from_catalog(filing.catalog, **filing.pins)
        result = filing.graph.get_graph_context(
            GetSnapshotGraphContextRequest(
                **filing.pins,
                node_id=seed,
                relations=["associated_with", "from_source"],
                depth=2,
                limit=8,
            )
        )
        records = {
            item.evidence_identity(): item
            for item in filing.catalog.evidence
            if item.kind in {"table", "text"}
        }
        records.update({item.observation_identity(): item for item in filing.catalog.facts})
        found = []
        for match in result.matches:
            related = records.get(getattr(match.node, "reference", None))
            if related is not None and (key := self.add(filing, related, "ef_eg_traversal")):
                found.append(key)
        self.traces.append(
            dict(
                tool="graph",
                filing=filing.alias,
                seed=seed,
                evidence=found,
                result=result.model_dump(mode="json"),
            )
        )
        self.searches[graph_key] = list(dict.fromkeys(found))
        return self.searches[graph_key]

    def open_page(self, source_id, visible, radius=0):
        citation = self.citation(source_id, visible)
        filing = self.filings[self.entries[self.base_id(source_id)]["filing"]]
        found = [
            key
            for record in filing.catalog.evidence
            if record.kind in {"table", "text"}
            and abs(location(record)[0] - citation["page"]) <= radius
            and (key := self.add(filing, record, "open_page"))
        ]
        self.traces.append(dict(tool="open_page", source=source_id, evidence=found))
        return found

    def render(self, key, query, limit, excluded=()):
        view = self.entries[key]["view"]
        header = f"{key} | {view['filing']} | trang {view['page']} | {view['pointer']}"
        if "rows" not in view:
            return f"{header} | {view.get('text') or dump(view)}", [key]
        # Preceding paragraphs are already rendered with the table. Attach their real
        # source ID when the exact paragraph is present among retrieved entries.
        linked = []
        preceding = []
        for paragraph in view["preceding_text"]:
            matching = [
                k
                for k, entry in self.entries.items()
                if k.startswith("D")
                and entry["view"]["filing"] == view["filing"]
                and entry["view"]["page"] == view["page"]
                and entry["view"].get("text") == paragraph
            ]
            if len(matching) == 1:
                linked.extend(matching)
                preceding.append(f"[{matching[0]}] {paragraph}")
            else:
                preceding.append(paragraph)
        header = "\n".join(
            [header, view["title"] or "", *preceding, " | ".join(map(str, view["columns"]))]
        )
        selected = [row for row in view["rows"] if key + row not in excluded]

        def cell_text(row, col, cell):
            raw = str(cell).strip().strip("()")
            token = NUMBER.match(raw)
            if token and (token.end() == len(raw) or UNIT.fullmatch(raw[token.end() :])):
                return f"[{key}{row}C{col}] {cell}"
            return str(cell)

        rendered = {
            row: f"[{key}{row}] "
            + " | ".join(cell_text(row, col, cell) for col, cell in enumerate(view["rows"][row], 1))
            for row in selected
        }
        if len(header) + sum(len(r) + 1 for r in rendered.values()) <= limit:
            return "\n".join([header, *rendered.values()]), [key, *linked]
        ranked = rank_search_candidates(rendered, [query], top_k=14)
        kept, budget = set(), limit - len(header) - 28
        for row in ranked:
            index = selected.index(row)
            for neighbor in (row, *selected[max(0, index - 1) : index]):
                if neighbor not in kept and len(rendered[neighbor]) + 1 <= budget:
                    kept.add(neighbor)
                    budget -= len(rendered[neighbor]) + 1
        shown = [row for row in selected if row in kept]
        return "\n".join([header, "(Trích hàng liên quan)", *(rendered[r] for r in shown)]), [
            key + row for row in shown
        ] + linked

    def was_shown(self, key, visible):
        return any(item in visible for item in (key, self.base_id(key), key.rsplit("C", 1)[0]))

    def group_locators(self, references):
        """Join only adjacent explicit address fragments, never independent IDs/addresses."""
        refs = list(references)
        page = r"(?:trang|p\.?)\s*\d+"
        pointer = r"/blocks/\d+/(?:table|text)(?:/rows/\d+(?:/\d+)?)?"
        alias = "(?:" + "|".join(re.escape(a) for a in self.active) + ")"
        separator = r"\s*(?:[|,]\s*)?"
        full = alias + separator + page + separator + pointer
        result = []
        i = 0
        while i < len(refs):
            for count in (3, 2):
                if i + count <= len(refs):
                    parts = refs[i : i + count]
                    joined = " ".join(p.strip() for p in parts)
                    if all(p.strip() for p in parts) and re.fullmatch(full, joined, re.I):
                        result.append(joined)
                        i += count
                        break
            else:
                result.append(refs[i])
                i += 1
        return result

    def resolve(self, reference, visible):
        """Resolve explicit IDs or one address with a page and a matching label."""
        page = re.search(r"\b(?:trang|p\.?)\s*(\d+)\b", reference, re.I)
        filing_hints = [alias for alias in self.active if alias.casefold() in reference.casefold()]
        locator = re.search(r"/blocks/\d+/(?:table|text)(?:/rows/\d+(?:/\d+)?)?", reference)
        if page and locator:
            pointer = locator[0]
            matches = []
            for key, entry in self.entries.items():
                view = entry["view"]
                if view["page"] != int(page[1]) or (
                    filing_hints and view["filing"] not in filing_hints
                ):
                    continue
                if view["pointer"] == pointer:
                    refs = (
                        [key]
                        if key in visible
                        else [key + r for r in view.get("rows", {}) if key + r in visible]
                    )
                elif "rows" in view and pointer.startswith(view["pointer"] + "/rows/"):
                    row, _, col = pointer.removeprefix(view["pointer"] + "/rows/").partition("/")
                    ref = f"{key}R{int(row) + 1}" + (f"C{int(col) + 1}" if col else "")
                    refs = [ref] if self.was_shown(ref, visible) else []
                else:
                    continue
                if refs:
                    matches.append(refs)
            # A full address takes precedence over an inconsistent shorthand ID.
            return (
                [self.citation(ref, self.entries) for ref in matches[0]]
                if len(matches) == 1
                else []
            )
        if ids := source_ids(reference):
            return [
                self.citation(key, self.entries)
                for key in ids
                if self.was_shown(key, visible)
                and (not page or self.entries[self.base_id(key)]["view"]["page"] == int(page[1]))
                and (
                    not filing_hints
                    or self.entries[self.base_id(key)]["view"]["filing"] in filing_hints
                )
            ]
        if not page:
            return []
        text = " " + normalize_search(reference) + " "
        matches, page_matches = [], []
        for key, entry in self.entries.items():
            view = entry["view"]
            if view["page"] != int(page[1]) or (
                filing_hints and view["filing"] not in filing_hints
            ):
                continue
            if key in visible:
                page_matches.append(key)
            rows = [
                key + row
                for row, values in view.get("rows", {}).items()
                if self.was_shown(key + row, visible)
                and values
                and len(label := normalize_search(str(values[0]))) >= 5
                and f" {label} " in text
            ]
            if rows:
                matches.extend(rows)
            elif (
                key in visible
                and len(
                    label := normalize_search(
                        view.get("title") or view.get("label") or view.get("text", "")[:80]
                    )
                )
                >= 5
                and f" {label} " in text
            ):
                matches.append(key)
        if not matches and len(page_matches) == 1:
            matches = page_matches
        cites = {citation_key(c): c for key in matches if (c := self.citation(key, self.entries))}
        return list(cites.values()) if len(cites) == 1 else []

    def bind_literal(self, token, explanation, visible):
        value = number(token)
        refs = []
        # Keep a literal with its own row and period when two operands share a line.
        for clause in re.split(r"(?<=[.!?;])\s+|\n+", explanation):
            for match in NUMBER.finditer(clause):
                try:
                    same_value = abs(number(match[0])) == value
                except DecimalException:
                    continue
                if not same_value:
                    continue
                suffix = UNIT.match(clause[match.end() :])
                unit = suffix[1].casefold() if suffix else ""
                dates = {
                    normalize_search(date)
                    for date in re.findall(r"\b\d{1,2}/\d{1,2}/20\d{2}\b", clause)
                }
                years = set(re.findall(r"\bnăm\s+(20\d{2})\b", clause, re.I))
                refs.append((set(source_ids(clause)), normalize_search(clause), dates, years, unit))
        matches = {}
        for key, entry in self.entries.items():
            view = entry["view"]
            for row, values in view.get("rows", {}).items():
                row_id = key + row
                if not self.was_shown(row_id, visible) or not values:
                    continue
                label = normalize_search(re.sub(r"^\s*[IVXLCDM\d]+[.)]\s*", "", str(values[0])))
                for column, cell in enumerate(values, 1):
                    raw = str(cell).strip().strip("()")
                    if not NUMBER.fullmatch(raw):
                        continue
                    try:
                        if abs(number(raw)) != value:
                            continue
                    except DecimalException:
                        continue
                    source = f"{row_id}C{column}"
                    header = (
                        normalize_search(str(view["columns"][column - 1]))
                        if column <= len(view["columns"])
                        else ""
                    )
                    candidates = [
                        (dates, years, unit)
                        for ids, text, dates, years, unit in refs
                        if (
                            source in ids
                            or row_id in ids
                            or (
                                len(label) >= 5
                                and f" {label} " in f" {text} "
                                and len(header) >= 4
                                and f" {header} " in f" {text} "
                            )
                        )
                    ]
                    if not candidates:
                        continue
                    try:
                        fact = self.operand(source, self.entries)
                    except ValueError:
                        continue
                    if not any(
                        (
                            not unit
                            or fact["unit"].casefold()
                            == ("vnd" if unit in {"đồng", "vnđ"} else unit)
                        )
                        and (
                            not dates
                            or any(
                                f" {date} " in f" {header} "
                                or fact["period"]
                                == "-".join(part.zfill(2) for part in reversed(date.split()))
                                for date in dates
                            )
                        )
                        and (
                            dates
                            or not years
                            or any(
                                str(fact["period"]).startswith(year) or f" {year} " in f" {header} "
                                for year in years
                            )
                        )
                        for dates, years, unit in candidates
                    ):
                        continue
                    matches[citation_key(fact["citation"])] = fact
        if len(matches) != 1:
            raise ValueError(f"Chưa xác định duy nhất nguồn của toán hạng {token}.")
        fact = next(iter(matches.values()))
        return fact["id"] if Decimal(fact["value"]) >= 0 else f"abs({fact['id']})"

    @staticmethod
    def base_id(source_id):
        match = ROW.fullmatch(source_id)
        return match[1] if match else source_id

    def citation(self, source_id, visible):
        match = ROW.fullmatch(source_id)
        base = self.base_id(source_id)
        if base not in visible or base not in self.entries:
            raise ValueError("evidence_not_shown")
        entry = self.entries[base]
        filing = self.filings[entry["filing"]]
        if filing.alias not in self.active:
            raise ValueError("evidence_filing_not_selected")
        page, pointer = location(entry["record"])
        digest = filing.descriptor.json_pages[page]
        raw = filing.catalog.json_source_bytes[digest]
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("source_hash_mismatch")
        if match:
            pointer += f"/rows/{int(match[2]) - 1}"
            if match[3] is not None:
                pointer += f"/{int(match[3]) - 1}"
        try:
            value = resolve_pointer(filing.catalog.json_sources[digest], pointer)
        except (ValueError, KeyError, IndexError, TypeError):
            raise ValueError("invalid_source_coordinate") from None
        return dict(
            id=source_id,
            filing=filing.alias,
            origin=entry["origin"],
            page=page,
            pointer=pointer,
            page_sha256=digest,
            source_value=value,
            **filing.pins,
        )

    def table_cells(self, table_id):
        if table_id not in self.cell_metadata:
            entry = self.entries[table_id]
            filing = self.filings[entry["filing"]]
            record = entry["record"]
            self.cell_metadata[table_id] = {
                item["source_pointer"]: item
                for item in json_table_cells(
                    filing.catalog, filing.descriptor, record, _cells(record), filing.scope
                )
            }
        return self.cell_metadata[table_id]

    def operand_choices(self, visible):
        """Only numeric observations in the actually rendered source rows."""
        choices = {}
        for key, entry in self.entries.items():
            view = entry["view"]
            if key.startswith("F") and key in visible:
                try:
                    op = self.operand(key, self.entries)
                except ValueError:
                    continue
                choices[key] = dict(
                    label=op["label"],
                    period=op["period"],
                    column=op["column"],
                    raw=op["raw"],
                    value=op["value"],
                    scale=op["scale"],
                    unit=op["unit"],
                    filing=view["filing"],
                    page=view["page"],
                    pointer=view["pointer"],
                )
            elif "rows" in view and any(self.was_shown(key + row, visible) for row in view["rows"]):
                for pointer, cell in self.table_cells(key).items():
                    row, col = map(int, pointer.rsplit("/", 2)[-2:])
                    ref = f"{key}R{row + 1}C{col + 1}"
                    if not self.was_shown(ref, visible):
                        continue
                    value = parse_vietnamese_number(cell["raw_value"])
                    if (
                        value is None
                        or not value.is_finite()
                        or not all(cell.get(k) for k in ("period", "period_type", "unit", "scale"))
                    ):
                        continue
                    choices[ref] = dict(
                        label=cell["label"],
                        group=cell["group"],
                        period=cell["period"],
                        column=cell["header"],
                        raw=cell["raw_value"],
                        value=str(value),
                        scale=cell["scale"],
                        unit=cell["unit"],
                        filing=view["filing"],
                        page=view["page"],
                        pointer=pointer,
                        title=view.get("title"),
                    )
        return choices

    def direct_operand_choices(self, visible):
        """Pin the numeric cells actually shown, without requiring canonical period/label metadata.

        Scale 1 for an unresolved unit is raw-table arithmetic, NOT a VND assumption.
        The verifier receives the raw table, head/column and unresolved metadata explicitly.
        """
        choices = {}
        facts = {}
        for alias in self.active:
            filing = self.filings[alias]
            facts[alias] = {
                location(f): f
                for f in filing.catalog.facts
                if f.company_id == filing.company and f.sources and f.sources[0].reference
            }
        for key, entry in self.entries.items():
            view = entry["view"]
            if key.startswith("F") and key in visible:
                try:
                    op = self.operand(key, self.entries)
                except ValueError:
                    continue
                op.update(
                    filing=view["filing"],
                    page=view["page"],
                    pointer=view["pointer"],
                    title="",
                    row=[op["label"], op["raw"]],
                    columns=[op["column"]],
                    group="",
                    scale_basis="pinned_fact",
                )
                # If the fact is a table cell, expose the actual header and row to the verifier.
                pointer = view["pointer"]
                if "/rows/" in pointer:
                    base, rest = pointer.split("/rows/", 1)
                    filing = self.filings[view["filing"]]
                    table = resolve_pointer(
                        filing.catalog.json_sources[op["citation"]["page_sha256"]], base
                    )
                    row, _, col = rest.partition("/")
                    if col:
                        op.update(
                            title=table.get("title"),
                            row=table["rows"][int(row)],
                            columns=table["columns"],
                            column=table["columns"][int(col)],
                        )
                choices[key] = op
                continue
            if "rows" not in view or not any(
                self.was_shown(key + row, visible) for row in view["rows"]
            ):
                continue
            projected = self.table_cells(key)
            columns = view["columns"]
            headers = [normalize_search(str(c)) for c in columns]
            label_col = next(
                (
                    i
                    for i, c in enumerate(headers)
                    if c
                    in {"tai san", "nguon von", "chi tieu", "noi dung", "khoan muc", "danh muc"}
                ),
                1 if headers and headers[0] in {"stt", "so tt", "ma so", "ms"} else 0,
            )
            filing = self.filings[view["filing"]]
            for row_id, row in view["rows"].items():
                if not self.was_shown(key + row_id, visible) or len(row) != len(columns):
                    continue
                for i, raw in enumerate(row):
                    if (
                        i == label_col
                        or headers[i] in {"ma so", "ms", "stt", "so tt", "tm", "note", "notes"}
                        or "thuyet minh" in headers[i]
                    ):
                        continue
                    raw = str(raw).strip()
                    value = parse_vietnamese_number(raw)
                    if value is None:
                        token = raw[:-1].strip() if raw.endswith("%") else raw
                        signed = token.startswith("(") and token.endswith(")")
                        token = token[1:-1] if signed else token
                        if not NUMBER.fullmatch(token):
                            continue
                        try:
                            value = number(token)
                            if signed:
                                value = -abs(value)
                        except DecimalException:
                            continue
                    if not value.is_finite():
                        continue
                    ref = f"{key}{row_id}C{i + 1}"
                    ptr = f"{view['pointer']}/rows/{int(row_id[1:]) - 1}/{i}"
                    cell = projected.get(ptr, {})
                    fact = facts[view["filing"]].get((view["page"], ptr))
                    unit, scale, period = cell.get("unit"), cell.get("scale"), cell.get("period")
                    scale_basis = "table_metadata" if unit and scale else "raw_source_unresolved"
                    label = cell.get("label") or str(row[label_col])
                    if (
                        fact is not None
                        and (not unit or not scale or not period)
                        and json_fact_bound(filing.catalog, fact)
                    ):
                        if (
                            fact.value.normalized_value is not None
                            and Decimal(fact.value.normalized_value) == value
                        ):
                            unit = unit or fact.value.unit
                            scale = scale or str(fact.context.scale)
                            period = period or fact.context.period
                            scale_basis = "pinned_fact" if unit and scale else scale_basis
                    if raw.endswith("%") and not unit:
                        unit, scale, scale_basis = "%", "1", "explicit_cell_unit"
                    try:
                        citation = self.citation(ref, self.entries)
                    except ValueError:
                        continue
                    # The value must be the literal at this address, not a number matched elsewhere.
                    if str(citation["source_value"]).strip() != raw:
                        continue
                    choices[ref] = dict(
                        id=ref,
                        raw=raw,
                        value=str(value),
                        scale=str(scale or "1"),
                        unit=unit or "unresolved_raw_unit",
                        period=period,
                        label=label,
                        column=columns[i],
                        group=cell.get("group"),
                        filing=view["filing"],
                        page=view["page"],
                        pointer=ptr,
                        title=view.get("title"),
                        row=row,
                        columns=columns,
                        preceding_text=view.get("preceding_text", []),
                        scale_basis=scale_basis,
                        origin="shown_cell",
                        citation=citation,
                    )
        return choices

    def operand(self, source_id, visible):
        citation = self.citation(source_id, visible)
        entry = self.entries[self.base_id(source_id)]
        filing = self.filings[entry["filing"]]
        catalog = filing.catalog
        key = citation["page"], citation["pointer"]
        fact = next(
            (
                f
                for f in catalog.facts
                if f.company_id == filing.company
                and f.sources
                and f.sources[0].reference
                and location(f) == key
            ),
            None,
        )
        origin = "request_local" if source_id in self.overlay else "ef_eg"
        if fact is not None and not json_fact_bound(catalog, fact):
            fact = None
        if fact is None:
            origin = "request_local"
            if source_id not in self.overlay:
                match = CELL.fullmatch(source_id)
                if not match:
                    raise ValueError("numeric_operand_requires_cell_or_fact")
                table_id = match[1]
                self.table_cells(table_id)
                if key[1] not in self.cell_metadata[table_id]:
                    raise ValueError("cell_value_unit_or_period_unresolved")
                fact, issue = json_cell_observation(
                    filing.descriptor,
                    self.cell_metadata[table_id][key[1]],
                    filing.issuer,
                    filing.company,
                )
                if issue:
                    raise ValueError(issue)
                catalog.add_request_json_facts([fact])
                if not json_fact_bound(catalog, fact):
                    raise ValueError("request_local_fact_source_mismatch")
                self.overlay[source_id] = fact
            fact = self.overlay[source_id]
        return dict(
            id=source_id,
            raw=fact.value.raw_value,
            value=str(fact.value.normalized_value),
            scale=str(fact.context.scale),
            unit=fact.value.unit,
            period=fact.context.period,
            label=fact.context.raw_item_label,
            column=fact.raw_header,
            origin=origin,
            citation=citation,
        )


def calculate(expression, get_operand, question, precision):
    """Read a bounded arithmetic AST and return a replayable Decimal proof."""
    if len(expression) > 350 or not 0 <= precision <= 6:
        raise ValueError("calculation_bounds")
    tree = ast.parse(expression, mode="eval")
    if sum(1 for _ in ast.walk(tree)) > 70:
        raise ValueError("calculation_tree_limit")
    operands, constants = {}, {}
    question_numbers = {
        Decimal(n.replace(",", "."))
        for n in re.findall(r"(?<![\d.,])\d+(?:[.,]\d+)?(?![\d.,])", question)
    }

    question_ratios = {
        Decimal(n.replace(",", ".")) / 100
        for n in re.findall(r"(?<![\d.,])\d+(?:[.,]\d+)?(?=\s*(?:%|phần trăm\b))", question)
    }

    def visit(node):
        if isinstance(node, ast.Name):
            if node.id not in operands:
                operands[node.id] = get_operand(node.id)
            bound = operands[node.id]
            return Decimal(bound["value"]) * Decimal(bound["scale"])
        if isinstance(node, ast.Constant) and type(node.value) in {int, float}:
            n = Decimal(ast.get_source_segment(expression, node).replace("_", ""))
            if (
                n in STANDARD_CONSTANTS
                or n in question_numbers
                or n in question_ratios
                or n == Decimal("0.01")
            ):
                constants[str(n)] = (
                    "question"
                    if n in question_numbers
                    else "question_percent_ratio"
                    if n in question_ratios
                    else "standard"
                )
                return n
        if isinstance(node, ast.BinOp) and type(node.op) in MATH:
            return MATH[type(node.op)](visit(node.left), visit(node.right))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
            base, exponent = visit(node.left), visit(node.right)
            if abs(exponent) > 100:
                raise ValueError("calculation_exponent_bounds")
            return base**exponent
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -visit(node.operand)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "abs"
            and len(node.args) == 1
            and not node.keywords
        ):
            return abs(visit(node.args[0]))
        raise ValueError(
            "Dùng mã ô (T…R…C…), F hoặc P thay số tài chính. Giữ các hằng số có căn cứ như 100, 365."
        )

    with localcontext(Context(prec=34, rounding=ROUND_HALF_UP)):
        value = visit(tree.body)
        if not operands or not value.is_finite():
            raise ValueError("calculation_requires_source_operands")
        rounded = value.quantize(Decimal(1).scaleb(-precision))
    return dict(
        expression=expression,
        operands=operands,
        constants=constants,
        exact=str(value),
        value=str(rounded),
        decimals=precision,
        decimal_context="prec=34,ROUND_HALF_UP",
    )


def result_unit(expression, operands, proposed, requested):
    """Validate dimension for monetary arithmetic; semantic formula remains Verifier's job."""
    unit = requested or proposed
    normalized = normalize_search(unit)
    target = (
        1
        if normalized in {"vnd", "vnd dong", "dong"}
        else 0
        if (normalized in {"lan", "phan tram"} or unit.strip() == "%")
        else None
    )
    money = {"vnd", "dong", "vnd dong"}
    if target is None or not all(normalize_search(op["unit"]) in money for op in operands.values()):
        return unit

    def dimension(node):
        if isinstance(node, ast.Name):
            return 1
        if isinstance(node, ast.Constant):
            return 0
        if isinstance(node, (ast.UnaryOp, ast.Call)):
            return dimension(node.operand if isinstance(node, ast.UnaryOp) else node.args[0])
        if isinstance(node, ast.BinOp):
            left, right = dimension(node.left), dimension(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if left != right:
                    raise ValueError("Cộng/trừ các đại lượng khác thứ nguyên.")
                return left
            if isinstance(node.op, ast.Mult):
                return left + right
            if isinstance(node.op, ast.Div):
                return left - right
            if isinstance(node.op, ast.Pow) and right == 0:
                if left == 0:
                    return 0
                if isinstance(node.right, ast.Constant):
                    return left * node.right.value
        raise ValueError("Không xác định thứ nguyên của biểu thức.")

    tree = ast.parse(expression, mode="eval")
    if dimension(tree.body) != target:
        raise ValueError(f"Biểu thức không cùng thứ nguyên với đơn vị kết quả {unit}.")
    if unit.strip() == "%" or normalized == "phan tram":
        constants = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant)}
        if not ({100, 0.01} & constants):
            raise ValueError("Tỷ lệ phần trăm cần quy đổi ×100 hoặc /0,01 trong biểu thức.")
    return unit
