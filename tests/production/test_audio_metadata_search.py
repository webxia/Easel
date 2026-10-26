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
 ('翻页声','Household Pages Turn Pages 01','Household Book Close Book 01'),
 ('翻书声音','Book Hard Cover Flip Through Single 01','Book Fall To Ground 01'),
 ('书页翻动声','Book Soft Cover Pages Flipping 01','Book Close Book 01'),
 ('翻阅杂志','Magazine Page Turn 05','Paper Bag Rustle 01'),
 ('报纸翻页声','Newspaper Turn Page 01','Newspaper Rustle 02'),
 ('纸张沙沙声','Paper Rustle Short 01','Paper Cutter Slice Paper 01'),
 ('揉纸声','Paper Crumble Notebook Paper 03','Pen Writing On Paper 16'),
 ('揉皱纸张','Paper Crumpling 01','Paper Rustle Short 01'),
 ('撕纸声','Paper Envelope Tearing Open 01','Paper Rustle Short 01'),
 ('钢笔在纸上写字','Pen Writing On Paper On Wood Table 16','Pencil Erase On Paper 01'),
 ('page turning','Book Soft Cover Pages Turning 14','Book Close Book 01'),
])
def test_action_identity(query, good, bad):
    assert score_audio(query,good,good)>0
    assert score_audio(query,bad,bad)==0

def test_broad_import_tags_cannot_make_single_keystroke_continuous():
    assert score_audio('keyboard typing','Keyboard Single Hit','keyboard typing 键盘 打字')==0

def test_broad_import_tags_cannot_turn_book_closing_into_page_turning():
    assert score_audio('翻页声','Book Close Book 01','page turning 翻页 纸张')==0

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

@pytest.mark.parametrize('query,title', [
    ('翻页声', 'Household Book Soft Cover Pages Turning 14'),
    ('翻阅杂志', 'Household Magazine Page Turn 05'),
    ('报纸翻页声', 'Household Newspaper Page Turn 01'),
])
def test_chinese_page_queries_rank_source_action_before_top_k(query, title):
    data = [record(0, 'Book Close Book 01'),
            record(1, 'Book Hard Cover Book Flip Page Fast 01'), record(2, title)]
    class Catalog:
        def metadata_search(self, **kwargs):
            return tuple(data)
    idx = MaterialSemanticIndex.__new__(MaterialSemanticIndex)
    idx.catalog = Catalog()
    found = idx.search(query, scope=None, context=None, provider=None, limit=3)
    titles = [hit.record.asset.semantic.caption for hit in found.hits]
    assert 'Book Close Book 01' not in titles
    assert title in titles
    if query != '翻页声':
        assert titles[0] == title

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


@pytest.mark.parametrize('title,expected',[
    ('Inleiding Spark Of Being (audio).mp3','speech'),
    ('Lecture on piano music.mp3','speech'),
    ('Speechless piano prelude.ogg','music'),
    ('Ambient guitar instrumental.ogg','music'),
    ('Office background.wav','unclassified'),
])
def test_file_content_type_is_not_search_role(title,expected):
    from easel.materials.audio_search import audio_content_kind
    assert audio_content_kind(title)==expected
