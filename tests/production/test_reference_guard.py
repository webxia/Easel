from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from web import app as web


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(web,'OUTPUTS_DIR',tmp_path)
    (tmp_path/'_production').mkdir()
    (tmp_path/'_production/production.sqlite3').write_text('private')
    (tmp_path/'works/work').mkdir(parents=True)
    (tmp_path/'works/work/preview.mp4').write_bytes(b'preview')
    (tmp_path/'normal').mkdir()
    (tmp_path/'normal/public.txt').write_text('public')
    return TestClient(web.app,base_url='http://127.0.0.1:7860',client=('127.0.0.1',5000)),tmp_path


@pytest.mark.parametrize('endpoint',['output','media'])
@pytest.mark.parametrize('path',['_production/production.sqlite3','%5Fproduction/production.sqlite3','works/work/preview.mp4'])
def test_legacy_read_rejects_managed_files(client,endpoint,path):
    c,_=client
    assert c.get(f'/api/{endpoint}/{path}').status_code==403


def test_aliases_and_nested_enumeration(client):
    c,root=client
    try:
        (root/'alias').symlink_to(root/'_production',target_is_directory=True)
        (root/'normal/leak').symlink_to(root/'_production',target_is_directory=True)
    except OSError:pytest.skip('symlink privileges unavailable')
    assert c.get('/api/media/alias/production.sqlite3').status_code==403
    assert c.get('/api/output/normal/leak/production.sqlite3').status_code==403
    tree=c.get('/api/outputs').json()
    assert len(tree)==1 and tree[0]['name']=='normal'
    assert [v['name'] for v in tree[0]['children']]==['public.txt']
    assert c.delete('/api/output/alias/production.sqlite3').status_code==403


def test_old_regular_output_still_readable(client):
    c,_=client
    assert c.get('/api/output/normal/public.txt').json()['content']=='public'
    assert c.get('/api/artifacts/archive?path=_production/production.sqlite3').status_code==403
