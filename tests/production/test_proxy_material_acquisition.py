"""Security regression for opt-in loopback HTTPS CONNECT material acquisition."""
import ipaddress
import json

import httpx
import pytest

from easel.materials.application.acquisition import AcquisitionError, DownloadResponse, MediaDownloader, RemoteURLPolicy
from easel.materials.application.proxy import PublicDNSOverProxy, ProxyPinnedHttpsTransport, loopback_proxy


@pytest.mark.parametrize('url', [
    'https://127.0.0.1:7897', 'http://example.com:7897', 'http://192.168.1.1:7897',
    'http://127.0.0.1:7897@evil.example:9999', 'http://127.0.0.1:7897/a',
    'http://127.0.0.1:7897/?secret=1', 'socks5://127.0.0.1:7897',
    'http://user:pass@127.0.0.1:7897', 'http://localhost:7897',
    'http://127.0.0.1:0', 'http://127.0.0.1:70000', '',
])
def test_proxy_must_be_explicit_http_loopback_only(url):
    with pytest.raises(ValueError):
        loopback_proxy(url)


def test_valid_loopback_addresses_only():
    assert loopback_proxy('http://127.0.0.1:7897') == ('127.0.0.1', 7897)
    assert loopback_proxy('http://[::1]:7897') == ('::1', 7897)


def _response(name='cdn.example', answer='93.184.216.34', **updates):
    data={'Status':0,'Question':[{'name':name,'type':1}],
          'Answer':[{'name':name,'type':1,'data':answer}]}
    data.update(updates)
    return data


def _resolver(response):
    def handler(request):
        assert request.url.host == '1.1.1.1'
        assert request.headers['accept'] == 'application/dns-json'
        assert request.url.params['name']=='cdn.example'
        return httpx.Response(200, json=response)
    return PublicDNSOverProxy('http://127.0.0.1:7897',transport=httpx.MockTransport(handler))


def test_verified_https_doh_returns_only_public_numeric_ip():
    result=_resolver(_response())('cdn.example',443)
    assert result==('93.184.216.34',)


@pytest.mark.parametrize('address',['198.18.1.52','127.0.0.1','10.1.2.3','169.254.169.254','::1','0.0.0.0'])
def test_doh_never_accepts_fake_private_or_reserved_ips(address):
    with pytest.raises(AcquisitionError):
        _resolver(_response(answer=address))('cdn.example',443)


@pytest.mark.parametrize('response',[
    _response(name='evil.example'),
    _response(Status=1),
    _response(Question=[]),
    _response(Answer=[]),
    _response(Answer=[{'name':'cdn.example','type':1,'data':'93.184.216.34'},
                      {'name':'cdn.example','type':1,'data':'10.0.0.1'}]),
])
def test_doh_rejects_bad_answer_and_question_bindings(response):
    with pytest.raises(AcquisitionError):
        _resolver(response)('cdn.example',443)


def test_proxy_pinned_transport_refuses_unverified_ip_before_connection():
    transport=ProxyPinnedHttpsTransport('http://127.0.0.1:7897')
    with pytest.raises(AcquisitionError):
        transport.get('https://cdn.example/photo.jpg',headers={},timeout=1,max_bytes=100,addresses=('198.18.1.52',))


def test_proxy_policy_still_rejects_host_hijack_and_unsafe_redirect_before_next_connection():
    class FakeTransport:
        def __init__(self): self.urls=[]
        def get(self,url,**kwargs):
            self.urls.append(url)
            return DownloadResponse(302,{'location':'https://127.0.0.1/admin'})
    transport=FakeTransport()
    downloader=MediaDownloader(RemoteURLPolicy(('cdn.example',),resolver=lambda *_:('93.184.216.34',)),
                               transport=transport)
    with pytest.raises(AcquisitionError):
        downloader.download('https://cdn.example/picture',media_type='image')
    assert transport.urls==['https://cdn.example/picture']


def test_proxy_config_does_not_change_regular_default_stock_transport(tmp_path):
    from types import SimpleNamespace
    from easel.production.supply_tasks import configured_supply
    settings={'EASEL_WIKIMEDIA_AUDIO_ENABLED':'1'}
    original=configured_supply(SimpleNamespace(outputs=tmp_path),None,None,settings)
    assert not original.supplier.downloaders
    adapted=configured_supply(SimpleNamespace(outputs=tmp_path),None,None,{
        **settings,'EASEL_MATERIAL_HTTP_PROXY':'http://127.0.0.1:7897'})
    assert {'wikimedia_bgm','wikimedia_sfx'}<=set(adapted.supplier.downloaders)
    for downloader in adapted.supplier.downloaders.values():
        assert isinstance(downloader.transport,ProxyPinnedHttpsTransport)
        assert isinstance(downloader.policy.resolver,PublicDNSOverProxy)
