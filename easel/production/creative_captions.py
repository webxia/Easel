"""Keep speech subtitles and explanatory overlays distinct through compilation."""
from typing import Literal
from .editors import Caption, EditError
from .subtitles import caption_from_settings
from .media import caption_layout


class CreativeCaption(Caption):
    role: Literal['narration','overlay'] = 'narration'


def edit_data(edit):
    data=edit.model_dump()
    data['captions']=[c.model_dump(exclude={'role'}) for c in edit.captions]
    return data


def compile_captions(captions, *, style, fonts, aligned=None):
    overlays=[Caption.model_validate(c.model_dump(exclude={'role'})) for c in captions if c.role=='overlay']
    if aligned:
        speech=[caption_from_settings(style,caption_id='speech-'+str(i),text=c['text'],
                    start=c['start'],end=c['end'],fonts=fonts) for i,c in enumerate(aligned)]
    else:
        speech=[caption_from_settings(style,caption_id=c.caption_id,text=c.text,
                    start=c.start,end=c.end,fonts=fonts) for c in captions if c.role=='narration']
    return [c for c in speech if c is not None]+overlays


def check_caption_layout(captions, *, font_paths, width, height):
    boxes=[]
    for c in captions:
        if c.font_asset_id not in font_paths:
            raise EditError('文字图层必须使用本次真实字体素材')
        _, _, _, (x,y,w,h)=caption_layout(c,font_paths[c.font_asset_id],width=width,height=height)
        pad=10 if c.background else 0
        boxes.append((x-pad,y-pad,x+w+pad,y+h+pad))
    for i,a in enumerate(captions):
        for j in range(i):
            b=captions[j]
            if min(a.end,b.end)<=max(a.start,b.start)+.001:continue
            x1,y1,x2,y2=boxes[i];u1,v1,u2,v2=boxes[j]
            if min(x2,u2)>max(x1,u1) and min(y2,v2)>max(y1,v1):
                raise EditError('同时显示的文字图层发生叠字：'+a.caption_id+' / '+b.caption_id)
