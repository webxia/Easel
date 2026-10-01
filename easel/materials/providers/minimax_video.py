"""MiniMax's asynchronous video API, isolated behind a small HTTP adapter."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Callable, Mapping
from urllib.parse import quote, urlsplit

from easel.materials.providers.http_support import HttpTransport, UrllibTransport


DEFAULT_MINIMAX_VIDEO_BASE_URL = "https://api.minimax.cn"
MINIMAX_VIDEO_MODELS = frozenset({"MiniMax-H3", "MiniMax-H3-Max"})


class MiniMaxVideoError(ValueError):
    """A sanitized MiniMax API or task failure; never includes credentials."""

    def __init__(self, message: str, *, submission_uncertain: bool = False, observation_retryable: bool = False):
        super().__init__(message)
        self.submission_uncertain = submission_uncertain
        self.observation_retryable = observation_retryable


class MiniMaxVideoObservationPending(MiniMaxVideoError):
    """A known task has no terminal observation; it must not be resubmitted."""

    def __init__(self, message: str, *, task_status: str | None = None):
        super().__init__(message)
        self.task_status = task_status


@dataclass(frozen=True)
class MiniMaxVideoTask:
    task_id: str
    model: str
    status: str
    video_url: str | None = None
    duration_seconds: float | None = None
    error_code: str | None = None
    usage: Mapping[str, int | float] = field(default_factory=dict)


class MiniMaxVideoAdapter:
    """Implements MiniMax Video Generation V2 without leaking its schema."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "MiniMax-H3-Max",
        base_url: str = DEFAULT_MINIMAX_VIDEO_BASE_URL,
        transport: HttpTransport | None = None,
        poll_interval_seconds: float = 4.0,
        timeout_seconds: float = 1200.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not api_key.strip():
            raise MiniMaxVideoError("MiniMax API key is not configured")
        if model not in MINIMAX_VIDEO_MODELS:
            raise MiniMaxVideoError("Unsupported MiniMax video model")
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or parsed.username or parsed.password or parsed.query
                or parsed.fragment or parsed.path not in ("", "/") or not parsed.hostname
                or not self._official_api_host(parsed.hostname)):
            raise MiniMaxVideoError("MiniMax base URL must use an official HTTPS API host")
        if poll_interval_seconds <= 0 or timeout_seconds <= 0:
            raise ValueError("MiniMax polling limits must be positive")
        self._api_key = api_key.strip()
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._transport = transport or UrllibTransport()
        self._poll_interval = poll_interval_seconds
        self._timeout = timeout_seconds
        self._sleep = sleep
        self._monotonic = monotonic

    @property
    def model(self) -> str:
        return self._model

    @staticmethod
    def _official_api_host(host: str) -> bool:
        return host.lower() in {"api.minimax.cn", "api.minimaxi.com", "api.minimax.io"}

    def submit(
        self,
        prompt: str,
        *,
        duration_seconds: int,
        resolution: str = "480P",
        ratio: str = "16:9",
    ) -> MiniMaxVideoTask:
        if not prompt.strip() or len(prompt) > 7000:
            raise MiniMaxVideoError("Video prompt must contain 1–7000 characters")
        if not 5 <= duration_seconds <= 15:
            raise MiniMaxVideoError("MiniMax H3 video duration must be between 5 and 15 seconds")
        if self._model == "MiniMax-H3-Max":
            if resolution not in {"480P", "768P"}:
                raise MiniMaxVideoError("MiniMax-H3-Max supports 480P or 768P")
        elif resolution not in {"768P", "2K"}:
            raise MiniMaxVideoError("MiniMax-H3 supports 768P or 2K")
        if ratio not in {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9"}:
            raise MiniMaxVideoError("Unsupported MiniMax video ratio")
        body = {
            "model": self._model,
            "content": [{"type": "text", "text": prompt.strip()}],
            "resolution": resolution,
            "duration": duration_seconds,
            "ratio": ratio,
        }
        payload = self._request("POST", "/v2/video_generation", body=body)
        task_id = payload.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise MiniMaxVideoError("MiniMax did not return a task identifier")
        return MiniMaxVideoTask(task_id=task_id, model=self._model, status="queued")

    def wait(self, task_id: str) -> MiniMaxVideoTask:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
            raise MiniMaxVideoError("Invalid MiniMax task identifier")
        deadline = self._monotonic() + self._timeout
        last_status = None
        while self._monotonic() < deadline:
            try:
                payload = self._request("GET", f"/v2/query/video_generation/{quote(task_id, safe='')}")
            except MiniMaxVideoError as exc:
                if not exc.observation_retryable:
                    raise  # Explicit auth/parameter refusal needs repair, not endless polling.
                raise MiniMaxVideoObservationPending("暂时无法读取视频素材任务状态，已保留任务，将继续查询") from exc
            task = payload.get("task")
            if not isinstance(task, dict) or task.get("id") != task_id:
                raise MiniMaxVideoObservationPending("视频素材查询返回的任务身份无效，尚未确认当前状态")
            status = task.get("status")
            if status == "succeeded":
                content = task.get("content")
                url = content.get("url") if isinstance(content, dict) else None
                if not isinstance(url, str) or not self._official_media_url(url):
                    raise MiniMaxVideoError("MiniMax completed without a valid video URL")
                duration = task.get("duration")
                try:
                    duration_value = float(duration) if duration is not None else None
                except (ValueError, TypeError, OverflowError):
                    duration_value = None
                usage_raw = task.get("usage")
                usage = {
                    str(key): value for key, value in usage_raw.items()
                    if isinstance(key, str) and isinstance(value, (int, float)) and not isinstance(value, bool)
                } if isinstance(usage_raw, dict) else {}
                return MiniMaxVideoTask(task_id, str(task.get("model") or self._model), status,
                                        url, duration_value, usage=usage)
            if status in {"failed", "cancelled"}:
                error = task.get("error")
                code = error.get("code") if isinstance(error, dict) else None
                safe_code = str(code)[:64] if code is not None else None
                raise MiniMaxVideoError(f"MiniMax task {status}" + (f" (code {safe_code})" if safe_code else ""))
            if status not in {"queued", "running"}:
                raise MiniMaxVideoObservationPending("视频素材查询返回未知状态，尚未确认任务结果")
            last_status = status
            self._sleep(min(self._poll_interval, max(0.0, deadline - self._monotonic())))
        raise MiniMaxVideoObservationPending("视频素材仍在排队或制作，将继续查询同一任务", task_status=last_status)

    @staticmethod
    def _official_media_url(value: str) -> bool:
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        host = (parsed.hostname or "").lower().rstrip(".")
        allowed = ("minimax.io", "minimaxi.com", "minimaxi.cn", "minimax.cn")
        return (parsed.scheme == "https" and not parsed.username and not parsed.password
                and parsed.port in (None, 443) and not parsed.fragment
                and (host == "algeng-video-infer.oss-cn-shanghai.aliyuncs.com"
                     or any(host == domain or host.endswith("." + domain) for domain in allowed)))

    def _request(self, method: str, path: str, *, body: dict[str, object] | None = None) -> dict:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        try:
            if method == "POST":
                headers["Content-Type"] = "application/json"
                response = self._transport.post(
                    self._base_url + path, headers=headers,
                    body=json.dumps(body, ensure_ascii=False).encode("utf-8"), timeout=30,
                )
            else:
                response = self._transport.get(self._base_url + path, headers=headers, timeout=30)
        except Exception as exc:
            raise MiniMaxVideoError(
                "MiniMax API request failed; task submission may be uncertain",
                submission_uncertain=method == "POST",
                observation_retryable=method == "GET",
            ) from exc
        if not 200 <= response.status_code < 300:
            raise MiniMaxVideoError(f"MiniMax API rejected the request (code {response.status_code})",
                                    observation_retryable=method == "GET" and (response.status_code == 429 or response.status_code >= 500))
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MiniMaxVideoError("MiniMax returned invalid JSON", observation_retryable=method == "GET") from exc
        if not isinstance(payload, dict):
            raise MiniMaxVideoError("MiniMax returned an invalid response", observation_retryable=method == "GET")
        base_resp = payload.get("base_resp")
        status_code = base_resp.get("status_code") if isinstance(base_resp, dict) else 0
        if status_code not in (None, 0):
            safe_code = str(status_code or response.status_code)[:64]
            raise MiniMaxVideoError(f"MiniMax API rejected the request (code {safe_code})")
        return payload


__all__ = ["MiniMaxVideoAdapter", "MiniMaxVideoError", "MiniMaxVideoObservationPending", "MiniMaxVideoTask"]
