"""Original supply first, optional local SFX recall; no remote model or media."""
from datetime import datetime, timezone
import json
import struct

import pytest

from easel.materials.application.supply import MaterialSupply
from easel.materials.audio_search import audio_action_conflict
from easel.materials.domain import (CandidateSource, MaterialNeed, MediaType, NeedImportance,
    NeedIntent, NeedScope, NeedScopeType, RightsEvidence, RightsInfo, RightsStatus, SemanticInfo)
from easel.materials.library import LibraryVisibility, PromotionConsent, UseContext
from easel.production.materials import MaterialService
from .test_voice_subtitles import wav_bytes


class Embedding:
    provider_id = 'fixture'
    model_version = 'one'
    dimensions = 2
    minimum_score = .8

    def __init__(self):
        self.calls = 0
        self.fail = False

    def embed(self, text):
        self.calls += 1
        if self.fail:
            raise RuntimeError('private-token must not leak')
        return (0., 1.) if text == 'no-match' else (1., 0.)


@pytest.fixture
def env(tmp_path):
    svc = MaterialService(tmp_path.resolve() / 'library')
    return svc, LibraryVisibility(profile_ref='profile-a'), UseContext(work_id='work'), tmp_path.resolve()


def ingest(env, title, *, roles=('sfx',), rights=None, scope=None):
    svc, visibility, ctx, root = env
    count = len(svc.catalog.metadata_search(scope=visibility, context=ctx))
    source = root / f'{count}.wav'
    # Different PCM bytes retain independent candidates rather than deduping fixtures.
    body = bytearray(wav_bytes()); body[-2:] = struct.pack('<h', count + 1); source.write_bytes(body)
    return svc.ingest_input(source_root=root, relative_path=source.name, visibility=scope or visibility,
        context=ctx, media_type=MediaType.AUDIO,
        source=CandidateSource(kind='local_import', provider='fixture', provider_asset_id=source.name),
        rights=rights or RightsInfo(status=RightsStatus.KNOWN, license_name='fixture',
            evidence=(RightsEvidence(kind='asset_permission', reference='fixture:owned',
                observed_at=datetime.now(timezone.utc)),)),
        semantic=SemanticInfo(caption=title, attributes={'audio_roles': list(roles)}))


def need(query='翻翻资料的声音', *, options=1, role='sfx'):
    return MaterialNeed(need_id='cue', scope=NeedScope(type=NeedScopeType.EVENT, ref='cue'),
        media_type=MediaType.AUDIO, role=role, intent=NeedIntent(description=query),
        importance=NeedImportance.OPTIONAL, desired_options=options)


def index(env, provider, handle):
    svc, scope, ctx, _ = env
    r = svc.catalog.get(handle.asset_ref, scope=scope, context=ctx)
    svc.index.index_record(r, provider)


def supply(env, provider, requirement=None, **kwargs):
    svc, scope, ctx, _ = env
    return MaterialSupply(svc, sfx_embedding_provider=provider).supply(requirement or need(),
        visibility=scope, context=ctx, **kwargs)


def test_original_sufficient_does_not_call_model_or_change_order(env):
    ingest(env, 'Book Pages Turning'); ingest(env, 'Magazine Page Turn')
    base = supply(env, None, need('翻页声'))
    provider = Embedding()
    result = supply(env, provider, need('翻页声'))
    assert result == base and len(result.candidates) == 2 and provider.calls == 0


def test_semantic_miss_supplements_via_original_select(env):
    h = ingest(env, 'Book Pages Turning'); provider = Embedding(); index(env, provider, h)
    assert not supply(env, None).candidates
    result = supply(env, provider)
    assert [c.library_asset_id for c in result.candidates] == [h.asset_ref]
    svc, scope, ctx, _ = env
    assert svc.select(h.asset_ref, need(), visibility=scope, context=ctx,
        reference_id='selected').local_path.is_file()


