"""Independent local interval evidence under the existing voice verifier.

No model is downloaded, chosen or qualified here. A configured capability must
first pass the fixed positive/negative corpus before it can provide evidence.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from types import SimpleNamespace

from easel.materials.application.voice_delivery import (
    _spoken, _asr_script_converter, recognition_digest, voice_verification_identity,
)

REVISION = 'independent-voice-interval@1'
CASES = {'complete', 'wrong_word', 'missing_word', 'extra_word'}


def primary_digest(report):
    return recognition_digest({k: v for k, v in report.items() if k != 'supplements'})


def verify_interval(script, asset, report, word_index, proof):
    """Validate independent exact content and measured coverage, not score fusion."""
    if (proof.get('schema') != REVISION or proof.get('primary_sha256') != primary_digest(report)
            or proof.get('audio_sha256') != asset.file.sha256
            or proof.get('script_sha256') != hashlib.sha256(script.encode()).hexdigest()
            or proof.get('need_sha256') != report.get('need_sha256')
            or proof.get('word_index') != word_index):
        raise ValueError('局部声音证据不属于当前完整识别/音频/脚本/Need')
    independent = proof.get('recognition', {})
    descriptor = proof.get('verification', {})
    if (not descriptor.get('model_sha256') or descriptor.get('model_sha256') == report.get('model_sha256')
            or descriptor != independent.get('verification_config')
            or independent.get('model_sha256') != descriptor.get('model_sha256')
            or descriptor.get('rules') != 'complete-voice-and-independent-interval@2'
            or proof.get('capability_sha256') != proof.get('capability', {}).get('identity')):
        raise ValueError('补证须来自独立且通过能力验证的模型配置')
    validate_capability(proof['capability'], descriptor)
    left, right = proof.get('context_words', (None, None))
    original = report['words']
    if (type(left) is not int or type(right) is not int or not 0 <= left <= word_index < right <= len(original)):
        raise ValueError('局部证据上下文位置无效')
    start, end = proof.get('interval', (None, None))
    if (any(type(t) not in (int, float) or not math.isfinite(t) for t in (start, end))
            or not 0 <= start < end <= asset.technical.duration_seconds + .1
            or not start <= original[left]['start_seconds']
            or not original[right - 1]['end_seconds'] <= end):
        raise ValueError('局部证据未覆盖真实低置信区间')
    words = independent.get('words')
    if not isinstance(words, list) or not words:
        raise ValueError('独立识别缺少实际声音证据')
    position = 0.
    for word in words:
        p, a, b = word.get('probability'), word.get('start_seconds'), word.get('end_seconds')
        if (type(p) not in (int, float) or not math.isfinite(p) or not .5 <= p <= 1
                or any(type(t) not in (int, float) or not math.isfinite(t) for t in (a, b))
                or not position <= a < b <= end - start + .1 or not _spoken(word.get('text', ''))):
            raise ValueError('独立识别仍不足或实测时间无效')
        position = b
    wanted = ''.join(_spoken(w['text']) for w in original[left:right])
    got = ''.join(_spoken(w['text']) for w in words)
    convert = _asr_script_converter().convert
    if convert(wanted) != convert(got):
        raise ValueError('局部识别与原完整识别冲突，不能准入')
    return True


def validate_capability(capability, descriptor):
    from easel.materials.application.voice_delivery import timing_from_recognition
    rows = capability.get('cases', [])
    if (capability.get('schema') != 'local-voice-capability@1'
            or capability.get('verification') != descriptor
            or {r.get('id') for r in rows} != CASES or len(rows) != len(CASES)
            or len({r.get('audio_sha256') for r in rows}) != 4
            or len({r.get('script') for r in rows}) != 1):
        raise ValueError('备用声音能力尚未通过固定正负样本验证')
    body = {k: v for k, v in capability.items() if k != 'identity'}
    if capability.get('identity') != recognition_digest(body):
        raise ValueError('备用声音能力记录身份无效')
    for case in rows:
        if (type(case.get('expected_acceptance')) is not bool
                or case['expected_acceptance'] is not (case['id'] == 'complete')
                or case.get('recognition', {}).get('verification_config') != descriptor
                or not isinstance(case.get('audio_sha256'), str) or len(case['audio_sha256']) != 64):
            raise ValueError('声音样本与已验证配置不匹配')
        fake = SimpleNamespace(asset_id='capability-fixture', file=SimpleNamespace(sha256=case['audio_sha256']),
                               technical=SimpleNamespace(duration_seconds=case.get('duration_seconds')), semantic=SimpleNamespace(inferences=()))
        try:
            timing_from_recognition(case['script'], fake, case['recognition'])
            accepted = True
        except ValueError:
            accepted = False
        if accepted != case['expected_acceptance']:
            raise ValueError('备用声音验证器未通过固定正负样本')
    return capability


def configured_supplement():
    from easel.runtime_config import EaselRuntimeConfig
    config = EaselRuntimeConfig.load()
    model_value = config.get('EASEL_ASR_SUPPLEMENT_MODEL', '').strip()
    capability_value = config.get('EASEL_ASR_SUPPLEMENT_CAPABILITY', '').strip()
    if not model_value or not capability_value:
        raise ValueError('低置信声音补证能力未配置/验证；原旁白保留，未重购或重复全文识别')
    model, path = Path(model_value).expanduser(), Path(capability_value).expanduser()
    if not model.is_dir() or path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError('备用声音模型或能力记录无效')
    descriptor = voice_verification_identity(None, model)
    capability = validate_capability(json.loads(path.read_text(encoding='utf-8')), descriptor)
    return model, descriptor, capability


def supplement_low_confidence(path, asset, script, report, store, *, observe):
    """Only low-confidence intervals; each successful/failed attempt is durable."""
    model, descriptor, capability = configured_supplement()
    if descriptor['model_sha256'] == report.get('model_sha256'):
        raise ValueError('同一模型不能为自身低置信判断提供独立证据')
    report = {**report, 'supplements': list(report.get('supplements', []))}
    for index, word in enumerate(report['words']):
        if word['probability'] >= .5:
            continue
        if any(p.get('word_index') == index and verify_interval(script, asset, report, index, p)
               for p in report['supplements']):
            continue
        left, right = max(0, index - 1), min(len(report['words']), index + 2)
        start = max(0., report['words'][left]['start_seconds'] - .25)
        end = min(asset.technical.duration_seconds, report['words'][right - 1]['end_seconds'] + .25)
        proof = {'schema': REVISION, 'primary_sha256': primary_digest(report), 'audio_sha256': asset.file.sha256,
                 'script_sha256': hashlib.sha256(script.encode()).hexdigest(), 'need_sha256': report.get('need_sha256'),
                 'word_index': index, 'context_words': [left, right], 'interval': [start, end],
                 'verification': descriptor, 'capability': capability, 'capability_sha256': capability['identity']}
        key = 'voice-interval-' + recognition_digest(proof)
        saved = store.read_recovery_record(key)
        if saved is None:
            import subprocess
            import sys
            import tempfile
            try:
                with tempfile.TemporaryDirectory(prefix='easel-voice-interval-') as folder:
                    clip = Path(folder) / 'interval.wav'
                    # No expected text or script is passed to either process.
                    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', str(start), '-i', str(path),
                        '-t', str(end - start), '-ac', '1', '-ar', '16000', str(clip)], check=True, capture_output=True, timeout=30)
                    observe()
                    code = ('import json,sys; from pathlib import Path; '
                            'from easel.materials.application.voice_delivery import transcribe_local_voice; '
                            'print(json.dumps(transcribe_local_voice(Path(sys.argv[1]),Path(sys.argv[2]),None),ensure_ascii=False))')
                    result = subprocess.run([sys.executable, '-c', code, str(clip), str(model)],
                                            check=True, capture_output=True, timeout=180)
                    if len(result.stdout) > 2_000_000:
                        raise ValueError('局部声音识别输出过大')
                    recognition = json.loads(result.stdout)
                    proof['recognition'] = {**recognition, 'verification_config': descriptor,
                                            'model_sha256': descriptor['model_sha256']}
                # Even a validly delivered rejection is cached. Retrying under the
                # same model/interval does not run recognition again.
                store.write_recovery_record(key, proof)
            except (subprocess.SubprocessError, OSError, ValueError) as exc:
                store.write_recovery_record(key, {**proof, 'failure': '局部声音执行或交付失败，原证据保留，需先诊断条件'})
                raise ValueError('局部声音补证失败；未重复全文识别或TTS') from exc

        else:
            proof = saved
        if proof.get('failure'):
            raise ValueError(proof['failure'])
        verify_interval(script, asset, report, index, proof)
        report['supplements'].append(proof)
    return report
