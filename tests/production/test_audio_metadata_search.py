from types import SimpleNamespace as NS
from datetime import datetime, timezone
import pytest
from easel.materials.audio_search import score_audio
from easel.materials.semantic_index import MaterialSemanticIndex

@pytest.mark.parametrize('query,good,bad', [
 ('玻璃杯轻放在桌面上','Glass Set Down On Table','Glass Vase Break On Cement'),
 ('慢慢打开卧室门','Door Open Bedroom','Door Close Bedroom'),
 ('电脑键盘打字声','Computer Keyboard Typing','Keyboard Single Hit'),
 ('glass break','Glass Plate Break','Glass Fall Does Not Break'),
 ('关闭房间门','Door Closing Room','Door Open Room'),
])
def test_action_identity(query, good, bad):
    assert score_audio(query,good,good)>0
    assert score_audio(query,bad,bad)==0

def test_broad_import_tags_cannot_make_single_keystroke_continuous():
    assert score_audio('keyboard typing','Keyboard Single Hit','keyboard typing 键盘 打字')==0

def test_unknown_query_uses_generic_retrieval():
    assert score_audio('volcano','Volcano eruption','') is None

def record(i,title):
    return NS(library_asset_id=f'{i:05}',created_at=datetime(2026,1,1,tzinfo=timezone.utc),
        asset=NS(media_type=NS(value='audio'),semantic=NS(caption=title,tags=(),attributes={},inferences=())))

def test_search_pages_before_ranking_even_when_topk_is_one():
    data=[record(i,'Unrelated') for i in range(1000)]+[record(1000,'Computer Keyboard Typing')]
    class Catalog:
        def metadata_search(self,*,after_asset_id,limit,**kwargs):
            return tuple(x for x in data if x.library_asset_id>after_asset_id)[:limit]
    idx=MaterialSemanticIndex.__new__(MaterialSemanticIndex);idx.catalog=Catalog()
    found=idx.search('电脑键盘打字声',scope=None,context=None,provider=None,limit=1,metadata_filters={'limit':1000})
    assert [x.record.library_asset_id for x in found.hits]==['01000']

def test_catalog_cursor_keeps_visibility_and_filters(tmp_path):
    from PIL import Image
    from easel.production.materials import MaterialService
    from easel.materials.library import LibraryVisibility, UseContext
    from easel.materials.domain import CandidateSource, MediaType, RightsInfo, RightsStatus
    Image.new('RGB',(4,4)).save(tmp_path/'x.png')
    svc=MaterialService(tmp_path/'library');scope=LibraryVisibility(owner_id='test');ctx=UseContext(work_id='work')
    for name in ['one','two','three']:
        svc.ingest_input(source_root=tmp_path,relative_path='x.png',visibility=scope,context=ctx,
            media_type=MediaType.IMAGE,source=CandidateSource(kind='user_upload',provider_asset_id=name),
            rights=RightsInfo(status=RightsStatus.UNKNOWN))
    first=svc.catalog.metadata_search(scope=scope,context=ctx,limit=2)
    second=svc.catalog.metadata_search(scope=scope,context=ctx,limit=2,after_asset_id=first[-1].library_asset_id)
    assert len(first)==2 and len(second)==1
    assert set(x.library_asset_id for x in first).isdisjoint(x.library_asset_id for x in second)
    assert not svc.catalog.metadata_search(scope=LibraryVisibility(owner_id='other'),context=ctx,after_asset_id='')
