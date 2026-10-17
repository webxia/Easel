"""Real HTTP request/receipt contracts, with offline transports only."""
import base64
from io import BytesIO
import json

import httpx
from PIL import Image
import pytest

from easel.production.providers.base import ProviderResult, SubmissionNotSent, SubmissionUncertain
from easel.production.providers.generation_http import MiniMaxImageProvider, MiniMaxVideoProvider
from easel.materials.application.acquisition import DownloadResponse, MediaDownloader, RemoteURLPolicy


def image_bytes():
    output = BytesIO()
    Image.new("RGB", (24, 16), "green").save(output, format="PNG")
    return output.getvalue()


IMAGE_REQUEST = {"prompt": "A quiet city", "aspect_ratio": "16:9", "model": "image-01", "mode": "text_to_image"}
VIDEO_REQUEST = {"prompt": "A quiet city", "aspect_ratio": "16:9", "model": "MiniMax-H3", "mode": "text_to_video",
                 "duration_seconds": 4, "resolution": "2K"}


def test_image_posts_once_and_observes_durable_bytes_without_network(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == "/v1/image_generation"
        body = json.loads(request.content)
        assert body["n"] == 1 and body["prompt_optimizer"] is False and body["response_format"] == "base64"
        return httpx.Response(200, json={"id": "trace-id", "base_resp": {"status_code": 0},
            "data": {"image_base64": [base64.b64encode(image_bytes()).decode()]}})
    transport = httpx.MockTransport(handler)
    provider = MiniMaxImageProvider("fixture-key", receipt_root=tmp_path.resolve(), transport=transport)
    submitted = provider.submit(IMAGE_REQUEST, request_key="operation-1")
    assert submitted.state == "succeeded" and submitted.result["sha256"]
    again = MiniMaxImageProvider("fixture-key", receipt_root=tmp_path.resolve(), transport=transport)
    assert again.observe(task_id=None, request_key="operation-1") == submitted
    assert again.submit(IMAGE_REQUEST, request_key="operation-1") == submitted
    assert len(calls) == 1
    with pytest.raises(SubmissionNotSent):
        again.submit({**IMAGE_REQUEST, "prompt": "changed"}, request_key="operation-1")


def test_image_missing_receipt_stays_unknown_and_timeout_does_not_retry(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("fixture timeout")
    provider = MiniMaxImageProvider("fixture-key", receipt_root=tmp_path.resolve(), transport=httpx.MockTransport(handler))
    with pytest.raises(SubmissionUncertain):
        provider.submit(IMAGE_REQUEST, request_key="operation-1")
    assert provider.observe(task_id=None, request_key="operation-1").state == "unknown"
    assert len(calls) == 1


@pytest.mark.parametrize("case", [
    {**IMAGE_REQUEST, "model": "other"}, {**IMAGE_REQUEST, "mode": "image_to_image"},
    {**IMAGE_REQUEST, "provider": "other"}, {**IMAGE_REQUEST, "aspect_ratio": "bad"},
])
def test_image_configuration_mismatch_never_sends(tmp_path, case):
    calls = []
    provider = MiniMaxImageProvider("fixture", receipt_root=tmp_path.resolve(), transport=httpx.MockTransport(lambda r: calls.append(r)))
    with pytest.raises(SubmissionNotSent):
        provider.submit(case, request_key="operation-1")
    assert not calls


def test_unconfigured_modalities_report_unavailable_without_call(tmp_path):
    image = MiniMaxImageProvider("", receipt_root=tmp_path.resolve())
    video = MiniMaxVideoProvider("", model="MiniMax-H3")
    for provider, request in ((image, IMAGE_REQUEST), (video, VIDEO_REQUEST)):
        assert not provider.available
        with pytest.raises(SubmissionNotSent, match="capability_unavailable"):
            provider.submit(request, request_key="operation-1")


def test_video_submit_observe_identity_and_pending_are_separate():
    calls = []
    states = iter(["running", "succeeded"])
    def handler(request):
        calls.append(request)
        if request.method == "POST":
            assert request.url.path == "/v2/video_generation"
            assert json.loads(request.content)["duration"] == 4
            return httpx.Response(200, json={"task_id": "task-1"})
        assert request.url.path == "/v2/query/video_generation/task-1"
        return httpx.Response(200, json={"task": {"id": "task-1", "model": "MiniMax-H3", "status": next(states),
            "content": {"url": "https://cdn.hailuoai.com/video.mp4"}, "duration": 4, "resolution": "2K", "ratio": "16:9"}})
    provider = MiniMaxVideoProvider("fixture-key", model="MiniMax-H3", transport=httpx.MockTransport(handler))
    submitted = provider.submit(VIDEO_REQUEST, request_key="operation-1")
    assert submitted.state == "submitted" and submitted.task_id == "task-1"
    assert provider.observe(task_id="task-1", request_key="operation-1").state == "submitted"
    observed = provider.observe(task_id="task-1", request_key="operation-1")
    assert observed.state == "succeeded" and observed.result["model"] == "MiniMax-H3"
    assert [r.method for r in calls] == ["POST", "GET", "GET"]


@pytest.mark.parametrize("payload", [
    {"task": {"id": "wrong", "status": "succeeded"}},
    {"task": {"id": "task-1", "status": "new_unknown_state"}},
    {"task": {"id": "task-1", "status": "succeeded", "content": {"url": "http://127.0.0.1/private"}}},
    {"task": {"id": "task-1", "model": "other", "status": "running"}},
])
def test_video_ambiguous_observations_remain_unknown(payload):
    provider = MiniMaxVideoProvider("fixture", model="MiniMax-H3", transport=httpx.MockTransport(lambda r: httpx.Response(200, json=payload)))
    assert provider.observe(task_id="task-1", request_key="operation-1").state == "unknown"


def test_video_404_is_not_proof_of_unsubmitted_and_unknown_submit_is_not_replayed():
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={}) if request.method == "POST" else httpx.Response(404)
    provider = MiniMaxVideoProvider("fixture", model="MiniMax-H3", transport=httpx.MockTransport(handler))
    with pytest.raises(SubmissionUncertain):
        provider.submit(VIDEO_REQUEST, request_key="operation-1")
    assert provider.observe(task_id="task-1", request_key="operation-1").state == "unknown"
    assert provider.observe(task_id=None, request_key="operation-1").state == "unknown"
    assert [r.method for r in calls] == ["POST", "GET"]


def test_video_download_is_only_download_of_existing_receipt():
    calls = []
    class Transport:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            return DownloadResponse(200, {"content-type": "video/mp4"}, b"offline bytes")
    downloader = MediaDownloader(RemoteURLPolicy(("cdn.hailuoai.com",), resolver=lambda *_: ("8.8.8.8",)), transport=Transport())
    provider = MiniMaxVideoProvider("fixture", model="MiniMax-H3")
    receipt = ProviderResult("succeeded", task_id="task-1", result={"url": "https://cdn.hailuoai.com/a.mp4"})
    assert provider.download(receipt, downloader=downloader).body == b"offline bytes"
    assert len(calls) == 1 and calls[0][1]["addresses"] == ("8.8.8.8",)


def test_video_does_not_silently_change_resolution_or_duration():
    provider = MiniMaxVideoProvider("fixture", model="MiniMax-H3-Max")
    with pytest.raises(SubmissionNotSent):
        provider.submit({**VIDEO_REQUEST, "model": "MiniMax-H3-Max", "duration_seconds": 4}, request_key="op")
    with pytest.raises(SubmissionNotSent):
        provider.submit({**VIDEO_REQUEST, "model": "MiniMax-H3-Max", "duration_seconds": 5}, request_key="op")
