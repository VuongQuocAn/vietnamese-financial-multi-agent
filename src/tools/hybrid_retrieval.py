"""Local chunk retrieval: FTS5 + E5 dense + RRF; độc lập với M5/M6/M7."""

import hashlib
import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from time import perf_counter

import numpy as np

from ..core.persistence import atomic_json
from ..evidence.composition import payload_sha256
from ..evidence.json_catalog import resolve_pointer
from ..evidence.search import normalize_search

MODEL = "intfloat/multilingual-e5-small"
REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"
ONNX_FILE = "onnx/model_qint8_avx512_vnni.onnx"


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_file(root, name, expected_hash):
    path = (Path(root) / name).resolve()
    if not path.is_relative_to(Path(root).resolve()) or file_hash(path) != expected_hash:
        raise ValueError("source_file_hash_or_path_mismatch")
    return path


def reciprocal_rank_fusion(rankings, *, constant=60):
    if constant <= 0:
        raise ValueError("rrf_constant_must_be_positive")
    scores = defaultdict(float)
    for ranking in rankings:
        for rank, item in enumerate(dict.fromkeys(ranking), 1):
            scores[item] += 1.0 / (constant + rank)
    return sorted(scores, key=lambda item: (-scores[item], item)), dict(scores)


class LocalE5:
    """Encoder ONNX CPU, mean pooling/L2; cửa sổ đầy đủ, không silent truncation."""

    def __init__(self, cache, *, download=False, threads=4):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        files = {
            name: Path(
                hf_hub_download(
                    MODEL, name, revision=REVISION, cache_dir=cache, local_files_only=not download
                )
            )
            for name in ("tokenizer.json", ONNX_FILE)
        }
        self.tokenizer = Tokenizer.from_file(str(files["tokenizer.json"]))
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        self.session = ort.InferenceSession(
            str(files[ONNX_FILE]), sess_options=options, providers=["CPUExecutionProvider"]
        )
        self.metadata = dict(
            model=MODEL,
            revision=REVISION,
            onnx_file=ONNX_FILE,
            file_sha256={name: file_hash(path) for name, path in files.items()},
            dimensions=384,
            pooling="attention_mask_mean_then_l2_window_mean_then_l2",
            max_tokens=512,
            overlap_tokens=64,
            query_prefix="query: ",
            passage_prefix="passage: ",
        )

    def encode(self, texts, *, query=False, batch_size=16, progress=None):
        prefix = self.tokenizer.encode(
            "query: " if query else "passage: ", add_special_tokens=False
        ).ids
        capacity = 512 - 2 - len(prefix)
        windows, token_counts = [], []
        for owner, text in enumerate(texts):
            tokens = self.tokenizer.encode(text, add_special_tokens=False).ids
            token_counts.append(len(tokens))
            start = 0
            while True:
                part = tokens[start : start + capacity]
                ids = [
                    self.tokenizer.token_to_id("<s>"),
                    *prefix,
                    *part,
                    self.tokenizer.token_to_id("</s>"),
                ]
                windows.append((owner, ids))
                if start + capacity >= len(tokens):
                    break
                start += capacity - 64
        windows.sort(key=lambda item: len(item[1]))
        result = np.zeros((len(texts), 384), dtype=np.float32)
        owners = np.zeros(len(texts), dtype=np.int64)
        input_names = {item.name for item in self.session.get_inputs()}
        for offset in range(0, len(windows), batch_size):
            batch = windows[offset : offset + batch_size]
            width = max(len(ids) for _, ids in batch)
            ids = np.full((len(batch), width), self.tokenizer.token_to_id("<pad>"), dtype=np.int64)
            mask = np.zeros_like(ids)
            for i, (_, values) in enumerate(batch):
                ids[i, : len(values)] = values
                mask[i, : len(values)] = 1
            feed = {"input_ids": ids, "attention_mask": mask, "token_type_ids": np.zeros_like(ids)}
            hidden = self.session.run(None, {k: v for k, v in feed.items() if k in input_names})[0]
            pooled = (hidden * mask[:, :, None]).sum(axis=1) / mask.sum(axis=1)[:, None]
            pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
            for (owner, _), vector in zip(batch, pooled, strict=True):
                result[owner] += vector
                owners[owner] += 1
            if progress:
                progress(min(offset + batch_size, len(windows)), len(windows))
        result /= np.maximum(owners[:, None], 1)
        result /= np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-12)
        if not np.isfinite(result).all() or not np.allclose(
            np.linalg.norm(result, axis=1), 1, atol=1e-5
        ):
            raise ValueError("invalid_embeddings")
        return result, dict(
            texts=len(texts),
            windows=len(windows),
            multiwindow_texts=sum(n > capacity for n in token_counts),
            max_content_tokens=max(token_counts, default=0),
            truncated_tokens=0,
        )


