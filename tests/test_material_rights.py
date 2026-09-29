from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from easel.materials.application.rights import (
    AttributionCondition,
    RightsAdmissionStatus,
    RightsService,
)
from easel.materials.domain import (
    CandidateSource,
    FileInfo,
    MaterialAsset,
    MaterialNeed,
    MediaType,
    NeedImportance,
    NeedIntent,
    NeedScope,
    NeedScopeType,
    RightsEvidence,
    RightsInfo,
    RightsStatus,
    IntelligenceStatus,
    SemanticAnnotation,
    SemanticField,
    SemanticInference,
    TechnicalInfo,
)
from easel.materials.store import AttemptMaterialStore


def asset(rights: RightsInfo, *, provider: str = "pexels") -> MaterialAsset:
    return MaterialAsset(
        asset_id="asset-rights-test",
        media_type=MediaType.VIDEO,
        file=FileInfo(path="materials/assets/asset-rights-test/original.mp4", sha256="a" * 64, size=1, mime="video/mp4"),
        source=CandidateSource(
            kind="stock", provider=provider, provider_asset_id="42",
            source_page="https://www.pexels.com/video/42/", creator="A Creator",
        ),
        rights=rights,
        technical=TechnicalInfo(),
    )


def need(*, importance: NeedImportance = NeedImportance.REQUIRED, **constraints) -> MaterialNeed:
    return MaterialNeed(
        need_id="need-rights-test",
        scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-1"),
        media_type=MediaType.VIDEO,
        role="broll",
        intent=NeedIntent(description="city video"),
        constraints=constraints,
        importance=importance,
    )


def evidence(reference="https://example.test/license") -> tuple[RightsEvidence, ...]:
    return (RightsEvidence(
        kind="asset_license_statement",
        reference=reference,
        observed_at=datetime(2026, 9, 22, tzinfo=timezone.utc),
        summary="Observed source statement",
    ),)


def test_provider_identity_and_acquisition_do_not_upgrade_unknown_rights() -> None:
    value = asset(RightsInfo(status=RightsStatus.UNKNOWN))
    decision = RightsService().evaluate(value, need())
    assert decision.status is RightsAdmissionStatus.BLOCKED
    assert decision.reason == "required_need_rights_unknown"
    assert not decision.admitted


def test_unknown_is_review_required_for_optional_need_but_never_auto_admitted() -> None:
    value = asset(RightsInfo(status=RightsStatus.UNKNOWN))
    service = RightsService()
    result = service.evaluate(value, need(importance=NeedImportance.OPTIONAL))
    assert result.status is RightsAdmissionStatus.REVIEW_REQUIRED
    assert not result.admitted


def test_restricted_is_blocked_and_public_domain_requires_asset_evidence() -> None:
    service = RightsService()
    restricted = service.evaluate(asset(RightsInfo(status=RightsStatus.RESTRICTED)), need())
    unsupported_claim = service.evaluate(asset(RightsInfo(status=RightsStatus.PUBLIC_DOMAIN)), need())
    evidenced = service.evaluate(asset(RightsInfo(status=RightsStatus.PUBLIC_DOMAIN, evidence=evidence())), need())
    assert restricted.status is RightsAdmissionStatus.BLOCKED
    assert unsupported_claim.reason == "rights_evidence_missing"
    assert evidenced.status is RightsAdmissionStatus.ADMITTED


def test_known_rights_require_license_evidence_and_usage_compatibility() -> None:
    service = RightsService()
    no_evidence = service.evaluate(asset(RightsInfo(status=RightsStatus.KNOWN, license_name="License")), need())
    allowed = service.evaluate(
        asset(RightsInfo(status=RightsStatus.KNOWN, license_name="CC BY 4.0", evidence=evidence())), need()
    )
    restricted_use = service.evaluate(
        asset(RightsInfo(
            status=RightsStatus.KNOWN, license_name="Editorial license",
            usage_constraints=("editorial_only",), evidence=evidence(),
        )), need(commercial_use=True)
    )
    assert no_evidence.status is RightsAdmissionStatus.BLOCKED
    assert allowed.status is RightsAdmissionStatus.ADMITTED
    assert restricted_use.reason == "commercial_use_incompatible_or_unknown"

    provider_policy_only = service.evaluate(
        asset(RightsInfo(
            status=RightsStatus.KNOWN,
            license_name="Pexels License",
            evidence=(RightsEvidence(kind="provider_terms", reference="https://www.pexels.com/license/"),),
        )), need()
    )
    assert provider_policy_only.reason == "asset_specific_rights_evidence_missing"


