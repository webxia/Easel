"""Material supply domain, application, and persistence modules."""

from .library import (
    LibraryScope,
    MaterialLibraryCatalog,
    MaterialLibraryError,
    MaterialLibraryRecord,
    MaterialLibraryUsage,
    PromotionConsent,
    PromotionRejected,
)
from .semantic_index import (
    EmbeddingContract,
    EmbeddingProvider,
    MaterialSemanticIndex,
    SearchMode,
    SemanticIndexError,
    SemanticSearchHit,
    SemanticSearchResult,
)

__all__ = [
    "LibraryScope",
    "MaterialLibraryCatalog",
    "MaterialLibraryError",
    "MaterialLibraryRecord",
    "MaterialLibraryUsage",
    "PromotionConsent",
    "PromotionRejected",
    "EmbeddingContract",
    "EmbeddingProvider",
    "MaterialSemanticIndex",
    "SearchMode",
    "SemanticIndexError",
    "SemanticSearchHit",
    "SemanticSearchResult",
]
