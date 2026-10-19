"""Explicit MiniMax native T2A wire adapter, sharing durable voice receipts.

Protocol: POST /v1/t2a_v2, non-streaming JSON with hex audio. The caller names
its model and voice; this adapter never discovers or substitutes them.
"""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit
import httpx
from ..voice import VoiceHTTPAdapter, SpeechResponseError
from ..errors import ProductionError


class MiniMaxSpeechAdapter(VoiceHTTPAdapter):
    additional_parameters = frozenset({'emotion', 'subtitle_enable'})

    def option(self, identity, *, require_available=True):
        option = super().option(identity, require_available=require_available)
        emotion = identity.parameters.get('emotion')
        permitted = {'happy', 'sad', 'angry', 'fearful', 'disgusted', 'surprised', 'calm'}
        if identity.model in {'speech-2.6-hd', 'speech-2.6-turbo'}:
            permitted |= {'fluent', 'whisper'}
        if (emotion is not None and emotion not in permitted) or (
                'subtitle_enable' in identity.parameters and type(identity.parameters['subtitle_enable']) is not bool):
            raise ProductionError('voice_parameter_unsupported', '所选MiniMax模型不支持该情绪或字幕参数')
        return option

    def request(self, *, identity, text, segment_id, require_available=True):
        value = super().request(identity=identity,text=text,segment_id=segment_id,require_available=require_available)
        if (len(text)>10000 or self.config.response_format not in {'wav','mp3','flac'}
                or set(identity.parameters)-{'speed', 'emotion', 'subtitle_enable'}
                or not .5<=identity.parameters.get('speed',1)<=2):
            raise ProductionError('voice_parameter_unsupported','MiniMax 原生旁白的文本长度、速度或输出格式不支持；未发送请求')
        return value

    def _wire_request(self, request, identity):
        payload = {
            'model':identity.model,'text':request['text'],'stream':False,'output_format':'hex',
            'voice_setting':{'voice_id':identity.voice_id,'speed':identity.parameters.get('speed',1),'vol':1,'pitch':0},
            'audio_setting':{'format':self.config.response_format,'sample_rate':32000,'channel':1}}
        if 'emotion' in identity.parameters:
            payload['voice_setting']['emotion'] = identity.parameters['emotion']
        if identity.parameters.get('subtitle_enable'):
            payload['subtitle_enable'] = True
        return self.config.base_url.rstrip('/') + '/t2a_v2', payload

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
            # Timestamp retrieval is read-only. Losing it must never cause a
            # second paid TTS request or discard already received audio bytes.
            return self._alignment(value.get('subtitle_file'))
        except (ValueError,KeyError,TypeError):
            raise SpeechResponseError('native speech response is invalid') from None

    def _alignment(self, url):
        if not isinstance(url, str) or not url:
            return {}
        try:
            parsed = urlsplit(url)
            host = parsed.hostname or ''
            if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443)
                    or not any(host == h or host.endswith('.' + h) for h in
                               ('minimax.chat', 'minimaxi.chat', 'minimax.cn', 'minimaxi.com'))):
                return {'status': 'unavailable', 'reason': 'subtitle_host_not_admitted'}
            with httpx.Client(transport=self.transport, timeout=20, trust_env=False, follow_redirects=False) as client:
                with client.stream('GET', url) as response:
                    if response.status_code != 200:
                        return {'status': 'unavailable', 'reason': 'subtitle_not_received'}
                    raw = bytearray()
                    for chunk in response.iter_bytes():
                        raw.extend(chunk)
                        if len(raw) > 2 * 1024 * 1024:
                            raise ValueError
            items = json.loads(raw)
            if not isinstance(items, list) or len(items) > 10000:
                raise ValueError
            segments = []
            previous = 0.0
            for item in items:
                start, end = float(item['time_begin']) / 1000, float(item['time_end']) / 1000
                text = item['text']
                if (not isinstance(text, str) or not text or len(text) > 10000
                        or not 0 <= previous <= start < end <= 3600):
                    raise ValueError
                segments.append({'text': text, 'start': start, 'end': end})
                previous = end
            return {'status': 'received', 'unit': 'seconds', 'segments': segments} if segments else {}
        except (ValueError, KeyError, TypeError, httpx.HTTPError):
            return {'status': 'unavailable', 'reason': 'subtitle_invalid_or_unavailable'}