def test_append_keeps_original_prefix_and_respects_exclusion(env):
    one = ingest(env, 'Book Page Turn'); two = ingest(env, 'Foley Leaf Through Sheets')
    provider = Embedding(); index(env, provider, one); index(env, provider, two)
    result = supply(env, provider, need('page turn', options=2))
    assert [c.library_asset_id for c in result.candidates] == [one.asset_ref, two.asset_ref]
    assert not supply(env, provider, excluded_asset_refs=(one.asset_ref, two.asset_ref)).candidates


def test_required_reference_never_replaced_and_exact_source_skips_semantics(env):
    provider = Embedding()
    assert supply(env, provider, required_asset_refs=('missing',)).gap == 'required_material_unavailable'
    assert not supply(env, provider, need('https://example.test/exact')).candidates
    assert provider.calls == 0


@pytest.mark.parametrize('condition', ['disabled', 'failed', 'no-match', 'unindexed', 'stale', 'corrupt'])
def test_no_semantic_result_keeps_original_external_fallback(env, condition):
    h = ingest(env, 'Book Pages Turning'); provider = Embedding()
    if condition != 'unindexed': index(env, provider, h)
    if condition == 'failed': provider.fail = True
    if condition == 'stale': provider.model_version = 'changed'
    if condition == 'corrupt':
        with env[0].index._connect() as db: db.execute("UPDATE semantic_vectors SET vector_json='[1]'")
    class External:
        provider_id = 'external'
        allowed_hosts = ('example.test',)
        audio_roles = ('sfx',)
        calls = 0
        def search(self, *args, **kwargs):
            self.calls += 1
            return ()
    external = External()
    result = MaterialSupply(env[0], providers=(external,), sfx_embedding_provider=None if condition=='disabled' else provider).supply(
        need('no-match' if condition=='no-match' else '翻翻资料的声音'), visibility=env[1], context=env[2],
        allowed_providers=('external',))
    assert not result.candidates and result.gap and external.calls == 1
    assert result.failures and all(f.reason=='no_results' for f in result.failures)
    if condition not in {'disabled','no-match'}:
        assert result.search_diagnostics
    assert 'private-token' not in repr(result)


def test_partial_index_does_not_discard_fresh_result(env):
    h = ingest(env, 'Book Pages Turning'); ingest(env, 'Paper Rustle')
    provider = Embedding(); index(env, provider, h)
    assert [c.library_asset_id for c in supply(env, provider).candidates] == [h.asset_ref]


def test_shared_vectors_use_original_scope_without_cross_owner_access(env):
    svc, scope, ctx, _ = env
    shared_scope = LibraryVisibility()
    h = ingest(env, 'Book Pages Turning', scope=shared_scope)
    svc.catalog.promote(h.asset_ref, scope=shared_scope, context=ctx, owner_shared=True, consent=PromotionConsent(
        authorized=True, actor_id='fixture', purpose='owner_shared_import', consented_at=datetime.now(timezone.utc)))
    provider = Embedding()
    r = svc.catalog.get(h.asset_ref, scope=shared_scope, context=ctx)
    svc.index.index_record(r, provider)
    result = supply(env, provider)
    assert result.candidates[0].library_asset_id == h.asset_ref
    other = svc.candidates(need(), visibility=LibraryVisibility(owner_id='other'), context=ctx,
        query=need().intent.description, embedding_provider=provider, semantic_supplement=True)
    assert not other.candidates


@pytest.mark.parametrize('title,query', [('Book Close Book','翻页声'), ('Door Close','打开门'),
    ('Keyboard Single Hit','连续打字'), ('Glass Break','放杯'), ('Pencil Erase On Paper','写字')])
def test_source_action_conflicts_survive_semantic_rank(env, title, query):
    h = ingest(env, title); provider = Embedding(); index(env, provider, h)
    assert audio_action_conflict(query, title)
    assert not supply(env, provider, need(query)).candidates
    assert not audio_action_conflict('未收录词义', title)


@pytest.mark.parametrize('role', ['music', 'voice'])
def test_other_audio_roles_do_not_invoke_semantics(env, role):
    h = ingest(env, 'Book Pages Turning'); provider = Embedding(); index(env, provider, h)
    before = provider.calls
    assert not supply(env, provider, need(role=role)).candidates
    assert provider.calls == before


