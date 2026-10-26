"""Explicit MiniMax native T2A wire adapter, sharing durable voice receipts.

Protocol: POST /v1/t2a_v2, non-streaming JSON with hex audio. The caller names
its model and voice; this adapter never discovers or substitutes them.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit
import httpx
from ..voice import VoiceHTTPAdapter, SpeechResponseError
from ..errors import ProductionError
from ..media import atomic_json
from .base import ProviderResult


PLAN_VOICE_PARAMETERS = frozenset({'speed', 'emotion', 'subtitle_enable'})


def native_voice_settings(identity):
    """The exact native voice wire fields; fixed knobs are not Plan parameters."""
    settings = {'voice_id': identity.voice_id, 'speed': identity.parameters.get('speed', 1),
                'vol': 1, 'pitch': 0}
    if 'emotion' in identity.parameters:
        settings['emotion'] = identity.parameters['emotion']
    return settings


def voice_execution_contract(identity):
    return {'engine': 'minimax-speech-v1',
            'supported_plan_parameters': sorted(PLAN_VOICE_PARAMETERS),
            'fixed_wire_parameters': {'vol': native_voice_settings(identity)['vol'],
                                      'pitch': native_voice_settings(identity)['pitch']},
            'effective_wire_voice_setting': native_voice_settings(identity)}


class MiniMaxSpeechAdapter(VoiceHTTPAdapter):
    additional_parameters = frozenset({'emotion', 'subtitle_enable'})
    subtitle_hosts = ('minimax.chat', 'minimaxi.chat', 'minimax.cn', 'minimaxi.com',
                      'minimax-algeng-chat-tts.oss-cn-wulanchabu.aliyuncs.com')

    def observe(self, *, task_id, request_key):
        received=super().observe(task_id=task_id,request_key=request_key)
        if received.state!='succeeded' or received.result.get('alignment',{}).get('status')=='received':return received
        locator=self._directory(request_key)/'subtitle-locator.json'
        if not locator.is_file() or locator.is_symlink() or locator.stat().st_size>16384:return received
        try:
            url=json.loads(locator.read_text())['url']
            alignment=self._alignment(url)
            if alignment and alignment!=received.result.get('alignment'):
                result={**received.result,'alignment':alignment}
                atomic_json(self._directory(request_key)/'receipt.json',{'state':'succeeded','result':result})
                return ProviderResult('succeeded',result=result)
        except (OSError,ValueError,KeyError,TypeError):pass
        return received

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
                or set(identity.parameters)-PLAN_VOICE_PARAMETERS
                or not .5<=identity.parameters.get('speed',1)<=2):
            raise ProductionError('voice_parameter_unsupported','MiniMax 原生旁白的文本长度、速度或输出格式不支持；未发送请求')
        return value

    def _wire_request(self, request, identity):
        payload = {
            'model':identity.model,'text':request['text'],'stream':False,'output_format':'hex',
            'voice_setting':native_voice_settings(identity),
            'audio_setting':{'format':self.config.response_format,'sample_rate':32000,'channel':1}}
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
            # Private ephemeral download locator, never returned as an asset
            # field or exported in logs. This permits read-only reconciliation
            # after admitting a real provider CDN, without paying for TTS twice.
            url=value.get('subtitle_file')
            try:
                parsed=urlsplit(url) if isinstance(url,str) and len(url)<=8192 else None
                name=getattr(stream,'name',None)
                if (parsed and parsed.scheme in {'http','https'} and parsed.hostname and not parsed.username and not parsed.password
                        and parsed.port in (None,80,443) and isinstance(name,str)
                        and Path(name).resolve().is_relative_to(self.root.resolve())):
                    atomic_json(Path(name).parent/'subtitle-locator.json',{'url':url})
            except (OSError,ValueError,TypeError):pass
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
                           self.subtitle_hosts)):
                return {'status': 'unavailable', 'reason': 'subtitle_host_not_admitted',
                        'host':host if re.fullmatch(r'[a-zA-Z0-9.-]{1,253}',host) else ''}
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
