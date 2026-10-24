import io
import json
import shutil
import subprocess

import pytest
from PIL import Image
from fastapi import FastAPI
from fastapi.testclient import TestClient

from easel.production.publication_covers import prepare_cover, cover_path
from easel.production.media import file_sha256
from easel.production.errors import ProductionError
from easel.publication_bilibili import BilibiliSession, biliup_command
from web.publication_api import create_publication_router
from web.production_api import production_error_handler
from tests.production.test_publication import publication, send
from tests.production.test_revision_acceptance import prepared


def image_bytes():
    buffer=io.BytesIO();Image.new('RGB',(1200,700),'#27689c').save(buffer,format='PNG');return buffer.getvalue()


def choose(p,d):
    cover=prepare_cover(p,d['id'],d['revision'],data=image_bytes())
    return p.save(d['id'],d['revision'],{**d['content'],'cover':cover})


def test_candidate_preview_save_confirmation_and_upload_share_cover(publication,tmp_path,monkeypatch):
    p,a,d=publication
    cover=prepare_cover(p,d['id'],d['revision'],data=image_bytes())
    assert p.get(d['id'])['confirmation_hash']==d['confirmation_hash']
    assert p.get(d['id'])['content']['cover'] is None and a.calls==0
    path=cover_path(p,d,cover)
    with Image.open(path) as image:assert image.size==(1200,700) and image.format=='JPEG'
    saved=p.save(d['id'],d['revision'],{**d['content'],'cover':cover})
    assert saved['confirmation_hash']!=d['confirmation_hash']
    with pytest.raises(ProductionError):send(p,d)
    assert a.calls==0
    staged=[]
    monkeypatch.setattr(a,'stage_cover',lambda path,checksum:staged.append((path.read_bytes(),checksum)),raising=False)
    sent=send(p,saved)
    assert a.calls==1 and staged==[(path.read_bytes(),cover['digest'])]
    assert sent['attempts'][-1]['content']['cover']==cover
    send(p,saved);assert a.calls==1
    with pytest.raises(ProductionError):prepare_cover(p,saved['id'],saved['revision'],data=image_bytes())
    session=BilibiliSession(tmp_path,tmp_path/'cookies.json')
    staged_path=session.stage_cover(path,cover['digest'])
    assert staged_path.read_bytes()==path.read_bytes()
    command=biliup_command(tmp_path/'cookies.json',tmp_path/'video.mp4',saved['content'],staged_path)
    assert command[command.index('--cover')+1]==str(staged_path)


def test_cover_bytes_changed_blocks_before_upload(publication,monkeypatch):
    p,a,d=publication;saved=choose(p,d)
    cover_path(p,saved,saved['content']['cover']).write_bytes(image_bytes())
    with pytest.raises(ProductionError) as error:send(p,saved)
    assert error.value.code=='cover_changed' and a.calls==0
    assert not p.get(d['id'])['attempts']


def test_library_image_and_path_boundaries(publication):
    p,a,d=publication
    source=p.service.outputs/'local-image.png';source.write_bytes(image_bytes())
    cover=prepare_cover(p,d['id'],d['revision'],library_path='local-image.png')
    assert cover_path(p,d,cover).is_file()
    source.unlink()  # selected candidate is an immutable copy, not a dangling path
    assert cover_path(p,d,cover).is_file()
    for path in ['../cookies.json','/etc/passwd','_production/production.sqlite3','works/private/image.png']:
        with pytest.raises(ProductionError):prepare_cover(p,d['id'],d['revision'],library_path=path)
    linked=p.service.outputs/'linked.png';linked.symlink_to(cover_path(p,d,cover))
    with pytest.raises(ProductionError):prepare_cover(p,d['id'],d['revision'],library_path='linked.png')
    with pytest.raises(ProductionError):cover_path(p,{**d,'id':'another_draft'},cover)
    with pytest.raises(ProductionError):prepare_cover(p,d['id'],d['revision'],data=b'not an image')
    with pytest.raises(ProductionError):prepare_cover(p,d['id'],d['revision'],data=image_bytes(),at=0)
    assert a.calls==0


def test_remove_cover_and_existing_no_cover_record(publication):
    p,a,d=publication;saved=choose(p,d)
    cleared=p.save(d['id'],saved['revision'],{**saved['content'],'cover':None})
    assert '--cover' not in biliup_command('cookie','video',cleared['content'])
    # Old persisted records have no cover key: reading must not mutate old hashes.
    old_content={k:v for k,v in cleared['content'].items() if k!='cover'}
    with p.store.transaction() as c:c.execute('update publication_drafts set content_json=? where id=?',(json.dumps(old_content),d['id']))
    before=p.get(d['id']);assert 'cover' not in before['content']
    assert p.get(d['id'])['confirmation_hash']==before['confirmation_hash']
    assert choose(p,before)['content']['cover']


def test_real_frame_uses_accepted_video_without_production_job(publication,tmp_path,monkeypatch):
    if not shutil.which('ffmpeg'):pytest.skip('ffmpeg unavailable')
    p,a,d=publication
    with p.store.connection() as c:
        _,_,_,path=p._source(c,d['work_id'],d['output_id'],d['acceptance_id'])
        before={table:c.execute(f'select count(*) from {table}').fetchone()[0] for table in ['runs','tasks','operations','artifacts']}
    video=tmp_path/'sample.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=320x180:r=10:d=1','-c:v','libx264','-pix_fmt','yuv420p',str(video)],check=True)
    # Source identity/digest checks are covered separately; exercise real local decoding here.
    monkeypatch.setattr(p,'_source',lambda *args:(None,None,None,video))
    cover=prepare_cover(p,d['id'],d['revision'],at=.4)
    with Image.open(cover_path(p,d,cover)) as image:
        red,green,blue=image.getpixel((100,100));assert red>200 and green<30 and blue<30
    with pytest.raises(ProductionError):prepare_cover(p,d['id'],d['revision'],at=2)
    with p.store.connection() as c:
        assert before=={table:c.execute(f'select count(*) from {table}').fetchone()[0] for table in before}
    assert a.calls==0


def test_cover_http_upload_preview_and_submitted_protection(publication):
    p,a,d=publication;app=FastAPI();app.add_exception_handler(ProductionError,production_error_handler)
    app.include_router(create_publication_router(lambda:p.service,lambda:a));client=TestClient(app)
    url='/api/production/publications/'+d['id']
    result=client.post(url+'/covers/upload',data={'revision':d['revision']},files={'file':('cover.png',image_bytes(),'image/png')})
    assert result.status_code==200;cover=result.json()
    preview=client.get(url+'/covers/'+cover['digest']);assert preview.status_code==200 and preview.headers['content-type']=='image/jpeg'
    saved=client.put(url,json={'revision':d['revision'],'content':{**d['content'],'cover':cover}})
    assert saved.status_code==200
    assert client.post(url+'/covers',json={'revision':saved.json()['revision'],'at':-1}).status_code==422
    with p.store.transaction() as c:c.execute("update publication_drafts set state='submitted' where id=?",(d['id'],))
    assert client.post(url+'/covers/upload',data={'revision':saved.json()['revision']},files={'file':('cover.png',image_bytes(),'image/png')}).status_code==409
    assert client.get(url+'/covers/'+cover['digest']).status_code==200 and a.calls==0
