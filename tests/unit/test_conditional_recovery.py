"""REC-01 fixture controls; synthetic approval is never production authority."""

import hashlib
import json
from types import SimpleNamespace

import pytest
from vietnamese_financial_multi_agent.core.gemini_adapter import _base
from vietnamese_financial_multi_agent.core.llm_contracts import LLMResponse, parse_json_output
from vietnamese_financial_multi_agent.core.llm_gateway import SharedLLMGateway
from vietnamese_financial_multi_agent.document_processing.vision_ocr import (
    VerifiedPageImage,
    image_source,
)
from vietnamese_financial_multi_agent.evidence.composition import PageBinding, payload_sha256
from vietnamese_financial_multi_agent.evidence.conditional_recovery import (
    recover_histories,
    recover_record,
    recovery_reason,
)
from vietnamese_financial_multi_agent.evidence.document_corrections import (
    DocumentSourcePolicy,
    save_source_policy,
)
from vietnamese_financial_multi_agent.evidence.release_activation import select_active_releases

from .test_document_corrections import approve_fixture
from .test_document_corrections import correction_case as correction_case


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_clean_and_missing_do_not_initialize_recovery(monkeypatch):
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.evidence.conditional_recovery.storage_root",
        lambda: pytest.fail("clean path loaded storage"),
    )
    assert recover_histories([], None, None, seen=set()) == []
    clean = SimpleNamespace(final=SimpleNamespace(checks={"content_fidelity": False}))
    assert recover_histories([clean], None, None, seen=set()) == []


def test_short_deadline_is_blocked_before_image_or_network(correction_case, tmp_path, monkeypatch):
    _, manifest, original, _, _, _, _, _, _, _, policy, _ = correction_case
    save_source_policy(policy)
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.document_processing.gemini_ingestion.load_pages",
        lambda *a, **kw: pytest.fail("invalid deadline rendered an image"),
    )
    result = recover_record(
        original, manifest, {}, root=tmp_path, gateway=None, seen=set(), timeout=8
    )
    assert result["status"] == "blocked"
    assert result["calls"] == 0
    assert result["error_code"] == "recovery_timeout_below_provider_minimum"


@pytest.mark.parametrize(
    "mode",
    [
        "clean",
        "proposal",
        "ambiguous",
        "unchanged",
        "timeout",
        "schema_echo",
        "wrong_page",
        "wrong_selector",
        "wrong_image",
        "wrong_composition",
        "repeat",
    ],
)
def test_bounded_transcription_proposals(correction_case, tmp_path, monkeypatch, mode):
    _, manifest, original, clean, _, _, _, _, _, _, policy, _ = correction_case
    save_source_policy(policy)
    if mode == "clean":
        assert recovery_reason(clean, policy) is None
        assert recover_record(clean, manifest, {}, root=tmp_path, gateway=None, seen=set()) == {
            "status": "ineligible",
            "calls": 0,
        }
        return
    # Fixture image input; actual PDF binding is exercised separately by REC-01 real runs.
    content = b"\x89PNG\r\n\x1a\nunit-only"
    digest = hashlib.sha256(content).hexdigest()
    original.sources[0].reference.anchor.page.image = "sha256:" + digest
    key = payload_sha256(original.model_dump(mode="json"))
    for pin in manifest.sources[0].evidence:
        if pin.identity == original.evidence_identity():
            pin.payload_sha256 = key
    identity = original.sources[0].reference.anchor.page
    image = VerifiedPageImage(identity, digest, 10, 10, content)
    saved = {"source": image_source(image), "provenance": {"render_dpi": 200}}
    write(tmp_path / "page.json", saved)
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.document_processing.gemini_ingestion.load_pages",
        lambda *a, **kw: [SimpleNamespace(image=image, source=saved["provenance"])],
    )
    binding = dict(
        composition_sha256=payload_sha256(manifest.model_dump(mode="json")),
        saved_page="page.json",
        pdf="fixture.pdf",
        selector=original.sources[0].reference.source_pointer,
    )
    if mode == "wrong_page":
        saved["source"]["page"]["page"] += 1
        write(tmp_path / "page.json", saved)
    if mode == "wrong_selector":
        binding["selector"] = "/wrong"
    if mode == "wrong_image":
        saved["source"]["image_sha256"] = "wrong"
        write(tmp_path / "page.json", saved)
    if mode == "wrong_composition":
        binding["composition_sha256"] = "wrong"
    calls = []

    def transport(request):
        calls.append(request)
        assert request.constraints.timeout_seconds == 10
        assert len(request.messages[0].images) == 1
        prompt = request.messages[0].content
        instructions, locator_json = prompt.split("\n", 1)
        assert "Read the image first" in instructions
        assert "not a sample answer" in instructions
        assert "do not copy current_text or merge adjacent paragraphs" in instructions
        assert "exactly five fields and no other fields" in instructions
        for field in ("text", "readability", "ambiguous_spans", "page", "selector"):
            assert field in instructions
        assert "additionalProperties" not in instructions
        assert "$defs" not in instructions and '"properties"' not in instructions
        assert json.loads(locator_json) == {
            "page": identity.page,
            "selector": binding["selector"],
            "current_text": original.raw_text,
        }
        if mode == "timeout":
            raise TimeoutError()
        value = dict(
            text=original.raw_text if mode == "unchanged" else "New transcription",
            readability="uncertain" if mode == "ambiguous" else "readable",
            ambiguous_spans=["word"] if mode == "ambiguous" else [],
            page=identity.page,
            selector=binding["selector"],
        )
        if mode == "schema_echo":
            value["additionalProperties"] = False
        return LLMResponse(
            **_base(request),
            status="success",
            finish_reason="stop",
            output=parse_json_output(json.dumps(value)),
        )

    gateway = SharedLLMGateway({"gemini": transport})
    seen = set()
    result = recover_record(original, manifest, binding, root=tmp_path, gateway=gateway, seen=seen)
    expected = {
        "ambiguous": "pending_review",
        "unchanged": "unchanged",
        "timeout": "failed",
        "schema_echo": "failed",
    }.get(mode, "blocked" if mode.startswith("wrong_") else "proposal_pending_review")
    assert result["status"] == expected
    assert len(calls) == (0 if mode.startswith("wrong_") else 1)
    if calls:
        assert result["call_latency_ms"] >= 0
    if mode == "schema_echo":
        assert result["error_code"] == "recovery_output_schema_invalid"
        assert "transcription" not in result
    assert not any(k in result for k in ("review_provenance", "approval", "release"))
    assert len(list((tmp_path / "recovery-candidates").glob("*.json"))) == 1
    if mode == "repeat":
        assert (
            recover_record(original, manifest, binding, root=tmp_path, gateway=gateway, seen=seen)[
                "status"
            ]
            == "budget_exhausted"
        )
        assert len(calls) == 1


