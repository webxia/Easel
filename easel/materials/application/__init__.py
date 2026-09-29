"""Material supply application services."""

from .audio_supply import AudioSupplySearch, BgmMaterialSupply, SfxEventMaterialSupply
from .generation import (
    GeneratedMaterialResult,
    GenerationApprovalRequired,
    GenerationRequestConflict,
    MiniMaxVideoMaterialGeneration,
)
from .generation_modalities import MiniMaxImageSpeechGeneration
from .advanced_matching import (
    AdvancedMaterialMatcher,
    AdvancedMaterialMatch,
    AdvancedMatchEvidence,
    AdvancedMatchRejection,
    AdvancedMatchingResult,
    DirectorPreference,
    EvidenceKind,
    MatchEvidence,
)
from .library_reuse import (
    LibraryReuseCandidate,
    LibraryReuseRejection,
    LibraryReuseSearchResult,
    LibraryReuseService,
)
from .library_first import (
    ExternalSupplyFailure,
    LibraryFirstNeedResult,
    LibraryFirstSupplyService,
    SupplementalAttemptBudget,
)
from .routing import (
    MaterialSourceRouter,
    ProviderPerformance,
    ProviderRoutingPolicy,
    RouteSkip,
    RoutedSearchResult,
    RoutingDecision,
    SourceKind,
    SourceRoute,
)

__all__ = [
    "AudioSupplySearch",
    "BgmMaterialSupply",
    "GeneratedMaterialResult",
    "GenerationApprovalRequired",
    "GenerationRequestConflict",
    "MiniMaxVideoMaterialGeneration",
    "MiniMaxImageSpeechGeneration",
    "AdvancedMaterialMatcher",
    "AdvancedMaterialMatch",
    "AdvancedMatchEvidence",
    "AdvancedMatchRejection",
    "AdvancedMatchingResult",
    "DirectorPreference",
    "EvidenceKind",
    "MatchEvidence",
    "MaterialSourceRouter",
    "ProviderPerformance",
    "ProviderRoutingPolicy",
    "RouteSkip",
    "RoutedSearchResult",
    "RoutingDecision",
    "SourceKind",
    "SourceRoute",
    "LibraryReuseCandidate",
    "LibraryReuseRejection",
    "LibraryReuseSearchResult",
    "LibraryReuseService",
    "ExternalSupplyFailure",
    "LibraryFirstNeedResult",
    "LibraryFirstSupplyService",
    "SupplementalAttemptBudget",
    "SfxEventMaterialSupply",
]
