"""Optional local forced alignment of confirmed words, never transcription/TTS.

Provider paragraph anchors constrain each acoustic window. Model files must
already be installed locally; this module never downloads them or changes audio.
"""
from __future__ import annotations
import math
from pathlib import Path
from .contracts import fingerprint
from .media import atomic_json, file_sha256


def caption_units(words: list[dict], *, max_chars: int = 24) -> list[dict]:
    """Group acoustically aligned original tokens into readable literal cues."""
    result, pending = [], []
    def flush():
        if not pending:
            return
        result.append({'text': ''.join(w['word'] for w in pending),
                       'start': pending[0]['start'], 'end': pending[-1]['end']})
        pending.clear()
    for word in words:
        if pending and (len(''.join(w['word'] for w in pending)) + len(word['word']) > max_chars
                        or word['end'] - pending[0]['start'] > 5):
            flush()
        pending.append(word)
        if word['word'][-1:] in '，。！？；：,!?;:\n':
            flush()
    flush()
    return result


def align_confirmed_speech(path: Path, text: str, provider: dict, *, model_name: str, cache: Path) -> dict:
    """Return local acoustic estimates with provenance, or explicit unavailable."""
    unavailable = {'status': 'unavailable', 'reason': 'local_forced_alignment_unavailable'}
    normalize = lambda value: ''.join(value.split())
    paragraphs = provider.get('segments', [])
    if (model_name not in {'tiny', 'base', 'small'} or provider.get('status') != 'received' or not paragraphs
            or normalize(''.join(p['text'] for p in paragraphs)) != normalize(text)
            or any(not 0 < p['end'] - p['start'] <= 29 for p in paragraphs)):
        return unavailable
    digest = file_sha256(path)
    key = fingerprint([digest, text, provider, model_name, 'forced-captions-1'])
    target = cache / (key + '.json')
    if target.is_file():
        import json
        try:
            cached = json.loads(target.read_text(encoding='utf-8'))
            if (cached.get('audio_sha256') == digest and cached.get('status') == 'received'
                    and normalize(''.join(s['text'] for s in cached['segments'])) == normalize(text)):
                return cached
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    try:
        from faster_whisper import WhisperModel
        from faster_whisper.audio import decode_audio
        from faster_whisper.tokenizer import Tokenizer
        audio = decode_audio(str(path), sampling_rate=16000)
        model = WhisperModel(model_name, device='cpu', compute_type='int8', local_files_only=True, cpu_threads=4)
        tokenizer = Tokenizer(model.hf_tokenizer, model.model.is_multilingual, task='transcribe', language='zh')
        captions = []
        for paragraph in paragraphs:
            begin, end = max(0, paragraph['start'] - .1), min(len(audio) / 16000, paragraph['end'] + .1)
            part = audio[int(begin * 16000):int(end * 16000)]
            features = model.feature_extractor(part)
            raw = model.find_alignment(tokenizer, [tokenizer.encode(paragraph['text'])],
                                       model.encode(features), features.shape[-1])[0]
            if normalize(''.join(w['word'] for w in raw)) != normalize(paragraph['text']):
                return unavailable
            words = []
            previous = paragraph['start']
            for word in raw:
                start = max(previous, paragraph['start'], float(word['start']) + begin)
                stop = min(paragraph['end'], float(word['end']) + begin)
                if not math.isfinite(start + stop) or stop < start:
                    return unavailable
                words.append({'word': word['word'], 'start': start, 'end': stop})
                previous = stop
            units = caption_units(words)
            if any(c['end'] <= c['start'] for c in units):
                return unavailable
            captions.extend(units)
        result = {'status': 'received', 'unit': 'seconds', 'segments': captions,
                  'basis': 'local_acoustic_forced_alignment', 'model': 'faster-whisper/' + model_name,
                  'precision': 'estimated', 'audio_sha256': digest,
                  'text_unchanged': True, 'provider_paragraph_anchors': True}
        cache.mkdir(parents=True, exist_ok=True)
        atomic_json(target, result)
        return result
    except Exception:
        # Alignment failure must never trigger a new paid request or hide the
        # actual provider anchors. No third-party exception/locator is exported.
        return unavailable