@pytest.mark.parametrize(
    "mode", ["approved", "wrong_digest", "unapproved", "policy_changed", "missing", "escape"]
)
def test_persistent_exact_release_selection(correction_case, tmp_path, monkeypatch, mode):
    service, original, _, _, _, _, correction, _, manifest, release, policy, repository = (
        correction_case
    )
    approve_fixture(policy, release)
    root = tmp_path / "activation"
    write(root / "composition.json", manifest.model_dump(mode="json"))
    write(root / "page.json", {})
    # Copy fixture repository into configured activation storage.
    import shutil

    shutil.copytree(repository.root, root / "repository")
    selection = dict(
        document_id=manifest.logical_document_id,
        composition_id=manifest.composition_id,
        composition_sha256=release.composition_sha256,
        release_sha256=release.digest,
        policy_sha256=payload_sha256(policy.model_dump(mode="json")),
        composition="composition.json",
        repository="repository",
        pdf="fixture.pdf",
        saved_page="page.json",
    )
    if mode == "wrong_digest":
        selection["composition_sha256"] = "wrong"
    if mode == "unapproved":
        policy.approvals = []
        save_source_policy(policy)
        selection["policy_sha256"] = payload_sha256(policy.model_dump(mode="json"))
    if mode == "policy_changed":
        selection["policy_sha256"] = "wrong"
    if mode == "escape":
        selection["composition"] = "../outside.json"
    write(root / "active-releases.json", dict(active=[selection]))
    monkeypatch.setenv("DOCUMENT_RELEASE_ROOT", str(root))
    monkeypatch.setattr(
        "vietnamese_financial_multi_agent.evidence.document_corrections.verify_saved_pages",
        lambda *_: [
            PageBinding(
                page=correction.page,
                image_sha256=correction.source_image_digest,
                source_ref=correction.pdf_source_reference,
            )
        ],
    )
    if mode == "missing":
        (root / "active-releases.json").unlink()
    if mode != "approved":
        with pytest.raises((ValueError, OSError)):
            select_active_releases([original], service.document_repository)
    else:
        first, _ = select_active_releases([original], service.document_repository)
        monkeypatch.chdir(tmp_path)
        second, _ = select_active_releases([original], service.document_repository)
        assert first == second == (manifest,)
        assert (
            recovery_reason(
                repository.list_by_document(correction.original.document_id)[0],
                DocumentSourcePolicy(),
            )
            is None
        )