def test_rights_missing_files_and_deleted_vectors_cannot_reappear(env):
    svc, scope, ctx, _ = env
    h = ingest(env, 'Book Pages Turning', rights=RightsInfo(status=RightsStatus.UNKNOWN))
    provider = Embedding(); index(env, provider, h)
    assert not supply(env, provider).candidates
    h.local_path.unlink()
    assert not supply(env, provider).candidates
    with svc.catalog._connect() as db:
        raw = json.loads(db.execute('SELECT record_json FROM library_assets WHERE library_asset_id=?',(h.asset_ref,)).fetchone()[0])
        raw['lifecycle_status']='DELETED'
        db.execute("UPDATE library_assets SET lifecycle_status='DELETED',record_json=? WHERE library_asset_id=?",(json.dumps(raw),h.asset_ref))
    assert not supply(env, provider).candidates


def test_full_rebuild_pages_and_skips_fresh_records(env):
    from types import SimpleNamespace
    from easel.materials.semantic_index import MaterialSemanticIndex
    records = [SimpleNamespace(library_asset_id=f'{i:04}',asset=SimpleNamespace(semantic=SimpleNamespace(attributes={'audio_roles':['sfx']}))) for i in range(1415)]
    class Catalog:
        def list_scope(self, *, after_asset_id, limit, **kwargs):
            return tuple(r for r in records if r.library_asset_id > after_asset_id)[:limit]
    idx=MaterialSemanticIndex.__new__(MaterialSemanticIndex);idx.catalog=Catalog()
    idx.index_record=lambda r,p:r.library_asset_id
    idx.is_stale=lambda r,p:r.library_asset_id=='1414'
    assert len(idx.rebuild(env[1],Embedding(),context=env[2],audio_role='sfx'))==1415
    assert idx.rebuild(env[1],Embedding(),context=env[2],audio_role='sfx',skip_fresh=True)==('1414',)


