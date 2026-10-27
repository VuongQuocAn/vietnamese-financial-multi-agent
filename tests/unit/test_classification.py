"""Synthetic integration, không API/keys hoặc ground truth tài chính."""

import json
from decimal import Decimal
from unittest.mock import Mock

import pytest
from google.genai import types
from vietnamese_financial_multi_agent.core.data_config import load_data_config
from vietnamese_financial_multi_agent.core.gemini_adapter import GeminiAdapter
from vietnamese_financial_multi_agent.core.llm_cache import CachedLLMService
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.core.llm_quota_budget import (
    BudgetLimit,
    GatewayBinding,
    ProjectPolicy,
    ProjectRegistry,
    QuotaBudgetGuard,
    QuotaLimits,
    Reservation,
)
from vietnamese_financial_multi_agent.document_processing.checkpoints import CheckpointStore
from vietnamese_financial_multi_agent.document_processing.classification import (
    SCHEMA_REF,
    TITLES,
    ClassificationConfig,
    PageClassifier,
    aggregate_document,
    classification_schema_registry,
)
from vietnamese_financial_multi_agent.document_processing.contracts import (
    OCRPage,
    RawPageIdentity,
    validate_understanding_quality,
)
from vietnamese_financial_multi_agent.document_processing.contracts.path_mapping import (
    PathMappingResult,
)
from vietnamese_financial_multi_agent.document_processing.ocr_loader import LoadedOCRPage


def loaded(label="B01", *, number=1, source="synthetic-doc/run-A", texts=None):
    metadata = dict(symbol="SYNTHETIC", year="2025", page=number, image=f"p{number}.png")
    texts = texts if texts is not None else [label, TITLES[label]]
    raw = OCRPage.model_validate(
        dict(
            page={**metadata, "width": 200, "height": 1000, "dpi": 300},
            elements=[
                dict(id=f"e{i}", type="text", bbox=[1, 1 + i * 20, 190, 15 + i * 20], text=t)
                for i, t in enumerate(texts)
            ],
            provenance=dict(
                architecture="synthetic",
                layout_engine="synthetic",
                text_detector="synthetic",
                text_recognizer="synthetic",
                checkbox_detector="synthetic",
                checkbox_detector_source="synthetic",
                signature_detector="synthetic",
                detection_view=dict(
                    width=200, height=1000, scale_x_to_original=1, scale_y_to_original=1
                ),
                checkbox_detection=dict(
                    native_proposals=0,
                    magnified_proposals=0,
                    accepted=0,
                    threshold=0.5,
                    proposal_threshold=0.3,
                    seconds=0,
                ),
                signature_full_page_threshold=0.7,
                signature_context_roi_threshold=0.28,
                signature_fallback_detector=None,
                signature_full_page_proposal_count=0,
                signature_final_count=0,
                signature_policy="synthetic",
                checkbox_policy="synthetic",
                seal_policy="synthetic",
                notes=["Synthetic only"],
                page_seconds=0,
            ),
        )
    )
    mapping = PathMappingResult.model_validate(
        dict(
            contract_version="path_mapping_v1",
            reference=dict(
                original_path=f"source/p{number}.json",
                category="ocr_page_json",
                source_ref=source,
                source_location=[],
                anchor=dict(page={**metadata, "source_ref": source}, status="unresolved"),
            ),
            status="resolved",
            candidate_targets=[],
            existence_check="exists",
            containment_check="verified",
            issues=[],
        )
    )
    return LoadedOCRPage(raw, mapping, (), True)


def prediction(label="B01", disposition="supported", evidence=None):
    return dict(
        label=label, disposition=disposition, evidence=[0, 1] if evidence is None else evidence
    )


def config(**changes):
    return ClassificationConfig(
        taxonomy_version="experimental-candidates-v1",
        enabled_labels=tuple(TITLES),
        configuration_revision="synthetic-adapter-v1",
        **changes,
    )