@pytest.mark.parametrize(
    ("logo_value", "expected"),
    [
        (None, RightsAdmissionStatus.REVIEW_REQUIRED),
        (True, RightsAdmissionStatus.BLOCKED),
        (False, RightsAdmissionStatus.ADMITTED),
    ],
)
def test_pixabay_commercial_brand_restriction_requires_evidence_of_absence(logo_value, expected) -> None:
    value = asset(RightsInfo(
        status=RightsStatus.KNOWN,
        license_name="Pixabay Content License",
        usage_constraints=("recognizable_trademark_noncommercial_restriction",),
        evidence=evidence(),
    ), provider="pixabay")
    if logo_value is not None:
        inference = SemanticInference(
            analyzer_id="fixture-visual-audit",
            status=IntelligenceStatus.COMPLETE,
            annotations=(SemanticAnnotation(field=SemanticField.LOGO, value=logo_value),),
        )
        semantic = value.semantic.model_copy(update={"inferences": (inference,)})
        value = value.model_copy(update={"semantic": semantic})

    result = RightsService().evaluate(value, need(commercial_use=True))

    assert result.status is expected


def test_attribution_requires_mechanically_matching_credit_condition() -> None:
    service = RightsService()
    source_page = "https://www.pexels.com/video/42/"
    credit = "A Creator — Pexels, https://www.pexels.com/video/42/"
    value = asset(RightsInfo(
        status=RightsStatus.ATTRIBUTION_REQUIRED,
        license_name="Attribution license",
        license_url="https://example.test/license",
        attribution_required=True,
        attribution_text=credit,
        evidence=evidence(),
    ))
    missing = service.evaluate(value, need())
    mismatched = service.evaluate(value, need(), attribution=AttributionCondition(
        credit_text="A Creator — Pexels", source_page=source_page, destination="export_credits"
    ))
    complete = service.evaluate(value, need(), attribution=AttributionCondition(
        credit_text=credit, source_page=source_page, destination="export_credits"
    ))
    assert missing.status is RightsAdmissionStatus.BLOCKED
    assert mismatched.status is RightsAdmissionStatus.BLOCKED
    assert complete.status is RightsAdmissionStatus.CONDITIONAL
    assert complete.required_actions == ("attach_attribution_to_export",)
    assert not complete.admitted  # Material Layer cannot assert Production/Export fulfilled it.


def test_rights_and_source_sidecar_redact_secret_urls_without_reclassifying_provider(tmp_path) -> None:
    store = AttemptMaterialStore(tmp_path)
    asset_id = "asset-rights-test"
    path = store.write_asset_bytes(asset_id, "original.mp4", b"x")
    value = asset(RightsInfo(status=RightsStatus.UNKNOWN)).model_copy(update={
        "file": FileInfo(path=path, sha256="a" * 64, size=1, mime="video/mp4"),
        "source": CandidateSource(
            kind="stock", provider="pexels", provider_asset_id="42",
            source_page="https://www.pexels.com/video/42/?token=source-secret", creator="A Creator",
        ),
    })
    supplied_rights = RightsInfo(
        status=RightsStatus.UNKNOWN,
        license_url="https://example.test/license?access_token=license-secret",
        evidence=(RightsEvidence(
            kind="provider_terms", reference="https://example.test/terms?api_key=terms-secret",
            summary="Read https://example.test/page?signature=summary-secret",
        ),),
    )

    recorded = RightsService(store).record(
        value, supplied_rights, source_creator="Reviewed Creator",
        source_page="https://example.test/material?access_token=source-review-secret",
    )

    assert recorded.rights.status is RightsStatus.UNKNOWN
    assert recorded.rights.license_url == "https://example.test/license?[REDACTED]"
    assert recorded.rights.evidence[0].reference == "https://example.test/terms?[REDACTED]"
    assert recorded.source.creator == "Reviewed Creator"
    assert recorded.source.source_page == "https://example.test/material?[REDACTED]"
    assert "source-secret" not in recorded.source.source_page
    sidecar = (tmp_path / "materials" / "assets" / asset_id / "source.json").read_text()
    assert "license-secret" not in sidecar
    assert "terms-secret" not in sidecar
    assert "summary-secret" not in sidecar
    payload = json.loads(sidecar)
    assert payload["source"]["provider"] == "pexels"
    assert payload["rights"]["status"] == "UNKNOWN"
    with pytest.raises(ValueError, match="public HTTPS"):
        RightsService(store).record(
            recorded, supplied_rights, source_page="javascript:alert(1)",
        )
