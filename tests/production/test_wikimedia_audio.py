"""Commons BGM/SFX: role safety, source-page rights and offline supply integration.

No Wikimedia network calls, credentials or paid model operations occur.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
import json
import shutil
import subprocess

import httpx
import pytest

from easel.materials.application.acquisition import DownloadResponse, MediaDownloader, RemoteURLPolicy
from easel.materials.application.supply import MaterialSupply
from easel.materials.domain import MediaType, NeedImportance, NeedIntent, NeedScope, NeedScopeType, MaterialNeed
from easel.materials.library import LibraryVisibility, UseContext
from easel.production.materials import MaterialService
from easel.production.providers.stock import StockUnavailable
from easel.production.providers.wikimedia_audio import WikimediaAudioProvider
from easel.production.supply_tasks import configured_supply
from easel.production.configuration import capabilities
from .test_voice_subtitles import wav_bytes


def _file(*, license="CC BY 4.0", license_url="https://creativecommons.org/licenses/by/4.0/",
          creator="<a href='https://commons.wikimedia.org/wiki/User:Maker'>Maker</a>",
          mime="audio/wav", url="https://upload.wikimedia.org/wikipedia/commons/a/aa/City_sound.wav"):
    meta = {"LicenseShortName": {"value": license}, "LicenseUrl": {"value": license_url},
            "Artist": {"value": creator}}
    return {"ns": 6, "pageid": 4288, "title": "File:City sound.wav",
            "imageinfo": [{"url": url,
                           "descriptionurl": "https://commons.wikimedia.org/wiki/File:City_sound.wav",
                           "mime": mime, "size": 40000, "sha1": sha1(wav_bytes()).hexdigest(), "extmetadata": meta}]}


def _mock_provider(role, pages, *, status=200):
    observed = []
    def handle(request):
        observed.append(request)
        return httpx.Response(status, json={"query": {"pages": pages}} if status == 200 else {"error": {"code":"ratelimited"}})
    return WikimediaAudioProvider(role, transport=httpx.MockTransport(handle)), observed


def _need(role):
    return MaterialNeed(need_id=role+"-need",media_type=MediaType.AUDIO,role=role,
        scope=NeedScope(type=NeedScopeType.GLOBAL if role == "music" else NeedScopeType.EVENT,
                        ref="work-1" if role == "music" else "cue-1"),
        importance=NeedImportance.REQUIRED,intent=NeedIntent(description="calm cinematic music" if role=="music" else "door click"))


def test_bgm_search_yields_licensed_audio_and_exact_attribution():
    provider, calls = _mock_provider("music", [_file()])
    result = provider.search("calm cinematic", media_type=MediaType.AUDIO,limit=3)
    assert len(result) == 1
    candidate=result[0]
    assert candidate.media_type is MediaType.AUDIO
    assert candidate.source.creator == "Maker"
    assert candidate.source.provider_asset_id == "4288:"+sha1(wav_bytes()).hexdigest()
    assert candidate.semantic.attributes["audio_roles"] == ["music"]
    assert candidate.rights.attribution_required
    assert candidate.source.source_page in candidate.rights.attribution_text
    assert "CC BY 4.0" in candidate.rights.attribution_text
    assert candidate.download_url.startswith("https://upload.wikimedia.org/")
    assert len(calls) == 1
    assert calls[0].url.host == "commons.wikimedia.org"
    assert calls[0].url.params["gsrnamespace"] == "6"
    assert "filetype:audio" in calls[0].url.params["gsrsearch"]
    assert "EaselAudio" in calls[0].headers["User-Agent"]
    assert "github.com/webxia/Easel" in calls[0].headers["User-Agent"]


def test_source_page_tracking_query_does_not_poison_stable_attribution():
    page=_file()
    page['imageinfo'][0]['descriptionurl'] += '?utm_source=commons'
    provider,_=_mock_provider('music',[page])
    candidate=provider.search('calm',media_type=MediaType.AUDIO)[0]
    assert candidate.source.source_page.endswith('City_sound.wav')
    assert 'utm_source' not in candidate.rights.attribution_text


def test_sfx_search_accepts_cc0_without_attribution_or_account():
    provider,calls=_mock_provider("sfx",[_file(license="CC0 1.0",
        license_url="https://creativecommons.org/publicdomain/zero/1.0/",creator="")])
    results=provider.search("door click",media_type=MediaType.AUDIO,limit=1)
    assert results[0].rights.status.value == "PUBLIC_DOMAIN"
    assert results[0].rights.attribution_required is False
    assert results[0].semantic.attributes["audio_roles"] == ["sfx"]
    assert calls[0].url.params["gsrsearch"] == 'door click filetype:audio'


def test_actual_cc0_metadata_legacy_deed_and_ogg_source_are_accepted():
    page=_file(license='CC0',license_url='http://creativecommons.org/publicdomain/zero/1.0/deed.en',
               mime='application/ogg',url='https://upload.wikimedia.org/wikipedia/commons/0/0e/Rain.ogg')
    page['title']='File:Rain.ogg'
    provider,_=_mock_provider('sfx',[page])
    result=provider.search('rain',media_type=MediaType.AUDIO)
    assert len(result)==1
    assert result[0].rights.license_name=='CC0 1.0'
    assert result[0].rights.license_url=='https://creativecommons.org/publicdomain/zero/1.0/'


@pytest.mark.parametrize("changes",[
    {"license":"CC BY-NC-SA 4.0"},
    {"license":"CC BY-SA 4.0"},
    {"license":"CC BY 4.0","license_url":"https://creativecommons.org/licenses/by-nc/4.0/"},
    {"license":"CC BY 4.0","creator":""},
    {"mime":"image/png"},
    {"url":"https://127.0.0.1/internal.wav"},
    {"url":"https://other.example/file.wav"},
])
def test_unlicensed_non_audio_or_untrusted_host_is_not_a_candidate(changes):
    provider,_ = _mock_provider("sfx",[_file(**changes)])
    assert provider.search("click",media_type=MediaType.AUDIO) == ()


@pytest.mark.parametrize("changes",[
    {"size":128 * 1024 * 1024+1},
    {"sha1":"invalid"},
    {"descriptionurl":"https://evil.example/forge"},
    {"ns":0},
    {"pageid":"not-a-number"},
])
def test_malformed_file_metadata_is_not_a_candidate(changes):
    file=_file()
    if any(k in changes for k in ("size","sha1","descriptionurl")):
        file["imageinfo"][0].update(changes)
    else:
        file.update(changes)
    provider,_=_mock_provider("sfx",[file])
    assert not provider.search("click",media_type=MediaType.AUDIO)


def test_ogg_container_mime_only_allowed_for_audio_download():
    from easel.materials.application.acquisition import AcquisitionError
    class Reply:
        def get(self,url,**kwargs):
            return DownloadResponse(200,{'content-type':'application/ogg'},wav_bytes())
    client=MediaDownloader(RemoteURLPolicy(('upload.wikimedia.org',),resolver=lambda *_:('8.8.8.8',)),transport=Reply())
    result=client.download('https://upload.wikimedia.org/wikipedia/commons/example.ogg',media_type='audio')
    assert result.mime=='application/ogg'
    with pytest.raises(AcquisitionError):
        client.download('https://upload.wikimedia.org/wikipedia/commons/example.ogg',media_type='video')


def test_bounded_search_errors_never_leak_source_data():
    provider,calls=_mock_provider("music",[],status=429)
    with pytest.raises(StockUnavailable,match="unavailable") as exc:
        provider.search("music",media_type=MediaType.AUDIO)
    assert len(calls)==1
    assert "query=" not in str(exc.value)
    with pytest.raises(StockUnavailable, match="audio only"):
        provider.search("music",media_type=MediaType.IMAGE)
    assert len(calls)==1
    with pytest.raises(ValueError):
        provider.search("x"*141,media_type=MediaType.AUDIO)


class _AudioTransport:
    def __init__(self):
        self.calls=[]
    def get(self,url,**kw):
        self.calls.append(url)
        return DownloadResponse(200,{"content-type":"audio/wav"},wav_bytes())


def test_audio_supply_downloads_bgm_only_once_and_retains_source_and_credits(tmp_path, monkeypatch):
    # Tests Rights/stock/reuse without requiring FFprobe in ordinary CI.
    # Real FFprobe OGG admission is separately covered below, when installed.
    import wave
    from easel.materials.application.inspector import TechnicalInspector
    from easel.materials.domain import TechnicalInfo, TechnicalStatus
    def inspect_fixture_wav(self, asset):
        path = self._store.resolve_asset_locator(asset.file.path)
        with wave.open(str(path), 'rb') as audio:
            duration = audio.getnframes() / audio.getframerate()
            assert duration > 0 and audio.getnchannels() > 0
        assert path.read_bytes() == wav_bytes()
        return asset.model_copy(update={'technical': TechnicalInfo(
            status=TechnicalStatus.PASSED, mime='audio/wav',
            has_audio=True, duration_seconds=duration)})
    monkeypatch.setattr(TechnicalInspector, 'inspect', inspect_fixture_wav)
    provider,calls=_mock_provider("music",[_file()])
    downstream=_AudioTransport()
    downloader=MediaDownloader(RemoteURLPolicy(provider.allowed_hosts,resolver=lambda *_:("8.8.8.8",)),transport=downstream)
    materials=MaterialService(tmp_path/"library")
    scope=LibraryVisibility(profile_ref="owner")
    context=UseContext(work_id="work-1")
    supplier=MaterialSupply(materials,providers=(provider,),downloaders={provider.provider_id:downloader})
    grant=(provider.provider_id,)
    first=supplier.supply(_need("music"),visibility=scope,context=context,allowed_providers=grant)
    assert len(first.candidates)==1 and first.gap is None
    assert first.candidates[0].asset.rights.attribution_required
    assert len(calls)==len(downstream.calls)==1
    reused=supplier.supply(_need("music"),visibility=scope,context=context,allowed_providers=grant)
    assert len(reused.candidates)==1
    assert reused.candidates[0].library_asset_id==first.candidates[0].library_asset_id
    assert len(calls)==len(downstream.calls)==1


def test_mismatched_commons_source_revision_never_enters_library(tmp_path):
    page=_file();page['imageinfo'][0]['sha1']='f'*40
    provider,calls=_mock_provider('music',[page])
    fetched=_AudioTransport()
    downloader=MediaDownloader(RemoteURLPolicy(provider.allowed_hosts,resolver=lambda *_:('8.8.8.8',)),transport=fetched)
    materials=MaterialService(tmp_path/'library')
    scope=LibraryVisibility(profile_ref='owner');context=UseContext(work_id='work-1')
    result=MaterialSupply(materials,providers=(provider,),downloaders={provider.provider_id:downloader}).supply(
        _need('music'),visibility=scope,context=context,allowed_providers=(provider.provider_id,))
    assert not result.candidates and result.gap and len(fetched.calls)==1
    assert not materials.catalog.list_scope(scope=scope,context=context)


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),
                    reason='OGG media integration requires FFmpeg and FFprobe')
def test_actual_ogg_bytes_pass_download_rights_and_library_inspection(tmp_path):
    available=subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-encoders'],capture_output=True,text=True,timeout=10)
    if ' libopus ' not in available.stdout:
        pytest.skip('OGG fixture requires the libopus audio encoder')
    path=tmp_path/'rain.ogg'
    subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-y',
                    '-f','lavfi','-i','sine=frequency=440:sample_rate=16000',
                    '-t','0.6','-c:a','libopus',str(path)],check=True,timeout=20,capture_output=True)
    data=path.read_bytes()
    page=_file(license='CC0',license_url='https://creativecommons.org/publicdomain/zero/1.0/',
        mime='application/ogg',url='https://upload.wikimedia.org/wikipedia/commons/0/0e/Rain.ogg')
    page['title']='File:Rain.ogg'
    page['imageinfo'][0].update(sha1=sha1(data).hexdigest(),size=len(data))
    provider,_=_mock_provider('sfx',[page])
    class Download:
        def get(self,url,**kwargs):
            return DownloadResponse(200,{'content-type':'application/ogg'},data)
    transport=Download()
    downloader=MediaDownloader(RemoteURLPolicy(provider.allowed_hosts,resolver=lambda *_:('8.8.8.8',)),transport=transport)
    materials=MaterialService(tmp_path/'library')
    scope=LibraryVisibility(profile_ref='owner');context=UseContext(work_id='work-1')
    result=MaterialSupply(materials,providers=(provider,),downloaders={provider.provider_id:downloader}).supply(
        _need('sfx'),visibility=scope,context=context,allowed_providers=(provider.provider_id,))
    assert len(result.candidates)==1 and result.gap is None
    asset=result.candidates[0].asset
    assert asset.technical.status.value=='PASSED'
    assert asset.file.mime=='audio/ogg' and asset.technical.duration_seconds>0.5
    assert materials.catalog.resolve_physical_locator(result.candidates[0].record).is_file()


def test_audio_providers_restrict_role_and_dont_download_wrong_role(tmp_path):
    bgm,bcalls=_mock_provider("music",[_file()])
    effect,scalls=_mock_provider("sfx",[_file()])
    materials=MaterialService(tmp_path/"library")
    context=UseContext(work_id="work-1")
    scope=LibraryVisibility(profile_ref="owner")
    supplier=MaterialSupply(materials,providers=(effect,bgm))
    result=supplier.supply(_need("music"),visibility=scope,context=context,
        allowed_providers=(effect.provider_id,bgm.provider_id))
    assert bcalls and not scalls
    assert result.attempted_sources==(bgm.provider_id,)
    assert not result.candidates    # No downloader fixture for this test: network forbidden.
    # Other direction: do not ask the music provider for a required sound effect.
    assert MaterialSupply(materials,providers=(bgm,)).supply(
        _need("sfx"),visibility=scope,context=context,allowed_providers=(bgm.provider_id,)).attempted_sources==()


def test_wikimedia_download_user_agent_is_configured_for_proxy_and_direct(tmp_path):
    from easel.materials.application.acquisition import MediaDownloader, RemoteURLPolicy
    from types import SimpleNamespace
    output=tmp_path/'outputs';output.mkdir()
    svc=SimpleNamespace(outputs=output)
    configured=configured_supply(svc,None,None,{
        'EASEL_WIKIMEDIA_AUDIO_ENABLED':'1',
        'EASEL_MATERIAL_HTTP_PROXY':'http://127.0.0.1:7897'})
    assert configured.supplier.downloaders['wikimedia_sfx'].user_agent == WikimediaAudioProvider.download_user_agent
    assert configured.supplier.downloaders['wikimedia_bgm'].user_agent == WikimediaAudioProvider.download_user_agent
    assert MediaDownloader(RemoteURLPolicy(('example.com',),resolver=lambda *_:('8.8.8.8',))).user_agent == 'Easel/2 material acquisition'


def test_configuration_adds_two_stock_choices_only_when_enabled(tmp_path):
    outputs=tmp_path/"outputs"
    outputs.mkdir()
    from types import SimpleNamespace
    service=SimpleNamespace(outputs=outputs)
    disabled=configured_supply(service,None,None,{})
    assert not any(p.provider_id.startswith("wikimedia") for p in disabled.external_providers)
    settings={"EASEL_WIKIMEDIA_AUDIO_ENABLED":"1"}
    configured=configured_supply(service,None,None,settings)
    assert [(p.provider_id,p.audio_roles) for p in configured.external_providers]==[
        ("wikimedia_bgm",frozenset({"music"})),("wikimedia_sfx",frozenset({"sfx"}))]
    (tmp_path/".env").write_text("EASEL_WIKIMEDIA_AUDIO_ENABLED=1\n",encoding="utf-8")
    all_services=capabilities(tmp_path)["services"]
    choices=[service for service in all_services if service["provider"].startswith("wikimedia")]
    assert len(choices)==2
    assert all(service["available"] and service["supports_auto_supply"] for service in choices)
