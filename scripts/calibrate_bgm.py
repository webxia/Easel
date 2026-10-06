"""Offline AST capability experiment; never registers assets or changes Gates.

Use a prelabelled manifest and preregistered finite policy grid. Media and raw
reports stay under the explicit output/media directories, outside Git. Only
calibration scores select a policy; a selected policy sees the holdout once.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import itertools
import importlib.metadata
import json
import math
import re
from pathlib import Path
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from easel.materials.application import music_observation as music

EXTRA_VOCALS = frozenset({'Choir', 'A capella', 'Yodeling', 'Mantra'})


def digest_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def assess_candidate(sample, report, policy):
    asset = SimpleNamespace(file=SimpleNamespace(sha256=sample['audio_sha256']),
                            technical=SimpleNamespace(duration_seconds=sample['duration_seconds']))
    # Reuse the current production identity/coverage validation, and close its
    # nonfinite-duration hole explicitly for the isolated candidate experiment.
    if (type(report.get('duration_seconds')) not in (int, float)
            or not math.isfinite(report['duration_seconds'])):
        raise ValueError('nonfinite duration')
    baseline, _ = music.assess_music(asset, report)
    if policy['name'] == 'baseline':
        return baseline
    labels = music.VOCAL_LABELS | EXTRA_VOCALS
    windows = report['windows']
    if any(not labels <= w['scores'].keys() for w in windows):
        raise ValueError('missing expanded vocal labels')
    vocal = max(w['scores'][label] for w in windows for label in labels)
    if vocal >= .2:
        return 'vocals_detected'
    if vocal > .01:
        return 'unknown'
    if policy['name'] == 'A':
        return 'instrumental_music' if all(w['rms'] >= .0001 and w['scores']['Music'] >= .8
                                            for w in windows) else 'unknown'
    if policy['name'] == 'C':
        vad = report.get('_auxiliary_vad')
        if not vad or abs(vad['duration_seconds'] - sample['duration_seconds']) > 1 / 16000:
            raise ValueError('missing/invalid auxiliary VAD evidence')
        run = 0.
        for index, score in enumerate(vad['scores']):
            if not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError('invalid auxiliary VAD score')
            width = max(0., min(.032, vad['duration_seconds'] - index * .032))
            run = run + width if score >= policy['vad_threshold'] else 0.
            if run * 1000 + 1e-6 >= policy['vad_min_contiguous_ms']:
                return 'speech_risk'
    # No duration/majority averaging can erase a veto window.
    if any(w['rms'] < .0001 or w['scores']['Music'] < .2 for w in windows):
        return 'unknown'
    duration = sample['duration_seconds']
    cuts = sorted({0., duration, *(w['start_seconds'] for w in windows),
                   *(min(duration, w['end_seconds']) for w in windows)})
    supported = 0.
    gaps = []
    for start, stop in zip(cuts, cuts[1:]):
        covering = [w for w in windows if w['start_seconds'] <= start and w['end_seconds'] >= stop]
        if not covering:
            raise ValueError('coverage gap')
        if all(w['scores']['Music'] >= policy['music_min'] for w in covering):
            supported += stop - start
        elif gaps and abs(gaps[-1][1] - start) < 1e-8:
            gaps[-1][1] = stop
        else:
            gaps.append([start, stop])
    edge = policy['edge_transition_seconds']
    # An edge exception also requires actual adjacent supporting evidence.
    effective = [b-a for a,b in gaps if not (supported > 0 and b-a <= edge
                                             and (a == 0 or b == duration))]
    acceptable = (supported / duration >= policy['coverage_min']
                  and max(effective, default=0.) <= policy['unknown_max_seconds'])
    return 'instrumental_music' if acceptable else 'unknown'


def summarize(samples, reports, policy):
    results = []
    for sample in samples:
        try:
            verdict = assess_candidate(sample, reports[sample['sample_id']], policy)
        except (ValueError, TypeError, KeyError, AttributeError):
            verdict = 'invalid_evidence'
        positive = sample['expected'] == 'instrumental_music'
        admitted = verdict == 'instrumental_music'
        results.append({'sample_id': sample['sample_id'], 'layer': sample['layer'],
                        'positive': positive, 'verdict': verdict, 'admitted': admitted,
                        'duration_seconds': sample['duration_seconds']})
    return summarize_results(results, policy)


def summarize_results(results, policy):
    """Compute every total from final verdicts, including auxiliary vetoes."""
    layers = {}
    for result in results:
        row = layers.setdefault(result['layer'], {'total': 0, 'qualified': 0,
                                                  'false_admissions': 0, 'unknown': 0})
        row['total'] += 1
        row['qualified'] += int(result['positive'] and result['admitted'])
        row['false_admissions'] += int(not result['positive'] and result['admitted'])
        row['unknown'] += int(result['verdict'] == 'unknown')
    positive_rows = [r for r in results if r['positive']]
    positives = sum(r['admitted'] for r in positive_rows)
    positive_layers = {r['layer'] for r in positive_rows}
    false_admissions = sum(not r['positive'] and r['admitted'] for r in results)
    gate = (len(positive_rows) == 6 and positives >= 5 and false_admissions == 0
            and len(positive_layers) == 3 and all(layers[layer]['qualified'] >= 1 for layer in positive_layers))
    return {'policy': policy, 'positive_total': len(positive_rows), 'positive_qualified': positives,
            'false_admissions': false_admissions, 'gate_passed': gate, 'layers': layers, 'results': results}


def policies(preregistration, vad_preregistration=None):
    grid = preregistration['candidate_b_grid']
    fields = ('music_min', 'coverage_min', 'unknown_max_seconds', 'edge_transition_seconds')
    result = [{'name': 'baseline'}, {'name': 'A'}] + [
        {'name': 'B', **dict(zip(fields, values))}
        for values in itertools.product(*(grid[field] for field in fields))]
    if vad_preregistration is not None:
        result += [{**policy, 'name': 'C', 'vad_threshold': threshold, 'vad_min_contiguous_ms': minimum}
                   for policy in result[2:]
                   for threshold, minimum in itertools.product(vad_preregistration['threshold'],
                                                               vad_preregistration['min_contiguous_ms'])]
    return result


def technical_checks(sample, report):
    mutants = []
    for name, mutate in (
        ('nonfinite_duration', lambda r: r.update(duration_seconds=float('nan'))),
        ('nonfinite_score', lambda r: r['windows'][0]['scores'].update(Music=float('nan'))),
        ('nonfinite_rms', lambda r: r['windows'][0].update(rms=float('inf'))),
        ('coverage_gap', lambda r: r['windows'][0].update(start_seconds=1.)),
        ('missing_tail', lambda r: r['windows'].pop()),
        ('missing_choir', lambda r: r['windows'][0]['scores'].pop('Choir')),
        ('wrong_sha', lambda r: r.update(audio_sha256='0'*64)),
    ):
        clone = deepcopy(report)
        mutate(clone)
        try:
            assess_candidate(sample, clone, {'name': 'A'})
        except (ValueError, TypeError, KeyError, AttributeError):
            rejected = True
        else:
            rejected = False
        mutants.append({'case': name, 'rejected': rejected})
    return mutants



def prepare_media(samples, source_root, media_root):
    """Rebuild fixed samples from licensed originals already obtained locally."""
    import subprocess
    import wave
    import numpy as np

    def write(row, audio):
        expected_samples = round(row['duration_seconds'] * 16000)
        if abs(len(audio) - expected_samples) > 1 or not np.isfinite(audio).all():
            raise ValueError('reconstructed sample duration/data differs')
        path = media_root / row['audio_file']
        with wave.open(str(path), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(np.rint(np.clip(audio, -1, 1) * 32767).astype('<i2').tobytes())
        if music.file_digest(path) != row['audio_sha256']:
            raise ValueError('reconstructed sample SHA differs')

    media_root.mkdir(parents=True, exist_ok=True)
    by_id = {row['sample_id']: row for row in samples}
    for row in samples:
        source, transform = row['source'], row['transform']
        if source.get('kind') == 'licensed_derivative':
            continue
        if source.get('kind') == 'deterministic_local':
            t = np.arange(round(row['duration_seconds'] * 16000)) / 16000
            audio = np.zeros(len(t))
            if transform['kind'] == 'tone':
                frequency = {'tone440': 440, 'tone1000': 1000}[row['sample_id']]
                audio = .2 * np.sin(2 * np.pi * frequency * t)
            elif transform['kind'] == 'impulses':
                audio[::16000] = .5
            elif transform['kind'] != 'silence':
                raise ValueError('unsupported deterministic recipe')
        else:
            path = source_root / (row['source_group'] + '.wav')
            if music.file_digest(path) != source['source_sha256']:
                raise ValueError('original source SHA differs')
            decoded = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path),
                '-ac', '1', '-ar', '16000', '-f', 'f32le', 'pipe:1'],
                capture_output=True, check=True, timeout=60)
            audio = np.frombuffer(decoded.stdout, dtype='<f4').astype(np.float64)
            start = int(transform['start_seconds'] * 16000)
            audio = audio[start:start + round(row['duration_seconds'] * 16000)] * transform['gain']
        write(row, audio)
    for row in samples:
        if row['source'].get('kind') != 'licensed_derivative':
            continue
        parents = []
        for sample_id in row['source']['parent_sample_ids']:
            parent = by_id[sample_id]
            with wave.open(str(media_root / parent['audio_file']), 'rb') as stream:
                parents.append(np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype(float) / 32767)
        audio, voice = parents
        transform = row['transform']
        width = round(transform['speech_duration_seconds'] * 16000)
        source_start = round(transform['speech_source_start_seconds'] * 16000)
        insert_start = round(transform['insert_start_seconds'] * 16000)
        audio[insert_start:insert_start + width] += voice[source_start:source_start + width] * transform['voice_gain']
        audio *= transform['global_peak_scale']
        write(row, audio)
    return len(samples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--preregistration', type=Path, required=True)
    parser.add_argument('--media-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--source-root', type=Path)
    parser.add_argument('--vad-preregistration', type=Path)
    parser.add_argument('--ast-cache', type=Path)
    parser.add_argument('--phase', choices=('calibration', 'holdout'), required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    prereg = json.loads(args.preregistration.read_text())
    vad_prereg = json.loads(args.vad_preregistration.read_text()) if args.vad_preregistration else None
    samples = manifest['samples']
    groups = {}
    seen = set()
    for row in samples:
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,160}', row['sample_id'])
                or row['sample_id'] in seen or row['split'] not in {'calibration', 'holdout'}):
            raise ValueError('invalid sample identity/split')
        seen.add(row['sample_id'])
        for group in row.get('source_groups', [row['source_group']]):
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,160}', group):
                raise ValueError('invalid source identity')
            if group in groups and groups[group] != row['split']:
                raise ValueError('source leakage between calibration and holdout')
            groups[group] = row['split']
        if row['audio_file'] != Path(row['audio_file']).name:
            raise ValueError('media file must be a basename')
    if args.prepare_only:
        if args.source_root is None:
            raise ValueError('--prepare-only requires --source-root')
        count = prepare_media(samples, args.source_root, args.media_root)
        print(json.dumps({'reconstructed_samples': count, 'all_audio_sha256_verified': True}))
        return
    samples = [r for r in samples if r['split'] == args.phase]
    args.output.mkdir(parents=True, exist_ok=True)
    raw_root = args.output / 'raw'
    raw_root.mkdir(exist_ok=True)
    lock = {'manifest_sha256': music.file_digest(args.manifest),
            'preregistration_sha256': music.file_digest(args.preregistration),
            'model_files': music.MODEL_FILES, 'script_sha256': music.file_digest(Path(__file__)),
            'observer_sha256': music.file_digest(Path(music.__file__)),
            'packages': {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'numpy')},
            'vad_preregistration_sha256': music.file_digest(args.vad_preregistration) if args.vad_preregistration else None,
            'phase': args.phase}
    # Atomic immutable lock written before model scores. Holdout refuses to run
    # without one calibration-selected rule and the identical frozen inputs.
    lock_path = args.output / (args.phase + '-lock.json')
    if lock_path.exists() and json.loads(lock_path.read_text()) != lock:
        raise ValueError('experiment identity changed; use a new output directory')
    selected = None
    calibration_path = args.output / 'calibration.json'
    if args.phase == 'holdout':
        calibration = json.loads(calibration_path.read_text())
        if any(calibration['identity'][k] != lock[k] for k in ('manifest_sha256', 'preregistration_sha256', 'script_sha256', 'observer_sha256', 'packages', 'vad_preregistration_sha256')):
            raise ValueError('holdout identity differs from calibration')
        selected = calibration['selected_policy']
        if selected is None:
            raise ValueError('no feasible calibration policy; holdout must remain sealed')
        if (args.output / 'holdout.json').exists():
            raise ValueError('holdout already evaluated; no repeat tuning')
    if not lock_path.exists():
        with lock_path.open('x') as f:
            json.dump(lock, f, indent=2)
    model = music.require_local_music_model()
    import torch
    torch.set_num_threads(2)
    vad_model = None
    if vad_prereg:
        import faster_whisper
        from faster_whisper.vad import get_vad_model
        model_file = Path(faster_whisper.__file__).parent / 'assets' / vad_prereg['installed_model']['file']
        if (music.file_digest(model_file) != vad_prereg['installed_model']['sha256']
                or importlib.metadata.version('faster-whisper') != vad_prereg['installed_model']['version']):
            raise ValueError('installed auxiliary capability changed')
        vad_model = get_vad_model()
    reports = {}
    timings = []
    started = time.monotonic()
    for row in samples:
        path = args.media_root / row['audio_file']
        if music.file_digest(path) != row['audio_sha256']:
            raise ValueError('sample bytes changed')
        raw_path = raw_root / (row['sample_id'] + '.json')
        begin = time.monotonic()
        existing = raw_path if raw_path.exists() else (args.ast_cache / raw_path.name if args.ast_cache else raw_path)
        reused = existing.exists()
        report = json.loads(existing.read_text()) if reused else music.classify_music(path, model)
        # Validate identity even when replaying an existing local experiment.
        assess_candidate(row, report, {'name': 'A'})
        if not raw_path.exists():
            raw_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True))
        if vad_model is not None:
            import wave
            import numpy as np
            with wave.open(str(path), 'rb') as stream:
                if stream.getframerate() != 16000 or stream.getnchannels() != 1 or stream.getsampwidth() != 2:
                    raise ValueError('auxiliary experiment requires fixed 16kHz mono PCM16')
                audio = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').astype('float32') / 32768
            audio = np.pad(audio, (0, (-len(audio)) % 512))
            vad = {'audio_sha256': row['audio_sha256'], 'duration_seconds': row['duration_seconds'],
                   'model_sha256': vad_prereg['installed_model']['sha256'],
                   'scores': [round(float(score), 6) for score in vad_model(audio).ravel()]}
            (args.output / 'vad').mkdir(exist_ok=True)
            (args.output / 'vad' / (row['sample_id'] + '.json')).write_text(json.dumps(vad))
            report['_auxiliary_vad'] = vad
        reports[row['sample_id']] = report
        timings.append({'sample_id': row['sample_id'], 'seconds': time.monotonic()-begin,
                        'reused': reused, 'windows': len(report['windows'])})
        vocal = max(w['scores'][label] for w in report['windows'] for label in music.VOCAL_LABELS | EXTRA_VOCALS)
        print(json.dumps({'phase': args.phase, 'sample': row['sample_id'], 'windows': len(report['windows']),
                          'music_min': min(w['scores']['Music'] for w in report['windows']),
                          'vocal_max': vocal, 'seconds': timings[-1]['seconds']}, ensure_ascii=False), flush=True)
    if args.phase == 'calibration':
        comparisons = [summarize(samples, reports, policy) for policy in policies(prereg, vad_prereg)]
        feasible = [r for r in comparisons[1:] if r['gate_passed']]
        # A is simpler and preferred if sufficient. Otherwise strongest B first.
        feasible.sort(key=lambda r: ({'A': 0, 'B': 1, 'C': 2}[r['policy']['name']], -r['policy'].get('music_min', .8),
                                      -r['policy'].get('coverage_min', 1), r['policy'].get('unknown_max_seconds', 0),
                                      r['policy'].get('edge_transition_seconds', 0),
                                      -r['policy'].get('vad_threshold', 0), -r['policy'].get('vad_min_contiguous_ms', 0)))
        selected = feasible[0]['policy'] if feasible else None
        first = next(r for r in samples if r['expected'] == 'instrumental_music')
        checks = technical_checks(first, reports[first['sample_id']])
        invalid_path = args.output / 'invalid-audio.fixture'
        invalid_path.write_bytes(b'Easel deterministic invalid audio fixture')
        import subprocess
        try:
            music.classify_music(invalid_path, model)
        except (ValueError, subprocess.SubprocessError):
            rejected = True
        else:
            rejected = False
        checks.append({'case': 'decoding_failure', 'rejected': rejected})
        if not all(r['rejected'] for r in checks):
            selected = None
        result = {'identity': lock, 'selected_policy': selected, 'comparisons': comparisons,
                  'technical_checks': checks, 'timings': timings, 'total_seconds': time.monotonic()-started}
    else:
        result = {'identity': lock, 'selected_policy': selected,
                  'assessment': summarize(samples, reports, selected), 'timings': timings,
                  'total_seconds': time.monotonic()-started}
    (args.output / (args.phase + '.json')).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'phase': args.phase, 'selected_policy': selected,
                      'gate_passed': result.get('assessment', {}).get('gate_passed', selected is not None),
                      'total_seconds': result['total_seconds']}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