class Harness:
    def __init__(self, tmp_path, *, output=None, budget=False, rpm=100):
        self.client = Mock()
        self.set_output(prediction() if output is None else output)
        schemas = classification_schema_registry()
        adapter = GeminiAdapter(self.client, schema_registry=schemas)
        gateway = SharedLLMGateway({"gemini": adapter}, schema_registry=schemas)
        policy = ProjectPolicy(
            account_ref="synthetic-account",
            project_ref="synthetic-project",
            credential_refs=("synthetic-key",),
            provider="gemini",
            model=config().model,
            tier="synthetic",
            quota_limits=QuotaLimits(rpm=rpm, tpm=1_000_000, rpd=100),
            mapping_confirmed=True,
            verification_source="synthetic-test",
            budget=BudgetLimit(amount=Decimal("1"), currency="USD") if budget else None,
        )
        self.guard = QuotaBudgetGuard(
            ProjectRegistry([policy]),
            [
                GatewayBinding(
                    policy.account_ref,
                    policy.project_ref,
                    "synthetic-key",
                    "gemini",
                    policy.model,
                    gateway,
                )
            ],
        )
        self.guard.initialize(confirmed_fresh_scope=True)
        self.service = CachedLLMService(
            self.guard,
            tenant_ref="synthetic-tenant",
            project_ref=policy.project_ref,
            credential_refs=frozenset({"synthetic-key"}),
            scope_confirmed=True,
            configuration_revision="synthetic-v1",
            schema_registry=schemas,
        )
        data_config = load_data_config(
            {
                "FINANCIAL_REPORT_DIR": "data/raw",
                "FINANCIAL_OCR_DIR": "data/processed",
            },
            project_root=tmp_path,
        )
        self.store = CheckpointStore(tmp_path / "checkpoints", data_config=data_config)
        self.classifier = PageClassifier(self.service, config(), checkpoints=self.store)

    def set_output(self, payload):
        self.client.models.generate_content.return_value = types.GenerateContentResponse(
            candidates=[
                types.Candidate(
                    content=types.Content(parts=[types.Part(text=json.dumps(payload))]),
                    finish_reason="STOP",
                )
            ],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=100,
                candidates_token_count=20,
                total_token_count=120,
            ),
        )

    def classify(self, page=None, **changes):
        page = page or loaded()
        return self.classifier.classify(
            page,
            source_ref=page.mapping_result.reference.source_ref,
            credential_ref="synthetic-key",
            reservation=Reservation(
                token_upper_bound=20_000, token_basis="caller_attested_upper_bound"
            ),
            **changes,
        )

    @property
    def calls(self):
        return self.client.models.generate_content.call_count


@pytest.mark.parametrize("label", list(TITLES))
def test_supported_preserves_source_and_provenance(tmp_path, label, capsys):
    h = Harness(tmp_path, output=prediction(label))
    page = loaded(label)
    before = page.page.export_source()
    result = h.classify(page)
    assert result.understanding.classification.label == label
    assert result.understanding.classification.status == "resolved"
    assert not validate_understanding_quality(result.understanding, raw_page=page.page)
    assert result.provenance == before["provenance"]
    assert page.page.export_source() == before
    assert result.source_mapping == page.mapping_result.export_result()
    assert result.llm_result.response.output.validation_status == "schema_valid"
    assert result.llm_result.response.usage.total_tokens == 120
    call = h.client.models.generate_content.call_args.kwargs
    assert call["model"] == "gemini-3.5-flash-lite"
    assert call["config"].response_json_schema == classification_schema_registry().schema_for(
        SCHEMA_REF
    )
    assert not list(h.store.output_root.glob("*.json"))
    assert capsys.readouterr().out == ""
    assert TITLES[label] not in repr(result)


