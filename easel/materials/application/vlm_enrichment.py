"""Optional Library VLM enrichment that writes only typed AI inference data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from pydantic import ValidationError

from easel.materials.application.intelligence import SemanticAnalysisOutput
from easel.materials.domain import (
    IntelligenceStatus,
    MediaType,
    SemanticInference,
)
from easel.materials.library import (
    LibraryScope,
    MaterialLibraryCatalog,
    MaterialLibraryError,
    MaterialLibraryRecord,
)


class LibraryVLMAnalyzer(Protocol):
    """Replaceable analyzer interface; implementations may be local or remote."""

    analyzer_id: str
    model_version: str

    def analyze(self, path: Path, media_type: MediaType) -> SemanticAnalysisOutput | dict[str, object]: ...


@dataclass(frozen=True)
class VLMEnrichmentResult:
    record: MaterialLibraryRecord
    status: IntelligenceStatus
    error_code: str | None = None


class LibraryVLMEnricher:
    """Enrich a Library asset while keeping facts, inference, and scores apart."""

    def __init__(
        self,
        catalog: MaterialLibraryCatalog,
        analyzer: LibraryVLMAnalyzer | None = None,
        *,
        enabled: bool = False,
    ):
        self.catalog = catalog
        self.analyzer = analyzer
        self.enabled = enabled

    def enrich(self, record: MaterialLibraryRecord, *, scope: LibraryScope) -> VLMEnrichmentResult:
        current = self.catalog.get(record.library_asset_id, scope=scope)
        if current != record:
            raise MaterialLibraryError("VLM input does not match the current scoped Library record")
        if not self.enabled or self.analyzer is None:
            return VLMEnrichmentResult(record, IntelligenceStatus.DISABLED, "analyzer_disabled")
        analyzer_id = self.analyzer.analyzer_id.strip()
        model_version = self.analyzer.model_version.strip()
        if not analyzer_id or not model_version:
            return VLMEnrichmentResult(record, IntelligenceStatus.FAILED, "analyzer_identity_invalid")
        try:
            path = self.catalog.resolve_physical_locator(record)
            output = SemanticAnalysisOutput.validate_output(
                self.analyzer.analyze(path, record.asset.media_type)
            )
            status = IntelligenceStatus.PARTIAL if output.partial else IntelligenceStatus.COMPLETE
            inference = SemanticInference(
                analyzer_id=analyzer_id,
                model_version=model_version,
                status=status,
                annotations=output.annotations,
                observed_at=datetime.now(timezone.utc),
            )
            retained = tuple(
                item for item in record.asset.semantic.inferences if item.analyzer_id != analyzer_id
            )
            updated = self.catalog.update_semantic_inferences(
                record.library_asset_id,
                scope=scope,
                inferences=retained + (inference,),
                intelligence_status=status,
            )
            return VLMEnrichmentResult(updated, status)
        except Exception as exc:
            code = "analyzer_output_invalid" if isinstance(exc, ValidationError) else (
                "asset_unavailable_for_analysis" if isinstance(exc, OSError) else "analyzer_failed"
            )
            # Failed enrichment does not mutate the existing facts or inference corpus.
            return VLMEnrichmentResult(record, IntelligenceStatus.FAILED, code)


__all__ = ["LibraryVLMAnalyzer", "LibraryVLMEnricher", "VLMEnrichmentResult"]
