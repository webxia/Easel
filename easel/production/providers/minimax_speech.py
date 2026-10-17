"""Explicit MiniMax native T2A wire adapter, sharing durable voice receipts.

Protocol: POST /v1/t2a_v2, non-streaming JSON with hex audio. The caller names
its model and voice; this adapter never discovers or substitutes them.
"""
from __future__ import annotations

import json
import re
from ..voice import VoiceHTTPAdapter, SpeechResponseError
from ..errors import ProductionError


class MiniMaxSpeechAdapter(VoiceHTTPAdapter):
    def request(self, *, identity, text, segment_id, require_available=True):
        value = super().request(identity=identity,text=text,segment_id=segment_id,require_available=require_available)
        if (len(text)>10000 or self.config.response_format not in {'wav','mp3','flac'}
                or set(identity.parameters)-{'speed'}
                or not .5<=identity.parameters.get('speed',1)<=2):
            raise ProductionError('voice_parameter_unsupported','MiniMax 原生旁白的文本长度、速度或输出格式不支持；未发送请求')
        return value

    def _wire_request(self, request, identity):
        return self.config.base_url.rstrip('/') + '/t2a_v2', {
            'model':identity.model,'text':request['text'],'stream':False,'output_format':'hex',
            'voice_setting':{'voice_id':identity.voice_id,'speed':identity.parameters.get('speed',1),'vol':1,'pitch':0},
            'audio_setting':{'format':self.config.response_format,'sample_rate':32000,'channel':1}}

    def _write_audio(self, response, stream):
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data)>128*1024*1024:
                raise SpeechResponseError('native speech response exceeds limit')
        try:
            payload=json.loads(data)
            status=payload['base_resp']['status_code']
            value=payload['data']
            audio=value['audio']
            if type(status) is not int or status!=0 or value.get('status')!=2:
                raise ValueError('native service did not complete')
            if not isinstance(audio,str) or not audio or len(audio)%2 or len(audio)>128*1024*1024:
                raise ValueError('invalid native audio length')
            if re.fullmatch(r'[0-9a-fA-F]+',audio) is None:
                raise ValueError('invalid native audio encoding')
            stream.write(bytes.fromhex(audio))
        except (ValueError,KeyError,TypeError):
            raise SpeechResponseError('native speech response is invalid') from None