@pytest.mark.parametrize(
    "texts,payload,code",
    [
        ([TITLES["B01"]], prediction(evidence=[0]), "insufficient_evidence"),
        (["B01 " + TITLES["B01"]], prediction(evidence=[0]), "insufficient_evidence"),
        (["B01", TITLES["B01"], "B02", TITLES["B02"]], prediction(), "conflicting_evidence"),
        (["B01", TITLES["B01"]], prediction(evidence=[0, 90]), "invalid_evidence"),
        (["B01", TITLES["B01"]], prediction(evidence=[-1, 0]), "invalid_evidence"),
        (["B01", TITLES["B01"]], prediction(evidence=[0, 0]), "invalid_evidence"),
        (["B01", TITLES["B01"]], prediction("B02"), "insufficient_evidence"),
        (["B01", TITLES["B01"]], prediction(None, "conflicting"), "conflicting_evidence"),
        (["Phụ lục"], prediction(None, "insufficient", []), "insufficient_evidence"),
    ],
)
def test_unresolved_not_checkpointed(tmp_path, texts, payload, code):
    h = Harness(tmp_path, output=payload)
    result = h.classify(loaded(texts=texts), checkpoint_allowed=True)
    assert result.understanding.classification.label is None
    assert result.understanding.classification.status == "unresolved"
    assert result.understanding.issues[0].code == code
    assert not list(h.store.output_root.glob("*.json"))


def test_cells_anchors_and_quality_gate(tmp_path):
    h = Harness(tmp_path)
    page = loaded(texts=["B01"])
    raw = page.page.export_source()
    raw["elements"].append(
        dict(
            id="table",
            type="table",
            name="Not evidence",
            crop="source/crop.png",
            bbox=[1, 25, 190, 45],
            cells=[
                dict(
                    id="c1",
                    row=0,
                    col=0,
                    bbox=[1, 25, 190, 45],
                    text=TITLES["B01"],
                    line_count=0,
                    lines=[],
                )
            ],
        )
    )
    page = LoadedOCRPage(OCRPage.model_validate(raw), page.mapping_result, (), True)
    result = h.classify(page)
    assert result.understanding.classification.status == "resolved"
    anchor = result.understanding.classification.anchors[1]
    assert anchor.table_id == "table" and anchor.cell_id == "c1"
    assert anchor.observed_bbox == [1, 25, 190, 45]
    page.page.elements[1].cells[0].line_count = 1
    assert h.classify(page).understanding.issues[0].code == "ocr_quality_review"


def quality_page(*, selected_cell=False):
    page = loaded(texts=["B01"] if selected_cell else None)
    raw = page.page.export_source()
    raw["elements"].append(
        dict(
            id="table",
            type="table",
            name="Synthetic",
            crop="source/crop.png",
            bbox=[1, 25, 190, 80],
            cells=[
                dict(
                    id="c0",
                    row=0,
                    col=0,
                    bbox=[1, 25, 190, 45],
                    text=TITLES["B01"] if selected_cell else "Unrelated",
                    line_count=0,
                    lines=[],
                ),
                dict(id="c1", row=0, col=2, bbox=[1, 50, 190, 70], text="", line_count=0, lines=[]),
            ],
        )
    )
    return LoadedOCRPage(OCRPage.model_validate(raw), page.mapping_result, (), True)


@pytest.mark.parametrize("selected_cell", [False, True])
def test_sparse_and_empty_cells_only_block_relevant_table(tmp_path, selected_cell):
    h = Harness(tmp_path)
    page = quality_page(selected_cell=selected_cell)
    before = page.page.export_source()
    result = h.classify(page, checkpoint_allowed=True)
    assert result.understanding.classification.status == (
        "unresolved" if selected_cell else "resolved"
    )
    assert page.page.export_source() == before and result.provenance == before["provenance"]
    assert not validate_understanding_quality(result.understanding, raw_page=page.page)


