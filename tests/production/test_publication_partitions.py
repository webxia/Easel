"""Upload-category catalog uses the native login and never mutates drafts."""
from types import SimpleNamespace
import pytest
from easel import publication_partitions as categories

@pytest.fixture(autouse=True)
def clear_cache():
    categories._cache.clear()
    yield
    categories._cache.clear()


def test_catalog_sanitizes_private_fields():
    assert categories.normalize_partitions([
        {'id':36,'name':' 知识 ','private':'secret','children':[
            {'id':228,'name':'人文历史','private':'secret'},
            {'id':9,'name':'hidden','show':False}]},
        {'id':True,'name':'invalid'},None,{'id':0,'name':'invalid'},
    ])==[{'id':36,'name':'知识','children':[{'id':228,'name':'人文历史','children':[]}]}]


def test_live_catalog_cached_refresh_and_login_change(tmp_path,monkeypatch):
    cookie=tmp_path/'cookies.json';cookie.write_text('test')
    calls=[]
    def request(path,url,**kwargs):
        calls.append((path,url,kwargs))
        return {'code':0,'data':{'account':'private','typelist':[{'id':36,'name':'知识'}]}}
    monkeypatch.setattr(categories.platform_readback,'_bilibili_api',request)
    a=categories.partitions(tmp_path)
    assert a['source']=='bilibili' and 'private' not in str(a)
    assert categories.partitions(tmp_path)==a and len(calls)==1
    categories.partitions(tmp_path,refresh=True);assert len(calls)==2
    cookie.write_text('new-login');categories.partitions(tmp_path);assert len(calls)==3
    assert calls[0][0]==cookie and calls[0][1].endswith('/x/vupre/web/archive/pre')
    assert calls[0][2]=={'timeout_s':5}


def test_missing_login_or_remote_failure_uses_existing_native_categories(tmp_path,monkeypatch):
    monkeypatch.setattr(categories,'_native_builder',lambda:SimpleNamespace(__globals__={'PARTITIONS':{'本机分区':36}}))
    def request(*args,**kwargs):raise RuntimeError('private token must never escape')
    monkeypatch.setattr(categories.platform_readback,'_bilibili_api',request)
    for logged_in in [False,True]:
        if logged_in:(tmp_path/'cookies.json').write_text('test')
        result=categories.partitions(tmp_path,refresh=True)
        assert result['source']=='local' and result['groups']==[{'id':36,'name':'本机分区','children':[]}]
        assert 'private token' not in str(result)


def test_file_command_uses_selected_upload_tid_and_preserves_default():
    import web.app as web
    for tid in [36,228,99999]:
        request=web.PublishRequest(title='测试',tid=tid)
        cmd=web._native_publish_command('bilibili',request,[],['video.mp4'],web.LOGIN_RUNNERS['bilibili'])
        assert cmd[cmd.index('--tid')+1]==str(tid)
    assert web.PublishRequest().tid==36
    for invalid in [0,-1,True,1.5,'36']:
        with pytest.raises(ValueError):web.PublishRequest(tid=invalid)


def test_catalog_route_precedes_record_identity_and_is_read_only(tmp_path,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from web.publication_api import create_publication_router
    calls=[]
    monkeypatch.setattr(categories,'partitions',lambda root,refresh=False:calls.append((root,refresh)) or {'groups':[],'source':'local','message':'fallback'})
    app=FastAPI();app.include_router(create_publication_router(lambda:SimpleNamespace(outputs=tmp_path/'outputs')))
    result=TestClient(app).get('/api/production/publications/partitions?refresh=true')
    assert result.status_code==200 and result.json()['source']=='local'
    assert calls==[(tmp_path,True)]
