"""MiniMax T2A adapter; only provider-neutral audio bytes leave this module."""

from __future__ import annotations

import json
import math
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
    timings: tuple[dict, ...] = ()
    timing_error: str | None = None
    original_subtitles: tuple[dict, ...] = ()


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

    def generate(self, text: str, *, pace_ratio: float = 1.0, pitch_semitones: int = 0,
                 tone: str | None = None) -> MiniMaxSpeechResult:
        from easel.materials.application.voice_delivery import validate_voice_delivery

        validate_voice_delivery({"pace_ratio": pace_ratio, "pitch_semitones": pitch_semitones, "tone": tone})
        if not text.strip() or len(text) > 10_000:
            raise ValueError("Speech text must contain 1–10000 characters")
        voice_setting = {"voice_id": self._voice_id, "speed": pace_ratio, "vol": 1, "pitch": pitch_semitones}
        if tone is not None:
            voice_setting["emotion"] = {"neutral": "calm", "afraid": "fearful"}.get(tone, tone)
        body = {
            "model": self._model,
            "text": text,
            "stream": True,
            "stream_options": {"exclude_aggregated_audio": False},
            "subtitle_enable": True,
            "subtitle_type": "sentence",
            "voice_setting": voice_setting,
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
        if not 200 <= response.status_code < 300:
            raise ValueError(f"MiniMax speech request rejected (HTTP {response.status_code})")
        try:
            text_body = response.body.decode("utf-8")
            if text_body.lstrip().startswith("{"):
                packets = [json.loads(text_body)]  # JSON error responses are allowed by the API.
            else:
                packets = [json.loads(line[5:].strip()) for line in text_body.splitlines()
                           if line.startswith("data:") and line[5:].strip() not in {"", "[DONE]"}]
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("MiniMax returned invalid speech stream") from exc
        final = None
        subtitles = []
        for packet in packets:
            if not isinstance(packet, dict):
                raise ValueError("MiniMax returned an invalid speech response")
            base_resp = packet.get("base_resp")
            code = base_resp.get("status_code") if isinstance(base_resp, dict) else 0
            if code not in (None, 0):
                raise ValueError("MiniMax speech stream reported a generation failure")
            data = packet.get("data")
            if not isinstance(data, dict):
                continue
            if isinstance(data.get("subtitle"), dict):
                subtitles.append(data["subtitle"])
            if data.get("status") == 2:
                if final is not None:
                    raise ValueError("MiniMax speech stream has multiple terminal audio payloads")
                final = data
        if final is None:
            raise ValueError("MiniMax speech stream ended without a complete result; do not resubmit")
        # Official exclude_aggregated_audio=False: terminal audio contains the
        # entire utterance. Appending earlier chunks would duplicate narration.
        audio_hex = final.get("audio")
        if not isinstance(audio_hex, str) or not audio_hex or len(audio_hex) % 2:
            raise ValueError("MiniMax speech response did not contain valid audio bytes")
        try:
            audio = bytes.fromhex(audio_hex)
        except ValueError as exc:
            raise ValueError("MiniMax speech response contained invalid audio bytes") from exc
        timings = ()
        timing_error = None
        try:
            timings = self.map_timings(text, self._timings(final.get("subtitles", subtitles)))
        except (TypeError, ValueError, KeyError):
            # Valid audio must survive missing/bad alignment; this does not
            # authorize another paid TTS request or fabricate subtitle timing.
            timing_error = "provider_timing_missing_or_invalid"
        return MiniMaxSpeechResult(self._model, self._voice_id, audio, "mp3", timings, timing_error,
                                   tuple(final.get("subtitles", subtitles)) if isinstance(final.get("subtitles", subtitles), list) else ())

    @staticmethod
    def _timings(rows) -> tuple[dict, ...]:
        if not isinstance(rows, list) or not rows:
            raise ValueError("missing subtitles")
        cues = []
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("text"), str) or not row["text"].strip():
                raise ValueError("invalid subtitle")
            begin, end = row["time_begin"], row["time_end"]
            start_char, end_char = row["text_begin"], row["text_end"]
            if (any(type(t) not in (int, float) or not math.isfinite(t) for t in (begin, end))
                    or not 0 <= begin < end or type(start_char) is not int or type(end_char) is not int
                    or not 0 <= start_char < end_char):
                raise ValueError("invalid subtitle position")
            cues.append({"text": row["text"], "start_seconds": begin / 1000, "end_seconds": end / 1000,
                         "start_character": start_char, "end_character": end_char})
        return tuple(cues)

    @staticmethod
    def map_timings(script: str, cues: tuple[dict, ...]) -> tuple[dict, ...]:
        """Map exact subtitle text, retaining measured times and provider offsets.

        Official T2ASubtitle offsets are [begin,end), milliseconds. Some saved
        responses index the newline-free synthesis text. Accept that deviation
        only when *all* text/offsets prove one complete, unambiguous mapping.
        Never subtract a guessed newline count or search for a convenient match.
        """
        if not cues:
            raise ValueError('missing subtitles')
        possibilities = []
        for indices in (list(range(len(script))), [i for i, c in enumerate(script) if c not in '\r\n']):
            canonical = ''.join(script[i] for i in indices)
            cursor, last_time, mapped = 0, 0., []
            try:
                for cue in cues:
                    begin, end = cue['start_character'], cue['end_character']
                    start, finish = cue['start_seconds'], cue['end_seconds']
                    if (type(begin) is not int or type(end) is not int or begin != cursor
                            or not begin < end <= len(indices) or cue['text'] != canonical[begin:end]
                            or any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, finish))
                            or not last_time <= start < finish):
                        raise ValueError('ambiguous or incomplete subtitle mapping')
                    a, b = indices[begin], indices[end - 1] + 1
                    mapped.append({**cue, 'text': script[a:b], 'start_character': a, 'end_character': b})
                    cursor, last_time = end, finish
                if cursor != len(indices):
                    raise ValueError('incomplete subtitle text')
            except (KeyError, TypeError, ValueError):
                continue
            if mapped not in possibilities:
                possibilities.append(mapped)
        if len(possibilities) != 1:
            raise ValueError('subtitle text cannot uniquely cover frozen script')
        return tuple(possibilities[0])