@pytest.mark.parametrize("location", ["selected", "outside", "candidate"])
@pytest.mark.parametrize("defect", ["inverted", "outside_page"])
def test_bbox_issues_on_selected_or_uncited_candidates_block(tmp_path, location, defect):
    h = Harness(tmp_path)
    page = loaded(texts=["B01", TITLES["B01"], "B02" if location == "candidate" else "Footer"])
    element = page.page.elements[0 if location == "selected" else 2]
    element.bbox = [2, 1, 1, 5] if defect == "inverted" else [1, 1, 201, 5]
    result = h.classify(page, checkpoint_allowed=True)
    assert result.understanding.classification.status == (
        "resolved" if location == "outside" else "unresolved"
    )


@pytest.mark.parametrize("defect", ["duplicate_id", "cell_reference", "page_dimension", "unknown"])
def test_global_or_unknown_issues_fail_closed(tmp_path, monkeypatch, defect):
    h = Harness(tmp_path)
    page = quality_page()
    if defect == "duplicate_id":
        page.page.elements[2].id = "e0"
    elif defect == "cell_reference":
        from vietnamese_financial_multi_agent.document_processing.contracts.raw_ocr import (
            OCRTextLine,
        )

        cell = page.page.elements[2].cells[0]
        cell.lines = [
            OCRTextLine(id="l", type="text", bbox=cell.bbox, text="Unrelated", cell_id="missing")
        ]
        cell.line_count = 1
    elif defect == "page_dimension":
        page.page.page.dpi = 0
    else:
        from vietnamese_financial_multi_agent.document_processing.contracts.validation import (
            QualityIssue,
        )

        monkeypatch.setattr(
            "vietnamese_financial_multi_agent.document_processing.classification.validate_quality",
            lambda _: [
                QualityIssue(code="future_issue", path=("elements", 2), message="Synthetic")
            ],
        )
    result = h.classify(page, checkpoint_allowed=True)
    assert result.understanding.classification.status == "unresolved"
    assert not list(h.store.output_root.glob("*.json"))


def test_conflicting_evidence_not_hidden_by_outside_quality_issue(tmp_path):
    h = Harness(tmp_path)
    page = loaded(texts=["B01", TITLES["B01"], "B02", TITLES["B02"], "Footer"])
    page.page.elements[4].bbox = [1, 1, 201, 5]
    assert h.classify(page).understanding.issues[0].code == "conflicting_evidence"


def test_policy_revision_stales_checkpoint_but_reuses_compatible_prediction(tmp_path, monkeypatch):
    h = Harness(tmp_path)
    first = h.classify(cache_allowed=True, checkpoint_allowed=True)
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.document_processing.classification.QUALITY_POLICY_REVISION",
        "synthetic-policy-v2",
    )
    second = h.classify(cache_allowed=True, checkpoint_allowed=True)
    assert second.checkpoint_status == "STALE" and second.llm_result.cache_hit
    assert second.config_fingerprint != first.config_fingerprint and h.calls == 1
    assert second.understanding == first.understanding
    assert h.classify(checkpoint_allowed=True).checkpoint_status == "HIT"
    from vietnamese_financial_multi_agent.document_processing.contracts.validation import (
        QualityIssue,
    )

    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.document_processing.classification.validate_quality",
        lambda _: [QualityIssue(code="new_unsafe_issue", path=(), message="Synthetic")],
    )
    rejected = h.classify(cache_allowed=True, checkpoint_allowed=True)
    assert rejected.checkpoint_status == "INVALID" and rejected.llm_result.cache_hit
    assert rejected.understanding.classification.status == "unresolved" and h.calls == 1


@pytest.mark.parametrize(
    "output",
    [
        {"label": "INVENTED", "disposition": "supported", "evidence": [0, 1]},
        {"label": "B01", "disposition": "supported", "evidence": [True, 1]},
        {"label": "B01"},
    ],
)
def test_invalid_schema(tmp_path, output):
    h = Harness(tmp_path, output=output)
    result = h.classify(checkpoint_allowed=True)
    assert result.understanding.classification.status == "unresolved"
    assert not list(h.store.output_root.glob("*.json"))


