"""Controlled API transports only; no environment credentials or network."""
import httpx
import pytest
from easel.production.providers.stock import PexelsStockProvider, StockUnavailable
from easel.production.providers.pixabay import PixabayStockProvider
from easel.production.providers.wikimedia_audio import WikimediaAudioProvider
from easel.materials.domain import MediaType


@pytest.mark.parametrize('provider,kind',[(PexelsStockProvider('fake'),MediaType.VIDEO),(PixabayStockProvider('fake'),MediaType.VIDEO),(WikimediaAudioProvider('music'),MediaType.AUDIO)])
@pytest.mark.parametrize('status,code',[(401,'http_permission'),(429,'http_rate_limited'),(503,'http_unavailable')])
def test_search_preserves_safe_http_reason(provider,kind,status,code):
    provider._transport=httpx.MockTransport(lambda r:httpx.Response(status,json={'sensitive':'must not leak'}))
    with pytest.raises(StockUnavailable) as error:provider.search('sample',media_type=kind,limit=1)
    assert error.value.code==code
    assert 'sensitive' not in str(error.value)


@pytest.mark.parametrize('factory,kind',[(lambda **kw:PexelsStockProvider('fake',**kw),MediaType.VIDEO),(lambda **kw:PixabayStockProvider('fake',**kw),MediaType.VIDEO),(lambda **kw:WikimediaAudioProvider('music',**kw),MediaType.AUDIO)])
def test_explicit_proxy_is_passed_without_environment_inheritance(factory,kind,monkeypatch):
    seen=[]
    original=httpx.Client
    def client(**kw):
        seen.append(kw.copy())
        kw.pop('proxy',None)
        return original(**kw)
    monkeypatch.setattr(httpx,'Client',client)
    transport=httpx.MockTransport(lambda r:httpx.Response(200,json={'videos':[],'hits':[],'query':{'pages':[]}}))
    provider=factory(proxy_url='http://127.0.0.1:9876',transport=transport)
    provider.search('sample',media_type=kind,limit=1)
    assert seen[0]['proxy']=='http://127.0.0.1:9876'
    assert seen[0]['trust_env'] is False and seen[0]['follow_redirects'] is False


@pytest.mark.parametrize('error,code',[(httpx.ConnectError('PRIVATE URL KEY'),'network_connection'),(httpx.ReadTimeout('PRIVATE URL KEY'),'network_timeout')])
@pytest.mark.parametrize('factory,kind',[(PexelsStockProvider,MediaType.VIDEO),(PixabayStockProvider,MediaType.VIDEO),(WikimediaAudioProvider,MediaType.AUDIO)])
def test_transport_errors_are_sanitized(factory,kind,error,code):
    def fail(req):raise error
    provider=factory('music' if kind==MediaType.AUDIO else 'fake',transport=httpx.MockTransport(fail))
    with pytest.raises(StockUnavailable) as caught:provider.search('sample',media_type=kind,limit=1)
    assert caught.value.code==code
    assert 'PRIVATE' not in str(caught.value)


def test_configured_search_and_download_share_explicit_proxy(tmp_path):
    from easel.production.supply_tasks import configured_supply
    from easel.production.service import WorkService
    from easel.production.store import Store
    from easel.production.operations import OperationService
    store=Store(tmp_path/'outputs/_production/test.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=tmp_path/'profiles')
    supply=configured_supply(service,OperationService(store),None,{'PEXELS_API_KEY':'fake','PIXABAY_API_KEY':'fake','EASEL_WIKIMEDIA_AUDIO_ENABLED':'1','EASEL_MATERIAL_HTTP_PROXY':'http://127.0.0.1:9876'})
    assert len(supply.supplier.providers)==4
    assert all(p._proxy=='http://127.0.0.1:9876' for p in supply.supplier.providers)
    assert len(supply.supplier.downloaders)==4


@pytest.mark.parametrize('case,expected',[('empty','no_results'),('rights','required_need_rights_unknown'),('download','download_failed'),('network','network_timeout')])
def test_supply_keeps_empty_rights_download_and_network_distinct(tmp_path,case,expected):
    from tests.production.test_material_supply import Provider,need
    from easel.production.materials import MaterialService
    from easel.materials.library import LibraryVisibility,UseContext
    from easel.materials.application.supply import MaterialSupply
    from easel.materials.application.acquisition import AcquisitionError
    from easel.materials.domain import RightsInfo,RightsStatus
    provider=Provider(rights=RightsInfo(status=RightsStatus.UNKNOWN)) if case=='rights' else Provider()
    if case=='empty':provider.search=lambda *a,**kw:()
    if case=='network':
        def search(*a,**kw):raise StockUnavailable('safe',code='network_timeout')
        provider.search=search
    class Downloader:
        def download(self,*a,**kw):raise AcquisitionError('PRIVATE URL')
    result=MaterialSupply(MaterialService(tmp_path/'library'),providers=[provider],downloaders={provider.provider_id:Downloader()}).supply(need(),visibility=LibraryVisibility(profile_ref='fixture'),context=UseContext(work_id='fixture'),allowed_providers=[provider.provider_id])
    assert result.failures[0].reason==expected
    assert 'PRIVATE' not in repr(result)
    assert not result.candidates


def test_voice_replan_marker_forbids_optional_sfx():
    from easel.production.contracts import PlanDocument
    from easel.production.material_intent import MaterialIntent,check_intent
    from easel.production.model_tasks import ModelTaskError
    plan=PlanDocument.model_validate({'title':'测试','summary':'观点','script':'旁白','scenes':[{'id':'s1','purpose':'说明','visual':'桌面'}],'settings':{'duration_seconds':10,'audio_mode':'voice'},'constraints':['本片不使用背景音乐或可选音效']})
    intent=MaterialIntent.model_validate({'visuals':[{'scene_id':'s1','query':'desk','media_types':['image']}], 'sound_cues':[{'cue_id':'cue','scene_id':'s1','query':'click','at':1,'duration':.1,'required':False,'basis':'optional'}]})
    with pytest.raises(ModelTaskError):check_intent(intent,plan)
