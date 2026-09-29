from __future__ import annotations

import json

import pytest

from easel.materials.providers import (
    ProviderAccessDeniedError,
    ProviderAuthError,
    ProviderContractError,
    ProviderEdgeBlockedError,
    ProviderErrorCategory,
    ProviderFailure,
    ProviderRateLimitError,
    classify_http_error,
    error_from_failure,
)
from easel.materials.providers.http_support import (
    DEFAULT_PROVIDER_USER_AGENT,
    HttpResponse,
    UrllibTransport,
)


class _Response:
    status = 200
    headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b"{}"


def test_urllib_transport_adds_stable_non_personal_user_agent_for_get_and_post(monkeypatch):
    requests = []

    def fake_urlopen(request, *, timeout):
        requests.append((request, timeout))
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    transport = UrllibTransport()
    transport.get("https://provider.example/search", headers={"Accept": "application/json"}, timeout=7)
    transport.post(
        "https://provider.example/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        body=b"grant_type=client_credentials",
        timeout=9,
    )

    assert [request.get_header("User-agent") for request, _ in requests] == [
        DEFAULT_PROVIDER_USER_AGENT,
        DEFAULT_PROVIDER_USER_AGENT,
    ]
    assert all(request.get_method() in {"GET", "POST"} for request, _ in requests)
    assert "@" not in DEFAULT_PROVIDER_USER_AGENT
    assert "/" not in DEFAULT_PROVIDER_USER_AGENT.split(" ", 1)[-1]
    assert all("secret" not in repr(request.headers).casefold() for request, _ in requests)


@pytest.mark.parametrize(
    ("status", "headers", "body", "expected"),
    [
        (401, {}, b'{"detail":"invalid credentials"}', ProviderAuthError),
        (403, {}, b'{"detail":"invalid bearer token"}', ProviderAuthError),
        (400, {}, b'{"error":"invalid_client"}', ProviderAuthError),
        (
            403,
            {"Content-Type": "text/html"},
            b"The site owner has blocked access based on your browser's signature.",
            ProviderEdgeBlockedError,
        ),
        (403, {"Content-Type": "application/json"}, b'{"detail":"permission denied"}', ProviderAccessDeniedError),
        (429, {"Retry-After": "11"}, b"{}", ProviderRateLimitError),
        (400, {}, b'{"detail":"bad request"}', ProviderContractError),
    ],
)
def test_http_failure_classification_uses_evidence_without_echoing_body(
    status, headers, body, expected
):
    error = classify_http_error("fixture", status, headers, body, retry_after_seconds=11)

    assert isinstance(error, expected)
    assert b"browser" not in str(error).encode().lower()
    assert b"invalid bearer" not in str(error).encode().lower()
    if isinstance(error, ProviderRateLimitError):
        assert error.retry_after_seconds == 11


def test_cloudflare_edge_evidence_uses_headers_and_round_trips_as_typed_failure():
    error = classify_http_error(
        "fixture",
        403,
        {"Server": "cloudflare", "CF-Ray": "opaque-id", "Content-Type": "text/html"},
        b"<html><body>Request denied</body></html>",
    )

    assert isinstance(error, ProviderEdgeBlockedError)
    restored = error_from_failure(error.to_failure())
    assert isinstance(restored, ProviderEdgeBlockedError)
    assert restored.category is ProviderErrorCategory.EDGE_BLOCKED


def test_error_classifier_never_copies_provider_payload_into_persisted_failure():
    response = HttpResponse(
        403,
        {},
        json.dumps({"detail": "blocked", "token": "sensitive-token-value"}).encode(),
    )
    error = classify_http_error("fixture", response.status_code, response.headers, response.body)
    failure: ProviderFailure = error.to_failure()

    assert "sensitive-token-value" not in failure.model_dump_json()
