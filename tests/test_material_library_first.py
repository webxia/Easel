from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from types import SimpleNamespace

import pytest

from easel.materials.application.library_first import (
    LibraryFirstSupplyService,
    SupplementalAttemptBudget,
)
from easel.materials.application.matching import MaterialMatcher
from easel.materials.application.supplemental import SupplementalSupplyFoundation
from easel.materials.domain import (
    CandidateSource, FileInfo, MaterialAsset, MaterialNeed, MediaType,
    NeedImportance, NeedIntent, NeedScope, NeedScopeType, RightsEvidence,
    RightsInfo, RightsStatus, TechnicalInfo, TechnicalStatus,
)
from easel.materials.providers.models import (
    AccessMode, ProviderCapability, ProviderInfo,
)


def _need(*, desired_options: int = 1) -> MaterialNeed:
    return MaterialNeed(
        need_id="need-one", scope=NeedScope(type=NeedScopeType.SCENE, ref="scene-one"),
        media_type=MediaType.IMAGE, role="visual", intent=NeedIntent(description="city portrait"),
        importance=NeedImportance.REQUIRED, desired_options=desired_options,
    )


def _asset(asset_id: str) -> MaterialAsset:
    body = asset_id.encode()
    return MaterialAsset(
        asset_id=asset_id, media_type=MediaType.IMAGE,
        file=FileInfo(path=f"materials/assets/{asset_id}/original.jpg", sha256=hashlib.sha256(body).hexdigest(), size=len(body), mime="image/jpeg"),
        source=CandidateSource(kind="fixture", provider="fixture", provider_asset_id=asset_id),
        rights=RightsInfo(status=RightsStatus.KNOWN, license_name="Fixture", evidence=(RightsEvidence(kind="asset_license", reference=f"fixture:{asset_id}"),)),
        technical=TechnicalInfo(status=TechnicalStatus.PASSED, width=1080, height=1920, mime="image/jpeg"),
    )


class _Reuse:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = 0

    def find_candidates(self, *args, **kwargs):
        self.calls += 1
        return SimpleNamespace(candidates=self.candidates)


class _Advanced:
    def __init__(self, matches):
        self.matches = matches

    def match(self, *args, **kwargs):
        return SimpleNamespace(matches=self.matches)


def _candidate(asset: MaterialAsset):
    return SimpleNamespace(asset=asset, library_asset_id=f"library-{asset.asset_id}")


def _source(provider_id: str, access_mode: AccessMode) -> ProviderInfo:
    return ProviderInfo(
        provider_id=provider_id, display_name=provider_id, media_types=(MediaType.IMAGE,),
        access_mode=access_mode,
        capabilities=(ProviderCapability.SEARCH,)
        + (() if access_mode is AccessMode.DISCOVERY_ONLY else (ProviderCapability.DIRECT_DOWNLOAD,)),
    )


def test_library_qualified_options_precede_and_can_avoid_external_supply() -> None:
    candidate = _candidate(_asset("library-asset"))
    reuse = _Reuse((candidate,))
    calls = []
    service = LibraryFirstSupplyService(reuse, _Advanced((SimpleNamespace(),)))
    result = service.supply_need(
        _need(), scope=object(), creation_id="creation", attempt_id="attempt",
        provider_infos=(_source("remote", AccessMode.PUBLIC_API),),
        external_supply=lambda source, need: calls.append(source) or (_asset("remote-asset"),),
    )
    assert reuse.calls == 1
    assert calls == []
    assert result.qualified_option_count == 1
    assert result.attempted_sources == ()
    assert result.selection_authority is False


def test_short_library_uses_bounded_fallback_and_isolates_source_failure() -> None:
    reuse = _Reuse(())
    service = LibraryFirstSupplyService(reuse, _Advanced(()), matcher=MaterialMatcher())
    attempted = []

    def supply(source, need):
        attempted.append(source)
        if source == "bad":
            raise RuntimeError("fixture provider failure")
        return (_asset("remote-asset"),)

    sources = (_source("bad", AccessMode.PUBLIC_API), _source("good", AccessMode.PUBLIC_API))
    result = service.supply_need(
        _need(), scope=object(), creation_id="creation", attempt_id="attempt",
        provider_infos=sources, external_supply=supply,
    )
    assert attempted == ["bad", "good"]
    assert result.attempted_sources == ("bad", "good")
    assert [item.source_id for item in result.failures] == ["bad"]
    assert [item.asset_id for item in result.external_assets] == ["remote-asset"]
    assert len(result.external_matches) == 1


def test_discovery_only_providers_are_not_routed_for_acquisition() -> None:
    reuse = _Reuse(())
    service = LibraryFirstSupplyService(reuse, _Advanced(()))
    result = service.supply_need(
        _need(), scope=object(), creation_id="creation", attempt_id="attempt",
        provider_infos=(_source("discovery", AccessMode.DISCOVERY_ONLY),),
        external_supply=lambda source, need: (_asset("unexpected"),),
    )
    assert result.routing.routes == ()
    assert result.routing.skipped[0].source_id == "discovery"
    assert result.attempted_sources == ()


def test_supplemental_attempt_budget_enforces_explicit_ceiling() -> None:
    budget = SupplementalAttemptBudget(max_attempts=1)
    assert budget.consume() == 1
    with pytest.raises(RuntimeError, match="ceiling"):
        budget.consume()
    with pytest.raises(ValueError, match="invalid"):
        SupplementalAttemptBudget(max_attempts=0, attempts=1)
