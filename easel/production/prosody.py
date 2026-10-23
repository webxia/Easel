"""Bounded pauses are separate from literal narration and subtitle text."""
from .errors import ProductionError

VERSION='minimax-pauses-1'


def compile_pauses(text, pauses, identity):
    if not pauses:return text
    if identity.engine!='minimax-speech-v1' or identity.model not in {'speech-2.8-hd','speech-2.8-turbo'}:
        raise ProductionError('voice_prosody_unsupported','当前固定声音不支持已确认的停顿控制；未静默忽略或切换声音')
    if '<#' in text or len(pauses)>32:
        raise ProductionError('voice_prosody_invalid','停顿控制必须与正文分离且有界')
    previous=0;pieces=[]
    for item in pauses:
        at=item['after'];seconds=item['seconds']
        if type(at) is not int or not previous<at<len(text) or type(seconds) not in (int,float) or not .05<=seconds<=1:
            raise ProductionError('voice_prosody_invalid','停顿位置或时长无效')
        pieces.extend((text[previous:at],f'<#{seconds:g}#>'));previous=at
    pieces.append(text[previous:])
    return ''.join(pieces)
