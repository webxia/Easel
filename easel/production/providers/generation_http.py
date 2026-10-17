"""MiniMax IMAGE/VIDEO protocols behind the production operation boundary.

Adapted from V1 minimax_image.py/minimax_video.py (57c8e2ad, Apache-2.0).
V2 removes blocking poll loops/old authorization, separates one submit from one
observation, and retains sync image receipts before returning to the caller.
Official protocol sources and untested live scope: materials/MIGRATION.md.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import quote, urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from easel.materials.store import MaterialFileStore, digest_file, reject_symlinks
from easel.materials.application.acquisition import MediaDownloader, RemoteURLPolicy
from .base import ProviderCapabilities, ProviderResult, SubmissionNotSent, SubmissionUncertain


API_HOSTS = {"api.minimax.io", "api.minimaxi.com", "api.minimax.cn"}
MEDIA_HOSTS = ("cdn.hailuoai.com", "algeng-video-infer.oss-cn-shanghai.aliyuncs.com",
               "minimax.io", "minimaxi.com", "minimaxi.cn", "minimax.cn")


def _valid_media_url(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "https" and parsed.hostname and parsed.port in (None, 443)
                and not parsed.username and not parsed.password and not parsed.fragment
                and any(parsed.hostname == h or parsed.hostname.endswith("." + h) for h in MEDIA_HOSTS))
    except (TypeError, ValueError):
        return False


class _MiniMaxHTTP:
    provider_id = "minimax"

    def __init__(self, api_key: str, *, model: str, base_url: str = "https://api.minimax.io",
                 transport: httpx.BaseTransport | None = None, timeout: float = 90):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "https" or parsed.hostname not in API_HOSTS or parsed.port not in (None, 443)
                or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
            raise ValueError("MiniMax endpoint must be an official HTTPS API host")
        if timeout <= 0:
            raise ValueError("Request timeout must be positive")
        self._key, self.model, self._base = api_key.strip(), model, base_url.rstrip("/")
        self._transport, self._timeout = transport, timeout

    @property
    def available(self):
        return bool(self._key)

    def _validate_request(self, request, *, mode):
        if not self.available:
            raise SubmissionNotSent("capability_unavailable: MiniMax credential is not configured")
        if request.get("model", self.model) != self.model or request.get("mode", mode) != mode:
            raise SubmissionNotSent("Configured model/mode does not match the authorized operation")
        if request.get("provider", self.provider_id) != self.provider_id:
            raise SubmissionNotSent("Configured provider does not match the authorized operation")

    def _request(self, method: str, endpoint: str, *, body=None):
        try:
            # No proxy environment, redirect following or automatic submit retry.
            with httpx.Client(transport=self._transport, trust_env=False, follow_redirects=False,
                              timeout=self._timeout) as client:
                with client.stream(method, self._base + endpoint, json=body,
                    headers={"Authorization": "Bearer " + self._key, "Accept": "application/json"}) as response:
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > 48 * 1024 * 1024:
                            raise SubmissionUncertain("Provider receipt exceeds the configured limit")
                        chunks.append(chunk)
                    if not 200 <= response.status_code < 300:
                        return response.status_code, {}
                    payload = json.loads(b"".join(chunks))
                    if not isinstance(payload, dict):
                        raise ValueError
                    return response.status_code, payload
        except SubmissionUncertain:
            raise
        except (httpx.HTTPError, ValueError, OSError) as exc:
            raise SubmissionUncertain("Provider response cannot be verified; do not resubmit") from exc

    @staticmethod
    def _rejected(status, payload):
        if status >= 500 or 300 <= status < 400:
            raise SubmissionUncertain("Provider did not establish the submission result")
        base = payload.get("base_resp")
        if base is not None and not isinstance(base, dict):
            raise SubmissionUncertain("Provider receipt has an invalid status shape")
        return not 200 <= status < 300 or (base or {}).get("status_code", 0) not in (0, None)


class MiniMaxImageProvider(_MiniMaxHTTP):
    """One image per authorized submission; recovery uses local receipts only.

    MiniMax does not document image lookup by request key. Missing local receipt
    therefore means UNKNOWN, never proof of a failed/not-sent submission.
    """

    capabilities = ProviderCapabilities(query_by_request_key=True)
    mode = "text_to_image"

    def __init__(self, api_key: str, *, receipt_root: str | Path, model: str = "image-01", **kwargs):
        if model != "image-01":
            raise ValueError("Unsupported MiniMax image model")
        super().__init__(api_key, model=model, **kwargs)
        root = Path(receipt_root).absolute()
        if any(p.is_symlink() for p in (root, *root.parents)):
            raise ValueError("Image receipt root must not contain symlinks")
        root.mkdir(parents=True, exist_ok=True)
        self.files = MaterialFileStore(root)

    @staticmethod
    def _key_hash(request_key):
        if not isinstance(request_key, str) or not request_key.strip():
            raise SubmissionNotSent("A stable operation request key is required")
        return hashlib.sha256(request_key.encode()).hexdigest()

    def _receipt(self, key):
        return self.files.root / (key + ".json")

    def submit(self, request: dict, *, request_key: str) -> ProviderResult:
        self._validate_request(request, mode=self.mode)
        key = self._key_hash(request_key)
        prompt, ratio = request.get("prompt"), request.get("aspect_ratio")
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 1500:
            raise SubmissionNotSent("Image prompt must contain 1–1500 characters")
        if ratio not in {"1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9"}:
            raise SubmissionNotSent("Image aspect ratio is unsupported or absent")
        request_hash = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        receipt = self._read_receipt(key)
        if receipt is not None:
            if receipt["request_hash"] != request_hash:
                raise SubmissionNotSent("An operation key cannot be reused for different content")
            return self.observe(task_id=None, request_key=request_key)
        status, payload = self._request("POST", "/v1/image_generation", body={
            "model": self.model, "prompt": prompt.strip(), "aspect_ratio": ratio,
            "response_format": "base64", "n": 1, "prompt_optimizer": False})
        if self._rejected(status, payload):
            return ProviderResult("failed", result={"error": "provider_rejected", "http_status": status})
        data = payload.get("data")
        encoded = data.get("image_base64") if isinstance(data, dict) else None
        if isinstance(encoded, list) and len(encoded) == 1:
            encoded = encoded[0]
        if not isinstance(encoded, str):
            raise SubmissionUncertain("Image receipt did not contain the expected result")
        try:
            content = base64.b64decode(encoded, validate=True)
            if not content or len(content) > 32 * 1024 * 1024:
                raise ValueError
            with Image.open(BytesIO(content)) as im:
                im.verify()
            with Image.open(BytesIO(content)) as im:
                mime = Image.MIME.get(im.format or "", "")
            if not mime.startswith("image/"):
                raise ValueError
        except (ValueError, binascii.Error, OSError, UnidentifiedImageError):
            return ProviderResult("failed", result={"error": "invalid_generated_image"})
        digest = hashlib.sha256(content).hexdigest()
        filename = f"{key}.image"
        target = self.files.root / filename
        self._atomic_write(target, content)
        result = {"local_path": str(target), "sha256": digest, "media_type": "image", "mime": mime,
                  "provider": self.provider_id, "model": self.model}
        record = {"request_hash": request_hash, "result": result}
        self._atomic_write(self._receipt(key), json.dumps(record, sort_keys=True).encode())
        return ProviderResult("succeeded", result=result)

    def _atomic_write(self, path, content):
        reject_symlinks(self.files.root, path)
        fd, name = tempfile.mkstemp(dir=self.files.root, prefix=".receipt-")
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            reject_symlinks(self.files.root, path)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_receipt(self, key):
        path = self._receipt(key)
        reject_symlinks(self.files.root, path)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            if not isinstance(data.get("request_hash"), str) or not isinstance(data.get("result"), dict):
                raise ValueError
            return data
        except (OSError, ValueError, AttributeError) as exc:
            raise SubmissionUncertain("Local image receipt cannot be verified") from exc

    def observe(self, *, task_id: str | None, request_key: str) -> ProviderResult:
        key = self._key_hash(request_key)
        receipt = self._read_receipt(key)
        if receipt is None:
            return ProviderResult("unknown")
        result = receipt["result"]
        expected = self.files.root / f"{key}.image"
        reject_symlinks(self.files.root, expected)
        if result.get("local_path") != str(expected) or not expected.is_file() or digest_file(expected) != result.get("sha256"):
            return ProviderResult("unknown")
        return ProviderResult("succeeded", result=result)


class MiniMaxVideoProvider(_MiniMaxHTTP):
    """Video V2: submit once; observe one known task per call, without waiting."""

    capabilities = ProviderCapabilities(query_by_task_id=True)
    mode = "text_to_video"

    def __init__(self, api_key: str, *, model: str, **kwargs):
        if model not in {"MiniMax-H3", "MiniMax-H3-Max"}:
            raise ValueError("Unsupported MiniMax video model")
        super().__init__(api_key, model=model, **kwargs)

    def submit(self, request: dict, *, request_key: str) -> ProviderResult:
        self._validate_request(request, mode=self.mode)
        prompt, duration = request.get("prompt"), request.get("duration_seconds")
        ratio, resolution = request.get("aspect_ratio"), request.get("resolution")
        minimum = 4 if self.model == "MiniMax-H3" else 5
        resolutions = {"768P", "2K"} if self.model == "MiniMax-H3" else {"480P", "768P"}
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 7000:
            raise SubmissionNotSent("Video prompt must contain 1–7000 characters")
        if type(duration) is not int or not minimum <= duration <= 15 or resolution not in resolutions:
            raise SubmissionNotSent("Video duration or resolution is unsupported")
        if ratio not in {"16:9", "9:16", "1:1", "4:3", "3:4", "21:9"}:
            raise SubmissionNotSent("Video aspect ratio is unsupported or absent")
        status, payload = self._request("POST", "/v2/video_generation", body={"model": self.model,
            "content": [{"type": "text", "text": prompt.strip()}], "duration": duration,
            "resolution": resolution, "ratio": ratio})
        if self._rejected(status, payload):
            return ProviderResult("failed", result={"error": "provider_rejected", "http_status": status})
        task_id = payload.get("task_id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id):
            raise SubmissionUncertain("Video submission did not return a verifiable task identity")
        return ProviderResult("submitted", task_id=task_id)

    def observe(self, *, task_id: str | None, request_key: str) -> ProviderResult:
        if not task_id or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", task_id) or not self.available:
            return ProviderResult("unknown", task_id=task_id)
        try:
            status, payload = self._request("GET", "/v2/query/video_generation/" + quote(task_id, safe=""))
        except SubmissionUncertain:
            return ProviderResult("unknown", task_id=task_id)
        if not 200 <= status < 300:
            # A 404 is not evidence that the earlier paid submission never happened.
            return ProviderResult("unknown", task_id=task_id)
        task = payload.get("task")
        if not isinstance(task, dict) or task.get("id") != task_id or task.get("model", self.model) != self.model:
            return ProviderResult("unknown", task_id=task_id)
        state = task.get("status")
        if state in {"queued", "running"}:
            return ProviderResult("submitted", task_id=task_id)
        if state in {"failed", "cancelled"}:
            return ProviderResult("failed", task_id=task_id, result={"error": "provider_task_" + state})
        content = task.get("content")
        if state != "succeeded" or not isinstance(content, dict) or not _valid_media_url(content.get("url")):
            return ProviderResult("unknown", task_id=task_id)
        return ProviderResult("succeeded", task_id=task_id, result={"url": content["url"],
            "provider": self.provider_id, "model": self.model, "media_type": "video",
            "duration_seconds": task.get("duration"), "resolution": task.get("resolution"), "ratio": task.get("ratio")})

    def download(self, result: ProviderResult, *, downloader: MediaDownloader | None = None):
        """Receive the existing result; never POST, observe or create another task."""
        url = result.result.get("url")
        if result.state != "succeeded" or not _valid_media_url(url):
            raise ValueError("A verified completed video result is required")
        client = downloader or MediaDownloader(RemoteURLPolicy(MEDIA_HOSTS))
        return client.download(url, media_type="video")
