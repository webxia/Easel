"""Role-specific BGM/SFX discovery over existing Material supply contracts."""

from __future__ import annotations

from dataclasses import dataclass

from easel.materials.application.compiler import NeedCompiler
from easel.materials.application.matching import MaterialMatcher, MaterialMatchingResult
from easel.materials.domain import MaterialAsset, MaterialNeed, MediaType, RetrievalIntent
from easel.materials.providers.registry import ProviderRegistry, ProviderSearchResult


@dataclass(frozen=True)
class AudioSupplySearch:
    intent: RetrievalIntent
    providers: tuple[ProviderSearchResult, ...]


class _AudioRoleSupply:
    roles: frozenset[str] = frozenset()
    label = "audio"

    def __init__(self, compiler: NeedCompiler | None = None, matcher: MaterialMatcher | None = None) -> None:
        self._compiler = compiler or NeedCompiler()
        self._matcher = matcher or MaterialMatcher()

    def discover(
        self,
        need: MaterialNeed,
        registry: ProviderRegistry,
        *,
        continuations=None,
    ) -> AudioSupplySearch:
        self._validate_need(need)
        intent = self._compiler.compile(need)
        return AudioSupplySearch(intent, registry.search_all(intent, continuations=continuations))

    def match(self, need: MaterialNeed, assets: tuple[MaterialAsset, ...] | list[MaterialAsset]) -> MaterialMatchingResult:
        self._validate_need(need)
        if any(asset.media_type is not MediaType.AUDIO for asset in assets):
            raise ValueError(f"{self.label} matching accepts audio assets only")
        return self._matcher.match(need, assets)

    def _validate_need(self, need: MaterialNeed) -> None:
        if need.media_type is not MediaType.AUDIO:
            raise ValueError(f"{self.label} supply requires an audio MaterialNeed")
        role = need.role.casefold().replace("-", "_").strip()
        if role not in self.roles:
            raise ValueError(f"Need role {need.role!r} is not a {self.label} role")


class BgmMaterialSupply(_AudioRoleSupply):
    """Find and match background-music candidates, without playback decisions."""

    label = "BGM"
    roles = frozenset({"bgm", "music", "background_music", "background_audio"})


class SfxEventMaterialSupply(_AudioRoleSupply):
    """Find event-semantic effects; event timing remains production-owned."""

    label = "SFX"
    roles = frozenset({"sfx", "sound_effect", "event_sfx", "sfx_event"})


__all__ = ["AudioSupplySearch", "BgmMaterialSupply", "SfxEventMaterialSupply"]