class HybridChunkRetrieval:
    """Một index dẫn xuất trên projection; kết quả giữ locators để hydrate nguồn gốc."""

    @classmethod
    def build(cls, projection, output, encoder, *, progress=None):
        projection, output = Path(projection).resolve(), Path(output).resolve()
        if (
            output == projection
            or output.is_relative_to(projection)
            or projection.is_relative_to(output)
        ):
            raise ValueError("index_must_be_separate")
        output.mkdir(parents=True, exist_ok=False)
        manifest = json.loads((projection / "manifest.json").read_bytes())
        if manifest["validation"] != "PASS":
            raise ValueError("unvalidated_projection")
        db = sqlite3.connect(output / "lexical.sqlite")
        db.execute(
            "CREATE TABLE chunks(id INTEGER PRIMARY KEY, chunk_id TEXT UNIQUE, "
            "document_id TEXT, snapshot_id TEXT, alias TEXT, file TEXT, offset INTEGER, "
            "body TEXT)"
        )
        db.execute(
            "CREATE VIRTUAL TABLE lexical USING fts5(body, content='chunks', content_rowid='id')"
        )
        texts, ids = [], []
        for document in manifest["documents"]:
            path = checked_file(projection, document["chunks_file"], document["chunks_sha256"])
            with path.open("rb") as stream:
                while True:
                    offset = stream.tell()
                    line = stream.readline()
                    if not line:
                        break
                    chunk = json.loads(line)
                    expected = "chunk:sha256:" + payload_sha256(
                        {k: v for k, v in chunk.items() if k != "chunk_id"}
                    )
                    if chunk["chunk_id"] != expected:
                        raise ValueError("chunk_payload_mismatch")
                    ids.append(chunk["chunk_id"])
                    texts.append(chunk["content"])
                    db.execute(
                        "INSERT INTO chunks VALUES (?,?,?,?,?,?,?,?)",
                        (
                            len(ids),
                            chunk["chunk_id"],
                            chunk["document_id"],
                            chunk["snapshot_id"],
                            chunk["document_alias"],
                            document["chunks_file"],
                            offset,
                            normalize_search(chunk["content"]),
                        ),
                    )
        if len(ids) != manifest["totals"]["chunks"]:
            raise ValueError("projection_count_mismatch")
        started = perf_counter()
        vectors, statistics = encoder.encode(texts, progress=progress)
        np.save(output / "vectors.npy", vectors, allow_pickle=False)
        db.execute("INSERT INTO lexical(lexical) VALUES ('rebuild')")
        db.commit()
        db.close()
        atomic_json(
            output / "manifest.json",
            dict(
                version="rag-hybrid-v1",
                projection_manifest_sha256=file_hash(projection / "manifest.json"),
                encoder=encoder.metadata,
                chunk_ids_sha256=payload_sha256(ids),
                chunks=len(ids),
                files={
                    name: file_hash(output / name) for name in ("vectors.npy", "lexical.sqlite")
                },
                encoding=statistics,
                encoding_and_fts_seconds=perf_counter() - started,
            ),
        )

    def __init__(self, projection, index, encoder):
        self.projection, self.index, self.encoder = Path(projection), Path(index), encoder
        self.manifest = json.loads((self.index / "manifest.json").read_bytes())
        checked_file(self.projection, "manifest.json", self.manifest["projection_manifest_sha256"])
        self.sources = json.loads((self.projection / "manifest.json").read_bytes())
        for doc in self.sources["documents"]:
            checked_file(self.projection, doc["chunks_file"], doc["chunks_sha256"])
        for name, sha in self.manifest["files"].items():
            checked_file(self.index, name, sha)
        if self.manifest["encoder"] != encoder.metadata:
            raise ValueError("encoder_index_mismatch")
        self.db = sqlite3.connect(
            (self.index / "lexical.sqlite").resolve().as_uri() + "?mode=ro", uri=True
        )
        self.rows = self.db.execute(
            "SELECT chunk_id,document_id,snapshot_id,alias,file,offset FROM chunks ORDER BY id"
        ).fetchall()
        self.vectors = np.load(self.index / "vectors.npy", allow_pickle=False, mmap_mode="r")
        if (
            self.vectors.shape != (len(self.rows), encoder.metadata["dimensions"])
            or payload_sha256([r[0] for r in self.rows]) != self.manifest["chunk_ids_sha256"]
        ):
            raise ValueError("vector_row_alignment_mismatch")

    def search(self, query, *, document_id=None, snapshot_id=None, top_k=5, candidate_k=50):
        if not query.strip() or not 1 <= top_k <= candidate_k <= 200:
            raise ValueError("invalid_query_or_limits")
        started = perf_counter()
        terms = list(dict.fromkeys(normalize_search(query).split()))
        lexical = []
        if terms:
            expression = " OR ".join('"' + term + '"' for term in terms)
            lexical = [
                row[0] - 1
                for row in self.db.execute(
                    "SELECT c.id FROM lexical JOIN chunks c ON c.id=lexical.rowid "
                    "WHERE lexical MATCH ? AND (? IS NULL OR c.document_id=?) "
                    "AND (? IS NULL OR c.snapshot_id=?) ORDER BY bm25(lexical),c.id LIMIT ?",
                    (expression, document_id, document_id, snapshot_id, snapshot_id, candidate_k),
                )
            ]
        lexical_ms = (perf_counter() - started) * 1000
        dense_start = perf_counter()
        vector, _ = self.encoder.encode([query], query=True)
        eligible = np.array(
            [
                i
                for i, row in enumerate(self.rows)
                if (document_id is None or row[1] == document_id)
                and (snapshot_id is None or row[2] == snapshot_id)
            ],
            dtype=np.int64,
        )
        scores = self.vectors[eligible] @ vector[0]
        dense = eligible[np.argsort(-scores, kind="stable")[:candidate_k]].tolist()
        dense_ms = (perf_counter() - dense_start) * 1000
        ranked, rrf = reciprocal_rank_fusion([lexical, dense])
        lexical_ranks = {item: rank for rank, item in enumerate(lexical, 1)}
        dense_ranks = {item: rank for rank, item in enumerate(dense, 1)}
        hits = []
        for i in ranked[:top_k]:
            row = self.rows[i]
            with (self.projection / row[4]).open("rb") as stream:
                stream.seek(row[5])
                chunk = json.loads(stream.readline())
            if chunk["chunk_id"] != row[0] or chunk["chunk_id"] != "chunk:sha256:" + payload_sha256(
                {k: v for k, v in chunk.items() if k != "chunk_id"}
            ):
                raise ValueError("retrieved_chunk_changed")
            hits.append(
                dict(
                    chunk_id=row[0],
                    document_id=row[1],
                    snapshot_id=row[2],
                    document_alias=row[3],
                    source_page=chunk["source_page"],
                    pdf_page=chunk["pdf_page"],
                    missing_pages=chunk["missing_pages"],
                    chunk_type=chunk["chunk_type"],
                    rrf_score=rrf[i],
                    bm25_rank=lexical_ranks.get(i),
                    dense_rank=dense_ranks.get(i),
                    evidence_selectors=[
                        {
                            k: m[k]
                            for k in (
                                "evidence_ref",
                                "catalog_selector",
                                "payload_sha256",
                                "source_selector",
                            )
                        }
                        for m in chunk["members"]
                    ],
                    fact_refs=chunk["fact_refs"],
                    financial_fact_verified=False,
                )
            )
        return dict(
            hits=hits,
            bm25_chunk_ids=[self.rows[i][0] for i in lexical],
            dense_chunk_ids=[self.rows[i][0] for i in dense],
            timing_ms=dict(
                bm25=lexical_ms, dense=dense_ms, hybrid=(perf_counter() - started) * 1000
            ),
        )

    def hydrate(self, hit, corpus, source_root):
        doc = next(
            d
            for d in self.sources["documents"]
            if d["document_id"] == hit["document_id"] and d["snapshot_id"] == hit["snapshot_id"]
        )
        bundle = (Path(corpus) / doc["catalog_bundle"]).resolve()
        if not bundle.is_relative_to(Path(corpus).resolve()):
            raise ValueError("catalog_outside_root")
        data = {
            name: json.loads(checked_file(bundle, name, sha).read_bytes())
            for name, sha in doc["catalog_pins"].items()
        }
        records, facts, pages = [], [], {}
        for link, name, output in [
            *[(m, "document-evidence.json", records) for m in hit["evidence_selectors"]],
            *[(f, "canonical-facts.json", facts) for f in hit["fact_refs"]],
        ]:
            record = resolve_pointer(data[name], link["catalog_selector"])
            if payload_sha256(record) != link["payload_sha256"]:
                raise ValueError("hydrated_payload_mismatch")
            for source in [*record["sources"], *record.get("member_sources", [])]:
                ref = source["reference"]
                number = ref["anchor"]["page"]["page"]
                pin = next(p for p in doc["source_manifest"]["pages"] if p["page"] == number)
                if number not in pages:
                    pages[number] = json.loads(
                        checked_file(source_root, pin["path"], pin["sha256"]).read_bytes()
                    )
                page = pages[number]
                resolve_pointer(page, ref["source_pointer"])
            output.append(record)
        return dict(
            chunk_id=hit["chunk_id"],
            evidence=records,
            source_facts=facts,
            financial_fact_verified=False,
            pdf_verified=False,
        )

    def close(self):
        self.db.close()
