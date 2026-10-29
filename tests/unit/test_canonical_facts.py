"""Synthetic invariants M3-02; không chứng minh accuracy PDF thực tế."""

import json
from copy import deepcopy
from decimal import Decimal

import pytest
from vietnamese_financial_multi_agent.accounting.contracts import FinancialNormalizationResult
from vietnamese_financial_multi_agent.accounting.quality import (
    AssessableEvidence,
    assess_evidence_for_task,
)
from vietnamese_financial_multi_agent.evidence import (
    CanonicalFactRepository,
    ObservationConflict,
    TaskQualityContext,
    fact_from_m2,
    facts_from_persisted_result,
)

from .test_evidence_contracts import fact


def m2_evidence():
    f = fact()
    return AssessableEvidence(
        evidence_id=f.local_observation_id,
        canonical_item_id=f.canonical_item_id,
        source_item_code=f.source_item_code,
        raw_header="Năm trước 2024",
        extraction=FinancialNormalizationResult(
            contract_version="financial_normalization_v1",
            value=f.value,
            context=f.context,
            provenance=[s.reference for s in f.sources],
        ),
        source_metadata={"request_id": "synthetic-request", "source": {"page": 7}},
    )


def convert(e=None, document="synthetic-BBS_2025", snapshot="attempt-a"):
    return fact_from_m2(
        e or m2_evidence(),
        document_id=document,
        snapshot_id=snapshot,
        company_id="synthetic-company",
    )


def test_m2_adapter_copies_raw_decimal_context_and_page_sources():
    e = m2_evidence()
    e.extraction.value.normalized_value = Decimal("12345678901234567890.0012300")
    e.extraction_issues = ["scope_unconfirmed"]
    before = e.model_dump_json()
    f = convert(e)
    assert f.value == e.extraction.value and f.context == e.extraction.context
    assert f.raw_header == e.raw_header and f.source_metadata == e.source_metadata
    assert f.source_item_code == "10" and f.canonical_item_id == "b02.net_revenue"
    assert f.sources[0].reference == e.extraction.provenance[0]
    assert f.sources[0].reference.provenance_level == "page"
    assert f.sources[0].reference.anchor.cell_id is None
    assert f.quality_context == [] and not f.financial_fact_verified
    assert any(i.code == "m2_extraction_issue" for i in f.resolution_issues)
    f.source_metadata["source"]["page"] = 9
    f.value.issues.append("caller-edit")
    assert e.model_dump_json() == before


@pytest.mark.parametrize("decision", ["usable", "usable_with_caveat", "insufficient", "conflicted"])
def test_persisted_m2_projection_preserves_item_quality_without_reassessment(tmp_path, decision):
    quality = assess_evidence_for_task([m2_evidence()])
    item = quality.items[0]
    item.decision = decision
    item.caveats = ["synthetic-caveat"]
    quality.decision = "insufficient"  # Task decision phải không thay item decision.
    result = dict(document_id="doc", attempt_id="attempt", quality=quality.model_dump(mode="json"))
    before = deepcopy(result)
    f = facts_from_persisted_result(result)[0]
    q = f.quality_context[0]
    assert q == TaskQualityContext(
        task_type=quality.task_type,
        decision=decision,
        evidence_ids=[item.evidence.evidence_id],
        issues=item.issues,
        caveats=item.caveats,
    )
    assert f.company_id is None and result == before
    repo = CanonicalFactRepository(tmp_path)
    repo.put(f)
    restored = CanonicalFactRepository(tmp_path).get(f.observation_identity())
    assert restored.quality_context == f.quality_context
    assert not restored.financial_fact_verified


