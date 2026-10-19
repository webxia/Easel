from pathlib import Path
import pytest
from PIL import Image
from easel.production.creative_captions import CreativeCaption, compile_captions, check_caption_layout
from easel.production.contracts import SubtitleSettings
from easel.production.media import caption_image
from easel.production.editors import Caption, EditError


@pytest.fixture
def font():
    p=next((Path(x) for x in ['/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/arial.ttf'] if Path(x).is_file()),None)
    if p is None:pytest.skip('font unavailable')
    return p


def test_speech_style_does_not_reposition_explanatory_overlay_and_collision_is_checked(font,tmp_path):
    speech=CreativeCaption(caption_id='speech',text='旁白原句',start=0,end=4,font_asset_id='font',role='narration')
    title=CreativeCaption(caption_id='title',text='做完不等于学会',start=0,end=4,font_asset_id='font',role='overlay',y=.2,size=72)
    result=compile_captions([speech,title],style=SubtitleSettings(size=56),fonts={'sans-serif':'font'})
    assert result[0].y==.88 and result[0].size==56 and result[1].y==.2 and result[1].size==72
    check_caption_layout(result,font_paths={'font':font},width=1920,height=1080)
    # Verify real raster bounds, not only the implementation's model fields.
    for i,c in enumerate(result):
        image=Image.open(caption_image(c,font,width=1920,height=1080,destination=tmp_path/f'{i}.png'))
        assert image.getbbox()[1] > 800 if i==0 else image.getbbox()[3]<350
    collision=[result[0],result[1].model_copy(update={'y':.88})]
    with pytest.raises(EditError,match='叠字'):
        check_caption_layout(collision,font_paths={'font':font},width=1920,height=1080)


def test_provider_alignment_replaces_speech_only_not_explanation():
    items=[CreativeCaption(caption_id='title',text='解释字',start=0,end=4,font_asset_id='font',role='overlay',y=.2)]
    result=compile_captions(items,style=SubtitleSettings(),fonts={'sans-serif':'font'},
                           aligned=[{'text':'真实对齐旁白','start':.2,'end':3.8}])
    assert [x.text for x in result]==['真实对齐旁白','解释字']
    assert all(isinstance(x,Caption) and 'role' not in x.model_dump() for x in result)
