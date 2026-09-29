"""Provider-neutral adapters and registry for Material supply sources."""

from .base import MaterialProvider, ProviderPage
from .errors import (
    ProviderAccessDeniedError,
    ProviderAuthError,
    ProviderContractError,
    ProviderDownloadUnavailableError,
    ProviderEdgeBlockedError,
    ProviderError,
    ProviderErrorCategory,
    ProviderFailure,
    ProviderInvalidResponseError,
    ProviderNetworkError,
    ProviderRateLimitError,
    ProviderRightsUnavailableError,
    ProviderTemporaryError,
    ProviderUnsupportedError,
    classify_http_error,
    error_from_failure,
)
from .models import (
    AccessMode,
    PaginationMode,
    ProviderCapability,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderInfo,
    ProviderContinuation,
)
from .registry import ProviderRegistry, ProviderSearchResult, RetryPolicy
from .local import LocalProvider
from .pexels import PexelsProvider
from .pixabay import PixabayProvider
from .coverr import CoverrProvider
from .unsplash import UnsplashProvider
from .openverse import OpenverseAudioProvider, OpenverseProvider
from .minimax_video import MiniMaxVideoAdapter, MiniMaxVideoError, MiniMaxVideoTask
from .minimax_image import MiniMaxImageAdapter, MiniMaxImageResult
from .minimax_speech import MiniMaxSpeechAdapter, MiniMaxSpeechResult

__all__ = [
    "AccessMode", "CoverrProvider", "LocalProvider", "MaterialProvider", "OpenverseAudioProvider", "OpenverseProvider", "PaginationMode", "PexelsProvider", "PixabayProvider", "ProviderAccessDeniedError", "ProviderAuthError", "ProviderContractError", "ProviderEdgeBlockedError",
    "ProviderCapability", "ProviderContinuation", "ProviderDownloadUnavailableError",
    "ProviderError", "ProviderErrorCategory", "ProviderFailure", "ProviderHealth",
    "ProviderHealthStatus", "ProviderInfo", "ProviderInvalidResponseError",
    "ProviderNetworkError", "ProviderPage", "ProviderRateLimitError",
    "ProviderRegistry", "ProviderRightsUnavailableError", "ProviderSearchResult",
    "ProviderTemporaryError", "ProviderUnsupportedError", "RetryPolicy", "UnsplashProvider",
    "classify_http_error", "error_from_failure", "MiniMaxVideoAdapter",
    "MiniMaxVideoError", "MiniMaxVideoTask", "MiniMaxImageAdapter", "MiniMaxImageResult",
    "MiniMaxSpeechAdapter", "MiniMaxSpeechResult",
]
