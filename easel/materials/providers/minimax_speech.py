"""MiniMax T2A adapter; only provider-neutral audio bytes leave this module."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from easel.materials.providers.http_support import HttpTransport, UrllibTransport


MINIMAX_SPEECH_MODELS = frozenset({"speech-2.8-hd", "speech-2.8-turbo", "speech-2.6-hd", "speech-2.6-turbo"})


@dataclass(frozen=True)
class MiniMaxSpeechResult:
    model: str
    voice_id: str
    audio_bytes: bytes
    audio_format: str


class MiniMaxSpeechAdapter:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "speech-2.8-hd",
        voice_id: str = "male-qn-qingse",
        base_url: str = "https://api.minimax.cn",
        transport: HttpTransport | None = None,
    ) -> None:
        if not api_key.strip():
            raise ValueError("MiniMax API key is not configured")
        if model not in MINIMAX_SPEECH_MODELS:
            raise ValueError("Unsupported MiniMax speech model")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", voice_id):
            raise ValueError("Invalid MiniMax preset voice id")
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query
                or parsed.fragment or parsed.path not in ("", "/")
                or parsed.hostname not in {"api.minimax.cn", "api.minimaxi.com", "api.minimax.io"}):
            raise ValueError("MiniMax base URL must use an official HTTPS API host")
        self._key = api_key.strip()
        self._model = model
        self._voice_id = voice_id
        self._base_url = base_url.rstrip("/")
        self._transport = transport or UrllibTransport()

    @property
    def model(self) -> str:
        return self._model

    @property
    def voice_id(self) -> str:
        return self._voice_id

    def generate(self, text: str) -> MiniMaxSpeechResult:
        if not text.strip() or len(text) > 10_000:
            raise ValueError("Speech text must contain 1–10000 characters")
        body = {
            "model": self._model,
            "text": text,
            "stream": False,
            "voice_setting": {"voice_id": self._voice_id, "speed": 1, "vol": 1, "pitch": 0},
            "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3", "channel": 1},
            "output_format": "hex",
        }
        try:
            response = self._transport.post(
                self._base_url + "/v1/t2a_v2",
                headers={"Authorization": f"Bearer {self._key}", "Accept": "application/json",
                         "Content-Type": "application/json"},
                body=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=120,
            )
        except Exception as exc:
            raise ValueError("MiniMax speech request failed; generation result may be uncertain") from exc
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("MiniMax returned invalid speech JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("MiniMax returned an invalid speech response")
        base_resp = payload.get("base_resp")
        code = base_resp.get("status_code") if isinstance(base_resp, dict) else 0
        if not 200 <= response.status_code < 300 or code not in (None, 0):
            raise ValueError(f"MiniMax speech request rejected (code {str(code or response.status_code)[:64]})")
        data = payload.get("data")
        audio_hex = data.get("audio") if isinstance(data, dict) else None
        if not isinstance(audio_hex, str) or not audio_hex or len(audio_hex) % 2:
            raise ValueError("MiniMax speech response did not contain valid audio bytes")
        try:
            audio = bytes.fromhex(audio_hex)
        except ValueError as exc:
            raise ValueError("MiniMax speech response contained invalid audio bytes") from exc
        return MiniMaxSpeechResult(self._model, self._voice_id, audio, "mp3")