def test_unmapped_missing_values_and_context_survive_restart(tmp_path):
    e = m2_evidence()
    e.canonical_item_id = None
    e.extraction.context.period = None
    e.extraction.context.period_type = None
    e.extraction.context.reporting_scope = None
    e.extraction.value.normalized_value = None
    e.extraction.value.status = "unresolved"
    e.extraction.value.raw_value = "-"
    f = fact_from_m2(e, document_id="doc", snapshot_id="snapshot")
    repo = CanonicalFactRepository(tmp_path)
    assert repo.put(f) == "stored"
    restored = CanonicalFactRepository(tmp_path).get(f.observation_identity())
    assert restored == f and restored.semantic_key() is None
    assert restored.context.period is None  # anchor.page.year vẫn 2025.
    assert restored.context.reporting_scope is None and restored.company_id is None
    assert restored.value.normalized_value is None and restored.value.raw_value == "-"
    assert restored.value.status == "unresolved" and restored.canonical_item_id is None
    assert {i.code for i in restored.resolution_issues} >= {
        "missing_company_id",
        "missing_period",
        "missing_reporting_scope",
        "missing_canonical_mapping",
    }


def test_cross_document_and_reextraction_keep_three_observations(tmp_path):
    repo = CanonicalFactRepository(tmp_path)
    observations = [
        convert(document="synthetic-BBS_2024"),
        convert(document="synthetic-BBS_2025"),
        convert(document="synthetic-BBS_2025", snapshot="attempt-b"),
    ]
    for f in observations:
        assert repo.put(f) == "stored"
    restarted = CanonicalFactRepository(tmp_path)
    matches = restarted.query_by_semantic_key(observations[0].semantic_key())
    assert len(matches) == 3
    assert len({f.observation_identity() for f in matches}) == 3
    assert len({f.sources[0].source_key() for f in matches}) == 3
    assert len(restarted.list_by_document("synthetic-BBS_2025")) == 2
    assert restarted.list_by_document("synthetic-BBS_2025", "attempt-b") == [observations[2]]
    assert restarted.list_by_document("missing") == []


def test_exact_decimal_roundtrip_and_explicit_identity_conflict(tmp_path):
    f = convert()
    f.value.normalized_value = Decimal("12345678901234567890.0012300")
    f.context.scale = Decimal("1000.00")
    repo = CanonicalFactRepository(tmp_path)
    assert repo.put(f) == "stored" and repo.put(f) == "idempotent"
    restored = CanonicalFactRepository(tmp_path).get(f.observation_identity())
    assert restored.model_dump_json() == f.model_dump_json()
    assert str(restored.value.normalized_value) == "12345678901234567890.0012300"
    assert str(restored.context.scale) == "1000.00"
    changed = f.model_copy(deep=True)
    changed.value.normalized_value += Decimal("1")
    with pytest.raises(ObservationConflict) as error:
        repo.put(changed)
    assert error.value.existing == f and error.value.incoming == changed
    assert repo.get(f.observation_identity()) == f
    # Dù Decimal bằng số học, khác biểu diễn nguồn cũng không overwrite.
    changed = f.model_copy(deep=True)
    changed.context.scale = Decimal("1000")
    with pytest.raises(ObservationConflict):
        repo.put(changed)


@pytest.mark.parametrize("field", ["document_id", "snapshot_id", "evidence_id"])
def test_missing_identity_is_persisted_only_in_explicit_quarantine(tmp_path, field):
    e = m2_evidence()
    options = dict(document_id="doc", snapshot_id="attempt")
    if field == "evidence_id":
        e.evidence_id = " "
    else:
        options[field] = None
    f = fact_from_m2(e, **options)
    assert f.observation_identity() is None
    repo = CanonicalFactRepository(tmp_path)
    assert repo.put(f) == repo.put(f) == "quarantined"
    assert repo.list_by_document("doc") == []
    restored = CanonicalFactRepository(tmp_path).list_quarantine()
    assert len(restored) == 1 and restored[0] == f
    assert restored[0].observation_identity() is None


def test_missing_persisted_quality_is_explicit_and_duplicate_storage_is_rejected(tmp_path):
    assert facts_from_persisted_result({"quality": None, "records": []}) == []
    with pytest.raises(ValueError, match="quality evidence unavailable"):
        facts_from_persisted_result({"quality": None, "records": [{}]})
    f = convert()
    repo = CanonicalFactRepository(tmp_path)
    repo.put(f)
    path = tmp_path / "canonical-facts.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["observations"].append(payload["observations"][0])
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate identity"):
        repo.list_by_document(f.document_id)
