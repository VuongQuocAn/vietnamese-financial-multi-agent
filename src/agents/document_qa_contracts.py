"""Typed document lane shared by M5, M6 and M7."""

import re
from typing import Literal

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..evidence.retrieval import EvidenceCitation, RetrievalReference
from ..evidence.search import (
    DocumentSearchResponse,
    SearchDocumentEvidenceRequest,
    normalize_search,
)
from .planner_contracts import PlannerOperation

DocumentKind = Literal["exact_text", "entity_role", "table_labels", "source_excerpt"]
ROLES = {
    "nguoi lap": "Người lập",
    "ke toan truong": "Kế toán trưởng",
    "giam doc": "Giám đốc",
}


class DocumentRequirement(FinancialModel):
    target: str
    label: str
    kind: DocumentKind
    query: str


class DocumentSearchOperation(PlannerOperation):
    operation: Literal["search_document_evidence"] = "search_document_evidence"
    requirement: DocumentRequirement
    request: SearchDocumentEvidenceRequest


class DocumentEvidenceBundle(FinancialModel):
    operation: DocumentSearchOperation
    result: DocumentSearchResponse


class DocumentCandidate(FinancialModel):
    version: Literal["document_candidate_v1"] = "document_candidate_v1"
    candidate_id: str
    kind: Literal["document"] = "document"
    claim_type: DocumentKind
    requirement: DocumentRequirement
    content: str
    company_id: str
    document_id: str
    source_document_id: str
    snapshot_id: str
    composition_id: str
    composition_sha256: str
    period: None = None
    references: list[RetrievalReference] = Field(min_length=1, max_length=3)
    citations: list[EvidenceCitation] = Field(min_length=1)
    quotations: list[str] = Field(min_length=1)
    person: str | None = None
    caveats: list[str] = Field(default_factory=list)
    verification_status: Literal["pending"] = "pending"


def document_intent(question):
    """Recognize supported source requests and preserve separate role requirements."""
    text = normalize_search(question)
    specs = []

    def add(label, kind, query):
        specs.append(
            DocumentRequirement(target=normalize_search(label), label=label, kind=kind, query=query)
        )

    signer = bool(re.search(r"\b(nguoi ky|ai ky|chu ky|ky bao cao)\b", text))
    roles = [key for key in ROLES if re.search(rf"\b{key}\b", text)]
    for key in roles or (list(ROLES) if signer else []):
        add(ROLES[key], "entity_role", ROLES[key])
    if "nhan vien quan ly chu chot" in text:
        add("Nhân viên quản lý chủ chốt", "exact_text", "nhân viên quản lý chủ chốt")
    if re.search(r"\b(bang tien|khoan muc tien)\b", text):
        add("Khoản mục trong bảng tiền", "table_labels", "tiền mặt")
    if "y kien kiem toan" in text:
        add("Ý kiến kiểm toán", "exact_text", "ý kiến kiểm toán")
    if not specs and re.search(r"\b(thuyet minh|chinh sach|noi dung b09)\b", text):
        topic = re.split(r"\bvề\s+", question, flags=re.I)[-1].strip(" .?")
        topic = re.sub(r"^(?:các\s+)?khoản\s+", "", topic, flags=re.I)
        topic = re.sub(r"\s+(?:không|như thế nào|thế nào|ra sao).*$", "", topic, flags=re.I)
        if topic == question.strip(" .?"):
            topic = re.sub(r"^.*?chính sách\s+", "", topic, flags=re.I)
            topic = re.sub(r"\s+được thuyết minh.*$", "", topic, flags=re.I)
        add(topic, "source_excerpt", re.sub(r"^chính sách\s+", "", topic, flags=re.I))
    outside_quotes = normalize_search(re.sub(r'["“][^"”]*["”]', "", question))
    mixed = bool(
        re.search(
            r"\b(bao nhieu|so tien|gia tri|so du|ty le|ty suat|he so|roe|roa|ebitda|tinh toan)\b",
            outside_quotes,
        )
    )
    if specs:
        from ..tools.question_understanding import understand

        prefix = re.split(r"\b(?:thuyết minh|chính sách|nội dung b09)\b", question, flags=re.I)[0]
        if prefix != question:
            parsed_prefix, _ = understand(prefix)
            mixed = mixed or bool(parsed_prefix.canonical_item_id or parsed_prefix.formula_id)
    exact_lookup = re.search(r"\b(o dau|xuat hien|trich nguyen van|tim cum)\b", outside_quotes)
    if exact_lookup or (not mixed and re.search(r"\bghi\b", outside_quotes)):
        quotes = re.findall(r'["“]([^"”]{3,180})["”]', question)
        for quote in quotes[:8]:
            if normalize_search(quote) and not any(
                r.target == normalize_search(quote) for r in specs
            ):
                add(quote, "exact_text", quote)
    if not specs:
        return "other", specs
    if not mixed:
        from ..tools.question_understanding import understand

        # A financial target in a separate conjunct must not be dropped.
        for clause in re.split(r"\b(?:va|dong thoi|kem theo)\b", outside_quotes)[1:]:
            parsed, _ = understand(clause)
            if parsed.canonical_item_id or parsed.formula_id:
                mixed = True
                break
    return ("mixed" if mixed else "document"), specs
