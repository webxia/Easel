#!/usr/bin/env python3
"""Explicit offline ability gate. Never downloads models or touches an Attempt.

The caller must supply a frozen, separately reviewed four-case corpus and its
SHA-256. This tool is intentionally not invoked by Delivery or software tests.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import sys
from time import monotonic

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from easel.materials.application.voice_delivery import read_local_voice, recognition_digest, voice_verification_identity
from easel.materials.application.voice_supplement import CASES, validate_capability


def verify(model: Path, corpus: Path, expected_sha: str):
    raw = corpus.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError('样本清单不是事先冻结的版本')
    source = json.loads(raw)
    rows = source.get('cases', [])
    if {r.get('id') for r in rows} != CASES or len(rows) != 4:
        raise ValueError('须使用完整、错字、缺字、多字四项独立样本')
    descriptor = voice_verification_identity(None, model)
    results = []
    for case in rows:
        path = (corpus.parent / case['path']).resolve(strict=True)
        if not path.is_relative_to(corpus.parent.resolve()) or path.is_symlink() or not path.is_file():
            raise ValueError('声音样本须位于隔离样本目录')
        if hashlib.sha256(path.read_bytes()).hexdigest() != case['audio_sha256']:
            raise ValueError('声音样本字节与冻结清单不符')
        if case.get('expected_acceptance') is not (case['id'] == 'complete'):
            raise ValueError('声音样本预期不能根据输出更改')
        if not 0 < case['duration_seconds'] <= 60:
            raise ValueError('隔离能力样本须为1分钟以内的完整短音轨')
        cache = corpus.parent / '.voice-verification'
        cache.mkdir(exist_ok=True)
        key = recognition_digest({'audio_sha256': case['audio_sha256'], 'verification': descriptor})
        cache_path = cache / (key + '.json')
        if cache_path.is_symlink():
            raise ValueError('隔离识别缓存路径无效')
        if cache_path.is_file():
            saved = json.loads(cache_path.read_text(encoding='utf-8'))
            report = saved['recognition']
            if report.get('verification_config') != descriptor:
                raise ValueError('声音能力缓存配置不同')
        else:
            started = monotonic()
            report = read_local_voice(path, None, model_path=model)
            cache_path.write_text(json.dumps({'recognition': report, 'elapsed_seconds': monotonic() - started},
                                            ensure_ascii=False, sort_keys=True), encoding='utf-8')
        results.append({k: case[k] for k in ('id', 'script', 'expected_acceptance', 'duration_seconds', 'audio_sha256')}
                       | {'recognition': report})
    capability = {'schema': 'local-voice-capability@1', 'verification': descriptor,
                  'corpus_sha256': expected_sha, 'cases': results}
    capability['identity'] = recognition_digest(capability)
    # Retain the actual corpus/config/output even when the semantic gate fails.
    diagnostic = corpus.parent / '.voice-verification' / ('capability-' + capability['identity'] + '.json')
    if not diagnostic.exists():
        diagnostic.write_text(json.dumps(capability, ensure_ascii=False, sort_keys=True, indent=2), encoding='utf-8')
    validate_capability(capability, descriptor)
    return capability


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--corpus-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.model, args.corpus, args.corpus_sha256)
    # Exclusive creation preserves previously reviewed capability records.
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write('\n')
    print('本机声音能力门通过；尚未恢复作品或授予素材准入。')


if __name__ == '__main__':
    main()
