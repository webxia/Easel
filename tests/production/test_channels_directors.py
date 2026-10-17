import json
import pytest
from easel.production.store import Store
from easel.production.service import WorkService
from easel.production.catalog import CreativeCatalog
from easel.production.errors import ProductionError


@pytest.fixture
def setup(tmp_path):
    profiles=tmp_path/'profiles';(profiles/'person').mkdir(parents=True)
    (profiles/'person/identity.md').write_text('same person')
    store=Store(tmp_path/'outputs/_production/production.sqlite3');store.initialize()
    service=WorkService(store,outputs=tmp_path/'outputs',profiles=profiles)
    catalog=CreativeCatalog(service)
    return service,catalog


def test_one_existing_profile_many_channels_reusable_director_defaults(setup):
    service,catalog=setup
    channels=[catalog.command('channels','create',{'name':name,'profile_ref':'person'},command_id=name)['id'] for name in ['finance','AI']]
    work_id=service.command('create',{'title':'trial'},command_id='trial')['work_id']
    with service.store.transaction() as conn:
        conn.execute("INSERT INTO artifacts(id,work_id,kind,storage_ref,digest,size_bytes,created_at) VALUES ('trial',?,'output','works/trial.mp4',?,1,'now')",(work_id,'0'*64))
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('d','style','now','now')")
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,style_confirmed,trial_artifact_id,accepted_at,created_at) VALUES ('v','d',1,?, ?,1,'trial','accepted','now')",(json.dumps({'schema_version':1,'visual_style':'cinematic','storytelling':'variable'}),json.dumps([{'input_id':'original-reference'}])))
    for id in channels:
        catalog.command('channels','edit',{'director_ids':['d'],'default_director_revision':'v'},id=id,expected_revision=1,command_id=id)
    values=catalog.list('channels')
    assert len({c['profile_ref'] for c in values})==1
    assert all(c['director_ids']==['d'] and c['default_director_revision']=='v' for c in values)
    with service.store.connection() as conn:assert conn.execute('SELECT count(*) FROM profile_refs').fetchone()[0]==1
    # Clearing a relation must explicitly clear default rather than leave a dangling style.
    with pytest.raises(ProductionError):catalog.command('channels','edit',{'director_ids':[]},id=channels[0],expected_revision=2,command_id='clear')


def test_no_blank_director_or_forged_reference_revision(setup):
    service,catalog=setup
    with pytest.raises(ProductionError):catalog.command('directors','create',{'name':'blank'},command_id='blank')
    with service.store.transaction() as conn:
        conn.execute("INSERT INTO directors(id,name,created_at,updated_at) VALUES ('d','style','now','now')")
        conn.execute("INSERT INTO director_revisions(id,director_id,revision,style_json,evidence_json,created_at) VALUES ('v','d',1,?,?,'now')",(json.dumps({'schema_version':1}),json.dumps([{'input_id':'real'}])))
    with pytest.raises(ProductionError):
        catalog.command('directors','revision',{'style':{'visual_style':'x','storytelling':'y'},'evidence':[{'input_id':'fake'}]},id='d',expected_revision=1,command_id='forged')
    result=catalog.command('directors','revision',{'style':{'visual_style':'x','storytelling':'y'},'evidence':[{'input_id':'real'}]},id='d',expected_revision=1,command_id='edit')
    assert result['revision']==2
    assert len(catalog.list('directors')[0]['versions'])==2


def test_deleted_profile_name_never_reuses_old_identity_or_defaults(setup):
    import shutil
    from easel.production.service import retire_profile_reference
    service,catalog=setup
    work=service.command('create',{'title':'old','profile_ref':'person'},command_id='old')['work_id']
    with service.store.transaction() as conn:
        old=conn.execute('SELECT profile_ref FROM works WHERE id=?',(work,)).fetchone()[0]
        conn.execute("UPDATE works SET deleted_at='deleted' WHERE id=?",(work,))
        conn.execute('UPDATE profile_refs SET settings_json=? WHERE id=?',(json.dumps({'schema_version':1,'duration_seconds':99}),old))
    retire_profile_reference(service.store.path,'person',lambda:shutil.rmtree(service.profiles/'person'))
    (service.profiles/'person').mkdir()
    fresh=service.command('create',{'title':'new','profile_ref':'person'},command_id='new')['work_id']
    snap=service.snapshot(fresh)
    assert snap['profile_ref']!=old and 'duration_seconds' not in snap['settings']
    with pytest.raises(ProductionError):service.command('create',{'title':'old-id','profile_ref':old},command_id='old-id')