def test_configuration_is_optional_and_model_load_is_lazy(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace
    from easel.materials.local_embedding import LocalSfxEmbedding, configured_sfx_embedding
    root=tmp_path.resolve();(root/'easel-model-identity.json').write_text(json.dumps({
        'model_id':'BAAI/bge-m3','revision':'fixture','dimensions':1024}))
    assert configured_sfx_embedding({}) is None
    assert configured_sfx_embedding({'EASEL_SFX_SEMANTIC_ENABLED':'1'}) is None
    calls=[]
    class Model:
        def __init__(self, path, **kwargs): calls.append(kwargs)
        def get_sentence_embedding_dimension(self): return 1024
        def encode(self, text, **kwargs): return SimpleNamespace(tolist=lambda:[1.]*1024)
    monkeypatch.setitem(sys.modules,'sentence_transformers',SimpleNamespace(SentenceTransformer=Model))
    monkeypatch.setattr('importlib.metadata.version',lambda name:'fixture')
    p=LocalSfxEmbedding(root,minimum_score=.8)
    assert not calls
    p.embed('one');p.embed('two')
    assert len(calls)==1 and calls[0]['local_files_only'] and not calls[0]['trust_remote_code']


def test_configured_supply_wires_only_sfx_supplement(env, monkeypatch):
    from types import SimpleNamespace
    from easel.production.supply_tasks import configured_supply
    provider = Embedding()
    monkeypatch.setattr('easel.materials.local_embedding.configured_sfx_embedding',lambda settings:provider)
    task = configured_supply(SimpleNamespace(outputs=env[3]),None,None,{})
    assert task.supplier.sfx_embedding_provider is provider
    assert not task.external_providers


def test_model_load_failure_is_local_and_does_not_repeat(env, monkeypatch):
    import sys
    from types import SimpleNamespace
    from easel.materials.local_embedding import LocalSfxEmbedding
    root=env[3];(root/'easel-model-identity.json').write_text(json.dumps({
        'model_id':'BAAI/bge-m3','revision':'fixture','dimensions':1024}))
    calls=[]
    def broken(*args, **kwargs):
        calls.append(1)
        raise OSError('private details')
    monkeypatch.setitem(sys.modules,'sentence_transformers',SimpleNamespace(SentenceTransformer=broken))
    monkeypatch.setattr('importlib.metadata.version',lambda name:'fixture')
    provider=LocalSfxEmbedding(root,minimum_score=.8)
    for _ in range(2):
        with pytest.raises(RuntimeError,match='^Local embedding unavailable$'):provider.embed('test')
    assert len(calls)==1


def test_semantic_insufficient_cannot_authorize_external_requests(env):
    class External:
        provider_id='external';allowed_hosts=('example.test',);calls=0
        def search(self,*args,**kwargs):self.calls+=1;return ()
    external=External()
    r=MaterialSupply(env[0],providers=(external,),sfx_embedding_provider=Embedding()).supply(
        need(),visibility=env[1],context=env[2])
    assert r.gap and external.calls==0


def test_shared_asset_requires_consent_even_when_vector_exists(env):
    svc,scope,ctx,_=env
    shared=LibraryVisibility()
    h=ingest(env,'Book Pages Turning',scope=shared)
    provider=Embedding()
    svc.index.index_record(svc.catalog.get(h.asset_ref,scope=shared,context=ctx),provider)
    assert not supply(env,provider).candidates


def test_music_or_voice_material_cannot_fill_sfx_from_semantic_similarity(env):
    provider=Embedding()
    for role in ['music','voice']:
        h=ingest(env,'Inleiding Spark Of Being (audio)',roles=(role,));index(env,provider,h)
    assert not supply(env,provider).candidates


def test_index_projection_uses_source_caption_and_preserves_metadata():
    from types import SimpleNamespace
    from easel.materials.local_embedding import LocalSfxEmbedding
    asset=SimpleNamespace(semantic=SimpleNamespace(caption='Household Book Soft Cover Pages Turning 14',
        tags=('unrelated paths',),attributes={'original_relative_path':'private/path'}))
    assert LocalSfxEmbedding.document_text(asset)=='Book Soft Cover Pages Turning'
    assert asset.semantic.caption=='Household Book Soft Cover Pages Turning 14'


def test_projection_is_shared_by_indexing_and_staleness(env):
    svc,scope,ctx,_=env
    h=ingest(env,'Book Pages Turning');provider=Embedding()
    provider.document_text=lambda asset:'sound:'+asset.semantic.caption
    index(env,provider,h)
    record=svc.catalog.get(h.asset_ref,scope=scope,context=ctx)
    assert not svc.index.is_stale(record,provider)
    provider.document_text=lambda asset:'changed:'+asset.semantic.caption
    assert svc.index.is_stale(record,provider)


@pytest.mark.parametrize('failure,expected_empty',[('no_results',True),('network_timeout',False)])
def test_local_index_diagnostic_does_not_change_original_sound_recovery(failure,expected_empty):
    from contextlib import nullcontext
    from types import SimpleNamespace as NS
    from easel.materials.application.supply import MaterialSupplyResult,SupplyFailure
    from easel.production.supply_tasks import SupplyTasks,SoundSearchEmpty
    from easel.production.errors import ProductionError
    result=MaterialSupplyResult((),(),('external',),(SupplyFailure('external',failure),),
        gap='insufficient_eligible_materials',search_diagnostics=(SupplyFailure('local_sfx_semantic','embedding_index_incomplete'),))
    task=SupplyTasks.__new__(SupplyTasks);task.supplier=NS(supply=lambda *args,**kwargs:result)
    task._allowed_providers=lambda *args:('external',)
    task._check_provider=lambda *args:None
    ctx=NS(work_id='work',run_id='run',assert_current=lambda:None,
        transaction=lambda:nullcontext(None),store=NS(append_event=lambda *args,**kwargs:None))
    cue=NS(cue_id='cue',scene_id='scene',at=0.,duration=1.,required=True,query='unknown',basis='fixture',timing_basis='absolute')
    with pytest.raises(ProductionError) as exc:
        task._acquire_sfx(ctx,NS(narration_policy=None),[],LibraryVisibility(),UseContext(work_id='work'),NS(sound_cues=[cue]))
    assert isinstance(exc.value,SoundSearchEmpty) is expected_empty
