"""Deterministic schematic rendering of the creative model's frozen board data.

No per-work copy, examples, card wording or classifications live in this renderer.
It supplies geometry, literal text, true counts and an always-visible disclosure.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .editors import EditError

VERSION='schematic-board-3'


def _label(draw,text,box,font,color,*,center=False):
    x,y,w,h=box;lines=[];line=''
    for c in text:
        if c=='\n' or (line and draw.textlength(line+c,font=font)>w):
            lines.append(line);line=''
        if c!='\n':line+=c
    lines.append(line);value='\n'.join(lines)
    bounds=draw.multiline_textbbox((0,0),value,font=font,spacing=6,align='center' if center else 'left')
    tw,th=bounds[2]-bounds[0],bounds[3]-bounds[1]
    if tw>w+1 or th>h:raise EditError('原生图解文字超出可读区域，请缩短文字而非缩小字号')
    draw.multiline_text((x+(w-tw)/2-bounds[0] if center else x-bounds[0],y+(h-th)/2-bounds[1]),
        value,font=font,fill=color,spacing=6,align='center' if center else 'left')


def board_footer(board, index):
    count = sum(len(v) for v in board.states[index].groups.values())
    disclosure = '假设示意' if board.kind == 'hypothetical' else '概念示意'
    return disclosure+'  ·  '+str(count)+' 条  /  '+str(len(board.columns))+' 组'


def render_board(board, index, *, font_path, aspect_ratio, destination):
    wide=aspect_ratio=='16:9';width,height=(1920,1080) if wide else (1080,1920)
    im=Image.new('RGB',(width,height),'#F7F7F2');draw=ImageDraw.Draw(im)
    fonts={size:ImageFont.truetype(str(font_path),size) for size in [64,56,48,40,36,34,28,24,22]}
    margin=80 if wide else 48;available=width-2*margin;state=board.states[index]
    _label(draw,board.title,(margin,40,available,90 if wide else 140),fonts[64] if wide else fonts[48],'#163238')
    _label(draw,state.title,(margin,140 if wide else 190,available,75 if wide else 105),fonts[40] if wide else fonts[36],'#294D53')
    col_top,top,bottom=(230,300,840) if wide else (320,440,1510)
    gap=48 if wide else 28;cw=(available-gap*(len(board.columns)-1))/len(board.columns)
    row_count=max(len(s.groups[col.id]) for s in board.states for col in board.columns)
    cell_h=(bottom-top-12*(row_count-1))/row_count
    cards={c.id:c for c in board.cards}
    # Use one legible size across the whole board and all states, keeping
    # geometry stable as cards move. Never hide overflow by shrinking below 34px.
    measure=ImageDraw.Draw(Image.new('RGB',(1,1)))
    for size in [56,48,40,36,34]:
        try:
            for card in board.cards:_label(measure,card.text,(0,0,cw-48,cell_h-24),fonts[size],'#000000')
            card_font=fonts[size];break
        except EditError:
            if size==34:raise
    for col_index,col in enumerate(board.columns):
        x=margin+col_index*(cw+gap)
        _label(draw,state.column_titles.get(col.id,col.title),(x,col_top,cw,60 if wide else 100),fonts[36] if wide else fonts[34],'#526A6C')
        draw.line((x,col_top+58 if wide else col_top+98,x+cw,col_top+58 if wide else col_top+98),fill='#D8DFDA',width=2)
        for row,identifier in enumerate(state.groups[col.id]):
            y=top+row*(cell_h+12);highlight=identifier in state.highlight_ids
            draw.rounded_rectangle((x,y,x+cw,y+cell_h),radius=12,fill='#E8EFE8' if highlight else '#FFFFFF')
            if highlight:
                draw.rounded_rectangle((x,y+12,x+5,y+cell_h-12),radius=2,fill='#397465')
            _label(draw,cards[identifier].text,(x+24,y+12,cw-48,cell_h-24),card_font,'#163238')
    _label(draw,board_footer(board,index),
        (margin,height-65,available,40),fonts[28],'#526A6C')
    destination=Path(destination);destination.parent.mkdir(parents=True,exist_ok=True);im.save(destination,'PNG')
    return destination


def check_board_usage(scenes,records,*,overlays=()):
    import json
    groups={};expected={}
    for record in records:
        for use in json.loads(record['metadata_json']).get('material_uses',[]):
            if use.get('board_id'):
                expected[record['id']]=(use['board_id'],use['board_frame_index'])
    selected=[s.asset_id for s in scenes]
    for asset,(board,index) in expected.items():
        if asset not in selected:raise ValueError('已确认图解的全部状态须真实展示，不能遗漏状态')
        groups.setdefault(board,[]).append((index,selected.index(asset)))
    for values in groups.values():
        if [p for _,p in sorted(values)]!=sorted(p for _,p in values):
            raise ValueError('图解状态须按已确认的前后顺序展示')
    # Framing/overlay readability is a visual judgment, not a blanket ban.
    # Literal frozen states and progression remain protected above; actual
    # caption geometry and independent media review check the chosen layout.