def test_provider_error_safe_and_no_retry(tmp_path, capsys):
    h = Harness(tmp_path)
    h.client.models.generate_content.side_effect = RuntimeError("synthetic-secret-do-not-log")
    result = h.classify(checkpoint_allowed=True)
    assert result.understanding.issues[0].code == "llm_failed"
    assert h.calls == 1
    assert "synthetic-secret" not in repr(result) + str(capsys.readouterr())


def test_checkpoint_restart_hit_and_semantic_revalidation(tmp_path):
    h = Harness(tmp_path)
    first = h.classify(checkpoint_allowed=True)
    assert first.checkpoint_status == "MISS"
    h.classifier = PageClassifier(h.service, config(), checkpoints=h.store)
    second = h.classify(checkpoint_allowed=True)
    assert second.checkpoint_status == "HIT" and second.llm_result is None and h.calls == 1
    assert second.understanding == first.understanding
    # Checksum có integrity vẫn không thay semantic gate: unsupported prediction phải reject.
    from vietnamese_financial_multi_agent.document_processing.checkpoints import (
        CheckpointRequest,
    )

    path = next(h.store.output_root.glob("*.json"))
    artifact = json.loads(path.read_text(encoding="utf-8"))
    h.store.save_verified(
        CheckpointRequest.model_validate(artifact["request"]), prediction("B02"), verified=True
    )
    assert h.classify(checkpoint_allowed=True).checkpoint_status == "INVALID"
    assert h.calls == 2


@pytest.mark.parametrize(
    "change", ["ocr", "provenance", "taxonomy", "version", "config", "prompt", "schema"]
)
def test_checkpoint_stale_and_cache_invalidated(tmp_path, change, monkeypatch):
    h = Harness(tmp_path)
    h.classify(checkpoint_allowed=True, cache_allowed=True)
    page = loaded()
    cfg = config()
    if change == "ocr":
        page.page.elements[0].text += " revised"
    elif change == "provenance":
        page.page.provenance.notes.append("revision")
    elif change == "taxonomy":
        cfg = cfg.model_copy(update={"taxonomy_version": "experimental-v2"})
    elif change == "version":
        cfg = cfg.model_copy(update={"processing_version": "classification-v2"})
    elif change == "config":
        cfg = cfg.model_copy(update={"max_output_tokens": 1024})
    elif change == "prompt":
        monkeypatch.setattr(
            "vietnamese_financial_multi_agent.document_processing.classification.PROMPT",
            "Revised synthetic instruction",
        )
    h.classifier = PageClassifier(h.service, cfg, checkpoints=h.store)
    if change == "schema":
        schema = h.classifier._schemas.schema_for(SCHEMA_REF)
        schema["description"] = "Synthetic schema revision"
        from vietnamese_financial_multi_agent.core.llm_schema_validation import LocalSchemaRegistry

        h.classifier._schemas = LocalSchemaRegistry([(SCHEMA_REF, schema)])
    assert (
        h.classify(page, checkpoint_allowed=True, cache_allowed=True).checkpoint_status == "STALE"
    )
    assert h.calls == 2


def test_cache_hit_and_identity_isolation(tmp_path):
    h = Harness(tmp_path)
    h.classify(cache_allowed=True)
    result = h.classify(cache_allowed=True)
    assert result.llm_result.cache_hit and result.llm_result.response.usage.total_tokens == 0
    assert h.calls == 1
    h.classify(loaded(source="synthetic-doc/run-B"), cache_allowed=True)
    h.classify(loaded(number=2), cache_allowed=True)
    assert h.calls == 3


@pytest.mark.parametrize("budget", [False, True])
def test_guard_quota_budget_denial(tmp_path, budget):
    h = Harness(tmp_path, budget=budget, rpm=1)
    if not budget:
        h.classify()
    result = h.classify(checkpoint_allowed=True)
    assert result.understanding.issues[0].code == "guard_denied"
    assert h.calls == (0 if budget else 1)
    assert not list(h.store.output_root.glob("*.json"))


