"""Factual provenance recording and conservative rights admission policy."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit

from easel.materials.domain import (
    MaterialAsset,
    MaterialNeed,
    NeedImportance,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    SemanticField,
)
from easel.materials.store import AttemptMaterialStore
from easel.materials.application.acquisition import RemoteURLPolicy


class RightsAdmissionStatus(str, Enum):
    ADMITTED = "ADMITTED"
    CONDITIONAL = "CONDITIONAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True)
class AttributionCondition:
    """A checkable credit requirement carried forward to Production/Export."""

    credit_text: str
    source_page: str
    destination: str


@dataclass(frozen=True)
class RightsAdmission:
    asset_id: str
    need_id: str
    status: RightsAdmissionStatus
    reason: str
    evidence_references: tuple[str, ...] = ()
    required_actions: tuple[str, ...] = ()

    @property
    def admitted(self) -> bool:
        return self.status is RightsAdmissionStatus.ADMITTED


class RightsService:
    """Persist factual rights/provenance evidence and evaluate Easel policy.

    This service records source evidence and makes a machine-readable workflow
    decision. It does not decide legal rights or infer a license from Provider.
    """

    _URL_RE = re.compile(r"https?://[^\s<>\]\[(){}\"']+", re.IGNORECASE)
    _SECRET_RE = re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|signature|sig)=([^\s&;,]+)"
    )

    def __init__(self, store: AttemptMaterialStore | None = None):
        self._store = store

    def record(
        self,
        asset: MaterialAsset,
        rights: RightsInfo,
        *,
        source_creator: str | None = None,
        source_page: str | None = None,
    ) -> MaterialAsset:
        """Write sanitized factual RightsInfo into the MaterialAsset sidecars."""
        if self._store is None:
            raise RuntimeError("RightsService.record requires an AttemptMaterialStore")
        source_updates = {}
        if source_creator is not None:
            source_updates["creator"] = self._sanitize_text(source_creator)
        if source_page is not None:
            try:
                parsed_source = urlsplit(source_page)
                if (parsed_source.scheme.lower() != "https" or not parsed_source.hostname
                        or parsed_source.username or parsed_source.password
                        or parsed_source.port not in (None, 443)):
                    raise ValueError
            except ValueError as exc:
                raise ValueError("Reviewed Material source page must be a public HTTPS URL") from exc
            source_updates["source_page"] = RemoteURLPolicy.redact(source_page)
        source = asset.source.model_copy(update=source_updates) if source_updates else asset.source
        clean_source = asset.source.model_copy(update={
            "creator": self._sanitize_text(source.creator),
            "source_page": RemoteURLPolicy.redact(source.source_page),
        })
        clean_evidence = tuple(
            evidence.model_copy(update={
                "reference": self._sanitize_text(evidence.reference),
                "summary": self._sanitize_text(evidence.summary),
            })
            for evidence in rights.evidence
        )
        clean_rights = rights.model_copy(update={
            "license_url": RemoteURLPolicy.redact(rights.license_url),
            "attribution_text": self._sanitize_text(rights.attribution_text),
            "usage_constraints": tuple(self._sanitize_text(value) or "" for value in rights.usage_constraints),
            "evidence": clean_evidence,
        })
        recorded = asset.model_copy(update={"source": clean_source, "rights": clean_rights})
        self._store.write_asset(recorded)
        return recorded

    def evaluate(
        self,
        asset: MaterialAsset,
        need: MaterialNeed,
        *,
        attribution: AttributionCondition | None = None,
    ) -> RightsAdmission:
        evidence_refs = tuple(self._sanitize_text(item.reference) or "" for item in asset.rights.evidence)
        status = asset.rights.status
        if status is RightsStatus.RESTRICTED:
            return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                  "rights_restricted", evidence_refs)
        if status is RightsStatus.UNKNOWN:
            if need.importance is NeedImportance.REQUIRED:
                return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                      "required_need_rights_unknown", evidence_refs)
            return self._decision(asset, need, RightsAdmissionStatus.REVIEW_REQUIRED,
                                  "optional_need_rights_unknown_review", evidence_refs)
        if not asset.rights.evidence:
            return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                  "rights_evidence_missing", evidence_refs)
        if not any(item.kind.casefold().startswith("asset_") for item in asset.rights.evidence):
            return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                  "asset_specific_rights_evidence_missing", evidence_refs)
        if status is RightsStatus.KNOWN and not asset.rights.license_name:
            return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                  "known_license_name_missing", evidence_refs)

        incompatible = self._incompatibility(asset, need)
        if incompatible:
            return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                  incompatible, evidence_refs)

        brand_restriction = "recognizable_trademark_noncommercial_restriction" in asset.rights.usage_constraints
        commercial = need.constraints.get("commercial_use") is True or need.constraints.get("usage") == "commercial"
        if brand_restriction and commercial:
            logo = self._annotation(asset, SemanticField.LOGO)
            if logo is None:
                return self._decision(asset, need, RightsAdmissionStatus.REVIEW_REQUIRED,
                                      "commercial_brand_clearance_unknown", evidence_refs,
                                      ("verify_recognizable_trademarks_are_absent_or_cleared",))
            if self._logo_present(logo.value):
                return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                      "commercial_use_of_recognizable_trademark_restricted", evidence_refs)

        attribution_required = (
            status is RightsStatus.ATTRIBUTION_REQUIRED
            or asset.rights.attribution_required
            or "attribution_required" in asset.rights.usage_constraints
        )
        if status is RightsStatus.ATTRIBUTION_REQUIRED and not asset.rights.attribution_required:
            return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                  "attribution_status_conflict", evidence_refs)
        if attribution_required:
            if not self._valid_attribution(asset, attribution):
                return self._decision(
                    asset, need, RightsAdmissionStatus.BLOCKED,
                    "attribution_condition_missing_or_unverifiable", evidence_refs,
                    ("provide_exact_creator_credit_and_source_page_for_export",),
                )
            return self._decision(
                asset, need, RightsAdmissionStatus.CONDITIONAL,
                "attribution_condition_must_be_enforced_by_production_export", evidence_refs,
                ("attach_attribution_to_export",),
            )

        if status not in {RightsStatus.PUBLIC_DOMAIN, RightsStatus.KNOWN}:
            return self._decision(asset, need, RightsAdmissionStatus.BLOCKED,
                                  "rights_status_not_admissible", evidence_refs)
        return self._decision(asset, need, RightsAdmissionStatus.ADMITTED,
                              "evidence_and_usage_constraints_compatible", evidence_refs)

    @staticmethod
    def attribution_condition_for(asset: MaterialAsset) -> AttributionCondition | None:
        """Build a condition only from the Asset's recorded attribution facts.

        This does not author or infer a credit. It succeeds only when the Asset
        already carries the exact credit, creator and source page to propagate.
        """
        if not (asset.rights.attribution_required
                or asset.rights.status is RightsStatus.ATTRIBUTION_REQUIRED
                or "attribution_required" in asset.rights.usage_constraints):
            return None
        if not asset.rights.attribution_text or not asset.source.creator or not asset.source.source_page:
            return None
        return AttributionCondition(
            credit_text=asset.rights.attribution_text,
            source_page=asset.source.source_page,
            destination="export_credits",
        )

    @staticmethod
    def _incompatibility(asset: MaterialAsset, need: MaterialNeed) -> str | None:
        restrictions = set(asset.rights.usage_constraints)
        constraints = need.constraints
        commercial = constraints.get("commercial_use") is True or constraints.get("usage") == "commercial"
        if commercial and restrictions & {"editorial_only", "commercial_use_unknown", "not_for_commercial_use"}:
            return "commercial_use_incompatible_or_unknown"
        if constraints.get("distribution_mode") == "stock_redistribution" and "no_redistribution_as_stock" in restrictions:
            return "stock_redistribution_prohibited"
        if (constraints.get("distribution_mode") == "trademark" or constraints.get("use_as_trademark") is True) and "no_trademark_use" in restrictions:
            return "trademark_use_prohibited"
        if constraints.get("endorsement") is True and "no_endorsement" in restrictions:
            return "endorsement_use_prohibited"
        return None

    @staticmethod
    def _annotation(asset: MaterialAsset, field: SemanticField):
        for inference in reversed(asset.semantic.inferences):
            for annotation in inference.annotations:
                if annotation.field is field:
                    return annotation
        return None

    @staticmethod
    def _logo_present(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, tuple):
            return bool(value)
        if isinstance(value, str):
            return value.strip().casefold() not in {"", "false", "no", "none", "absent"}
        return True

    def _valid_attribution(
        self, asset: MaterialAsset, condition: AttributionCondition | None
    ) -> bool:
        if condition is None or condition.destination != "export_credits":
            return False
        creator = asset.source.creator
        source_page = RemoteURLPolicy.redact(asset.source.source_page)
        credit = self._sanitize_text(condition.credit_text)
        expected = self._sanitize_text(asset.rights.attribution_text)
        if not creator or not source_page or not credit or not expected:
            return False
        return (
            condition.source_page == source_page
            and credit.casefold() == expected.casefold()
            and creator.casefold() in credit.casefold()
            and source_page in credit
        )

    def _decision(
        self,
        asset: MaterialAsset,
        need: MaterialNeed,
        status: RightsAdmissionStatus,
        reason: str,
        evidence_refs: tuple[str, ...],
        actions: tuple[str, ...] = (),
    ) -> RightsAdmission:
        return RightsAdmission(
            asset_id=asset.asset_id,
            need_id=need.need_id,
            status=status,
            reason=reason,
            evidence_references=evidence_refs,
            required_actions=actions,
        )

    def _sanitize_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        redacted = self._URL_RE.sub(lambda match: RemoteURLPolicy.redact(match.group(0)) or "[REDACTED_URL]", value)
        redacted = self._SECRET_RE.sub(r"\1=[REDACTED]", redacted)
        return redacted.strip()
