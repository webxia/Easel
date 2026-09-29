"""MiniMax Image-01 adapter; provider response details stay at this boundary."""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from easel.materials.providers.http_support import HttpTransport, UrllibTransport


@dataclass(frozen=True)
class MiniMaxImageResult:
    model: str
    image_bytes: bytes


class MiniMaxImageAdapter:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "image-01",
        base_url: str = "https://api.minimax.cn",
        transport: HttpTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("MiniMax API key is not configured")
        if model != "image-01":
            raise ValueError("Unsupported MiniMax image model")
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query
                or parsed.fragment or parsed.path not in ("", "/")
                or parsed.hostname not in {"api.minimax.cn", "api.minimaxi.com", "api.minimax.io"}):
            raise ValueError("MiniMax base URL must use an official HTTPS API host")
        self._key = api_key.strip()
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._transport = transport or UrllibTransport()

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str, *, aspect_ratio: str = "16:9") -> MiniMaxImageResult:
        if not prompt.strip() or len(prompt) > 1500:
            raise ValueError("Image prompt must contain 1–1500 characters")
        if aspect_ratio not in {"1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"}:
            raise ValueError("Unsupported MiniMax image aspect ratio")
        payload = self._post({
            "model": self._model,
            "prompt": prompt.strip(),
            "aspect_ratio": aspect_ratio,
            "response_format": "base64",
            "n": 1,
            "prompt_optimizer": True,
        })
        data = payload.get("data")
        encoded = data.get("image_base64") if isinstance(data, dict) else None
        if isinstance(encoded, list):
            if len(encoded) != 1:
                raise ValueError("MiniMax image response must contain exactly one image")
            encoded = encoded[0]
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("MiniMax image response did not contain base64 image bytes")
        try:
            image_bytes = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("MiniMax image response contained invalid base64 bytes") from exc
        if not image_bytes:
            raise ValueError("MiniMax returned an empty image")
        return MiniMaxImageResult(self._model, image_bytes)

    def _post(self, body: dict[str, object]) -> dict:
        try:
            response = self._transport.post(
                self._base_url + "/v1/image_generation",
                headers={"Authorization": f"Bearer {self._key}", "Accept": "application/json",
                         "Content-Type": "application/json"},
                body=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=90,
            )
        except Exception as exc:
            raise ValueError("MiniMax image request failed; generation result may be uncertain") from exc
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("MiniMax returned invalid image JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("MiniMax returned an invalid image response")
        base_resp = payload.get("base_resp")
        code = base_resp.get("status_code") if isinstance(base_resp, dict) else 0
        if not 200 <= response.status_code < 300 or code not in (None, 0):
            raise ValueError(f"MiniMax image request rejected (code {str(code or response.status_code)[:64]})")
        return payload
