"""Explicit local selection of an approved release; never grants authority."""

import os
from pathlib import Path

from pydantic import Field

from ..accounting.contracts import FinancialModel
from ..core.data_config import DataConfigError, default_project_root
from .composition import EvidenceComposition, payload_sha256
from .document_corrections import check_correction_promotion, load_source_policy
from .document_repository import DocumentEvidenceRepository


def storage_root():
    configured = os.environ.get("DOCUMENT_RELEASE_ROOT", "artifacts/source-quality")
    path = Path(configured)
    return (path if path.is_absolute() else default_project_root() / path).resolve()


def storage_path(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("release_storage_mismatch")
    return path


class ActiveRelease(FinancialModel):
    document_id: str
    composition_id: str
    composition_sha256: str
    release_sha256: str
    policy_sha256: str
    composition: str
    repository: str
    pdf: str
    saved_page: str


class ReleaseSelections(FinancialModel):
    version: str = "document_release_selection_v1"
    active: list[ActiveRelease] = Field(default_factory=list)


class SelectedRepositories:
    def __init__(self, original, selected):
        self.original, self.selected = original, selected

    def list_by_document(self, document_id):
        repository = self.selected.get(document_id, self.original)
        return repository.list_by_document(document_id)


def select_active_releases(manifests, repository):
    """Startup preflight; invalid configured selection raises, with no fallback."""
    if not manifests:
        return tuple(manifests), repository
    try:
        root = storage_root()
    except DataConfigError:
        if "DOCUMENT_RELEASE_ROOT" not in os.environ:
            return tuple(manifests), repository
        raise
    path = storage_path(root, "active-releases.json")
    if not path.exists() and "DOCUMENT_RELEASE_ROOT" not in os.environ:
        return tuple(manifests), repository
    selections = ReleaseSelections.model_validate_json(path.read_bytes())
    if selections.version != "document_release_selection_v1":
        raise ValueError("release_selection_version")
    ids = [s.document_id for s in selections.active]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_active_document")
    selected, replacements = {}, {}
    for selection in selections.active:
        # Validate every configured entry, including documents outside this request.
        policy = load_source_policy()
        if payload_sha256(policy.model_dump(mode="json")) != selection.policy_sha256:
            raise ValueError("activation_policy_mismatch")
        releases = [r for r in policy.releases if r.digest == selection.release_sha256]
        if len(releases) != 1:
            raise ValueError("activation_release_missing")
        manifest = EvidenceComposition.model_validate_json(
            storage_path(root, selection.composition).read_bytes()
        )
        if (
            manifest.logical_document_id,
            manifest.composition_id,
            payload_sha256(manifest.model_dump(mode="json")),
        ) != (selection.document_id, selection.composition_id, selection.composition_sha256):
            raise ValueError("activation_composition_mismatch")
        repo_path = storage_path(root, selection.repository)
        if not (repo_path / "document-evidence.json").is_file():
            raise ValueError("activation_repository_missing")
        selected_repository = DocumentEvidenceRepository(repo_path)
        import json

        check = check_correction_promotion(
            releases[0],
            manifest,
            selected_repository,
            storage_path(root, selection.pdf),
            json.loads(storage_path(root, selection.saved_page).read_bytes()),
            expected_release_sha256=selection.release_sha256,
        )
        if check.status != "ready":
            raise ValueError("activation_preflight_blocked:" + ",".join(check.reasons))
        # Sources may have separate document IDs; route every pinned descriptor.
        for source in manifest.sources:
            if source.status == "verified":
                selected[source.descriptor.document_id] = selected_repository
        replacements[selection.document_id] = manifest
    return (
        tuple(replacements.get(m.logical_document_id, m) for m in manifests),
        SelectedRepositories(repository, selected) if selected else repository,
    )