def test_no_text_and_input_limit_skip_gateway(tmp_path):
    h = Harness(tmp_path)
    assert h.classify(loaded(texts=[])).understanding.issues[0].code == "insufficient_evidence"
    h.classifier = PageClassifier(h.service, config(max_input_characters=1))
    assert h.classify().understanding.issues[0].code == "input_limit"
    assert h.calls == 0


def test_wrong_source_rejected_before_llm(tmp_path):
    h = Harness(tmp_path)
    page = loaded()
    page.mapping_result.reference.anchor.page.source_ref = "wrong-run"
    with pytest.raises(ValueError, match="identity mismatch"):
        h.classify(page)
    assert h.calls == 0


def test_disabled_label_and_overlapping_evidence(tmp_path):
    h = Harness(tmp_path)
    restricted = config().model_copy(update={"enabled_labels": ("B02",)})
    h.classifier = PageClassifier(h.service, restricted)
    assert h.classify().understanding.issues[0].code == "disabled_label"
    h.classifier = PageClassifier(h.service, config())
    page = loaded()
    page.page.elements[1].bbox = page.page.elements[0].bbox.copy()
    assert h.classify(page).understanding.issues[0].code == "insufficient_evidence"


def test_ancillary_cannot_hide_conflict(tmp_path):
    h = Harness(tmp_path)
    first = h.classify()
    conflicting = h.classify(loaded(number=2, texts=["B01", TITLES["B01"], "B02", TITLES["B02"]]))
    pages = [first, conflicting]
    result = aggregate_document(
        pages,
        source_ref="synthetic-doc/run-A",
        expected_pages=manifest(pages),
        ancillary_pages=frozenset({2}),
    )
    assert result.status == "unresolved" and "unresolved_page" in result.issues


def manifest(pages):
    return [p.understanding.raw_page.model_copy(deep=True) for p in pages]


def test_document_multilabel_manifest_appendix_and_missing(tmp_path):
    h = Harness(tmp_path)
    first = h.classify()
    h.set_output(prediction("B02"))
    second = h.classify(loaded("B02", number=2))
    h.set_output(prediction(None, "insufficient", []))
    appendix = h.classify(loaded(number=3, texts=["Phụ lục"]))
    pages = [first, second, appendix]
    args = dict(source_ref="synthetic-doc/run-A", expected_pages=manifest(pages))
    assert aggregate_document(pages, **args).status == "unresolved"
    result = aggregate_document(pages, ancillary_pages=frozenset({3}), **args)
    assert result.status == "resolved" and result.labels == ("B01", "B02")
    assert len(result.anchors) == 4
    assert aggregate_document(pages[:2], **args).status == "unresolved"
    assert aggregate_document([first, first, second, appendix], **args).status == "unresolved"
    incomplete = manifest(pages)
    incomplete[0].image = "another-image.png"
    assert (
        aggregate_document(pages, source_ref=args["source_ref"], expected_pages=incomplete).status
        == "unresolved"
    )


def test_document_source_conflict_and_configuration(tmp_path):
    h = Harness(tmp_path)
    first = h.classify()
    other = h.classify(loaded(number=2, source="synthetic-doc/run-B"))
    with pytest.raises(ValueError, match="different document"):
        aggregate_document(
            [first, other], source_ref="synthetic-doc/run-A", expected_pages=manifest([first])
        )
    h.classifier = PageClassifier(h.service, config(max_output_tokens=1024))
    second = h.classify(loaded(number=2))
    result = aggregate_document(
        [first, second], source_ref="synthetic-doc/run-A", expected_pages=manifest([first, second])
    )
    assert result.issues == ("mixed_classification_configuration",)
    with pytest.raises(ValueError, match="one explicit"):
        aggregate_document(
            [],
            source_ref="synthetic-doc/run-A",
            expected_pages=[
                RawPageIdentity(symbol="SYNTHETIC", year="2025", page=1, image="p1.png")
            ],
        )
