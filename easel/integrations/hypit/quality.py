"""Output-bound measurements and system review; never human acceptance."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

from .errors import HypitIntegrationError
from .narration import _attrs, _frames

SCHEMA = 'easel-output-quality@5'
VISUAL_CHECKS = ('visual_match', 'readability', 'mode', 'creator', 'truth_expression', 'narrative')
CONTENT_CHECKS = frozenset({'creator', 'truth_expression', 'narrative'})
MAX_OBSERVATION_ROUNDS = 3


def _unresolved_check(key: str, check: dict) -> bool:
    return (check.get('status') == 'unknown' or (key in CONTENT_CHECKS
            and check.get('status') == 'fail' and check.get('repair_target') == 'unknown'))


def needs_reobservation(report: dict) -> bool:
    """Incomplete observations get bounded review, never permission to rebuild."""
    round_number = report.get('observation_round', 1)
    unknown = report.get('status') == 'INCOMPLETE' or any(
        _unresolved_check(key, check)
        for batch in report.get('visual', []) for key, check in batch.get('checks', {}).items())
    return (report.get('status') in {'INCOMPLETE', 'REPAIR_REQUIRED'} and unknown
            and type(round_number) is int and 1 <= round_number < MAX_OBSERVATION_ROUNDS)


def repair_request(attempt: dict) -> dict | None:
    """Translate evidenced local defects; never fabricate a human rejection."""
    report = attempt.get('review', {}).get('system', {})
    binding = report.get('binding', {})
    output = attempt.get('outputs', {}).get(binding.get('output_name'), {})
    if (report.get('schema') != SCHEMA or report.get('status') != 'REPAIR_REQUIRED'
            or not output or binding.get('sha256') != output.get('sha256')):
        return None
    scopes, feedback = set(), []
    for defect in report.get('measurements', {}).get('defects', []):
        kind = defect.get('kind')
        if kind == 'near_black':
            scopes.add('visual')
        elif kind in {'silent_audio', 'audio_clipping', 'voice_masked', 'voice_missing', 'music_missing'}:
            scopes.add('audio')
        else:
            return None  # Missing alignment is an evidence gap, not permission to repurchase speech.
        feedback.append({'kind': 'quality', 'text': defect['reason'], 'time_seconds': defect['time_seconds']})
    offset = 0
    for batch in report.get('visual', []):
        for key, check in batch.get('checks', {}).items():
            if check.get('status') == 'unknown':
                return None
            if check.get('status') != 'fail':
                continue
            if key == 'readability':
                scopes.add('captions')
            elif key in {'visual_match', 'mode'}:
                scopes.add('visual')
                if key == 'visual_match':
                    scopes.add('visual_material')
            elif key in CONTENT_CHECKS and check.get('repair_target') in {'visual', 'visual_material'}:
                scopes.add('visual')
                if check['repair_target'] == 'visual_material':
                    scopes.add('visual_material')
            elif key in CONTENT_CHECKS and check.get('repair_target') == 'planning':
                scopes.add('planning')
            else:
                return None  # Unknown responsibility cannot authorize a rewrite.
            indices = check.get('frame_indices', [])
            if not indices:
                return None
            for index in indices:
                absolute = batch.get('frame_offset', offset) + index
                if not 0 <= absolute < len(report.get('frames', [])):
                    return None
                feedback.append({'kind': 'quality', 'text': check['reason'],
                                 'time_seconds': report['frames'][absolute]['time_seconds']})
        offset += len(batch.get('frames', []))
    if not feedback:
        return None
    return {**binding, 'origin': 'system_quality', 'allowed_changes': sorted(scopes), 'feedback': feedback,
            'quality_report_sha256': hashlib.sha256(json.dumps(report, sort_keys=True).encode()).hexdigest()}


def _decode(path: Path, *options: str) -> bytes:
    try:
        result = subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                                 '-protocol_whitelist', 'file,pipe', '-i', str(path), *options, 'pipe:1'],
                                capture_output=True, timeout=60, check=False)
    except subprocess.TimeoutExpired as exc:
        raise HypitIntegrationError('本地成片分析超时；已保留视频，可重试分析') from exc
    if result.returncode:
        raise HypitIntegrationError('无法解码当前成片或旁白进行质量检查')
    return result.stdout


def audio_measurements(output: np.ndarray, voice: np.ndarray | None = None,
                       offset: float = 0, cues: list[dict] | None = None) -> dict:
    """Measure signal preservation/masking, not pronunciation or ASR accuracy."""
    if len(output) == 0 or not np.isfinite(output).all():
        raise HypitIntegrationError('成片音频测量为空或无效')
    if voice is not None and not np.isfinite(voice).all():
        raise HypitIntegrationError('准入旁白包含无效音频采样，不能作比较依据')
    defects = []
    rms = float(np.sqrt(np.mean(output.astype(float) ** 2)))
    clipping = float(np.mean(np.abs(output) >= .999))
    if rms < .0001:
        defects.append({'kind': 'silent_audio', 'reason': '成片音轨接近静音', 'time_seconds': 0.})
    if clipping > .01:
        defects.append({'kind': 'audio_clipping', 'reason': '成片音轨存在持续满幅削波', 'time_seconds': 0.})
    windows = []
    if voice is not None:
        for cue in cues or []:
            # Cover every measured sentence, including its tail. Skip actual
            # source silence, never a missing/quiet region of the output.
            for begin in np.arange(cue['start_seconds'], cue['end_seconds'], .5):
                stop = min(begin + .5, cue['end_seconds'])
                start, end = round(begin * 16000), round(stop * 16000)
                reference = voice[start:end].astype(float)
                if len(reference) < 800 or float(np.mean(reference ** 2)) < 1e-6:
                    continue
                position = round((offset + begin) * 16000)
                margin = 640  # +/-40 ms tolerates codec alignment, not missing words.
                left, right = max(0, position - margin), min(len(output), position + len(reference) + margin)
                candidates = output[left:right].astype(float)
                if len(candidates) < len(reference):
                    windows.append({'time_seconds': round(offset + begin, 4), 'correlation': 0., 'snr_db': -100.})
                    continue
                dot = np.correlate(candidates, reference, mode='valid')
                summed = np.concatenate(([0.], np.cumsum(candidates ** 2)))
                energy = summed[len(reference):] - summed[:-len(reference)]
                ref_energy = float(reference @ reference)
                correlations = dot / np.sqrt(np.maximum(energy * ref_energy, 1e-20))
                index = int(np.argmax(correlations))
                gain = float(dot[index] / ref_energy)
                residual = max(float(energy[index] - dot[index] ** 2 / ref_energy), 1e-12)
                snr = 10 * np.log10(max(gain ** 2 * ref_energy, 1e-12) / residual)
                windows.append({'time_seconds': round(offset + begin, 4),
                                'correlation': round(float(correlations[index]), 4),
                                'snr_db': round(float(snr), 2), 'estimated_voice_gain': round(gain, 4),
                                'alignment_offset_ms': round((left + index - position) / 16, 2)})
        if not windows:
            defects.append({'kind': 'voice_unverifiable', 'reason': '旁白没有可比较的有效声音区间', 'time_seconds': offset})
        for window in windows:
            if window['correlation'] < .45 or window.get('estimated_voice_gain', 0) < .05:
                defects.append({'kind': 'voice_missing', 'reason': '成片未保留该段旁白的可辨识信号', **window})
            elif window['snr_db'] < 6:
                defects.append({'kind': 'voice_masked', 'reason': '该段旁白相对其他声音偏弱', **window})
    return {'rms': round(rms, 6), 'clipped_fraction': round(clipping, 6),
            'voice_windows': windows, 'defects': defects,
            'scope': 'signal_preservation_and_masking; not ASR or listening approval'}


def measure_output(path: Path, metadata: dict, voice_path: Path | None, offset: float, cues: list[dict]):
    duration = metadata.get('duration_seconds')
    if not isinstance(duration, (int, float)) or not 0 < duration <= 300:
        raise HypitIntegrationError('当前质量分析支持五分钟以内的有限成片')
    raw = _decode(path, '-an', '-vf', 'fps=2,scale=160:90', '-pix_fmt', 'gray', '-f', 'rawvideo', '-t', str(duration))
    if not raw or len(raw) % (160 * 90):
        raise HypitIntegrationError('成片画面采样不完整')
    frames = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 90, 160)
    dark = np.mean(frames < 12, axis=(1, 2)) > .98
    defects = []
    start = None
    for index, value in enumerate([*dark, False]):
        if value and start is None:
            start = index
        if not value and start is not None:
            if index - start >= 2:
                defects.append({'kind': 'near_black', 'reason': '连续画面几乎全黑，需要核对是否为有意留黑',
                                'time_seconds': start / 2, 'end_seconds': min(duration, index / 2)})
            start = None
    audio = None
    if metadata.get('audio_present'):
        pcm = np.frombuffer(_decode(path, '-vn', '-ac', '1', '-ar', '16000', '-t', str(duration), '-f', 'f32le'), dtype='<f4')
        voice = None if voice_path is None else np.frombuffer(
            _decode(voice_path, '-vn', '-ac', '1', '-ar', '16000', '-t', '300', '-f', 'f32le'), dtype='<f4')
        audio = audio_measurements(pcm, voice, offset, cues)
        defects.extend(audio['defects'])
    elif voice_path is not None:
        defects.append({'kind': 'voice_missing', 'reason': '成片缺少要求的旁白音轨', 'time_seconds': 0.})
    return {'visual_sampling_hz': 2, 'frame_count': len(frames), 'audio': audio, 'defects': defects}


def music_signal_window(output: np.ndarray, reference: np.ndarray,
                        narration: np.ndarray | None = None) -> dict:
    """Measure the music component after projecting out a known voice signal.

    This is a two-source linear comparison, not blind source separation. If
    voice and music are effectively the same waveform, their individual gains
    are not identifiable and the result must remain unknown.
    """
    ref = reference.astype(float)
    samples = output.astype(float)
    if (len(samples) < len(ref) or not len(ref) or not np.isfinite(samples).all()
            or not np.isfinite(ref).all()):
        raise ValueError('配乐对应输出采样不完整或无效')
    energy = float(ref @ ref)
    if energy / len(ref) < 1e-6:
        raise ValueError('配乐采样过静，尚不能核实输出中的信号')
    sums = np.concatenate(([0.], np.cumsum(samples ** 2)))
    energies = sums[len(ref):] - sums[:-len(ref)]
    total_energies = energies.copy()
    projected = False
    if narration is not None:
        voice = narration.astype(float)
        if len(voice) != len(ref) or not np.isfinite(voice).all():
            raise ValueError('旁白比较区间无效')
        voice_energy = float(voice @ voice)
        if voice_energy / len(voice) >= 1e-6:
            original_energy = energy
            ref -= float(ref @ voice) / voice_energy * voice
            energy = float(ref @ ref)
            if energy < .05 * original_energy:
                raise ValueError('旁白与配乐信号过于相似，无法分别核实')
            voice_dot = np.correlate(samples, voice, mode='valid')
            energies = np.maximum(0., energies - voice_dot ** 2 / voice_energy)
            projected = True
    dot = np.correlate(samples, ref, mode='valid')
    correlations = np.clip(dot / np.sqrt(np.maximum(energies * energy, 1e-20)), -1., 1.)
    if projected:
        # Both sources share the codec displacement. Selecting only the best
        # music partial correlation can lock onto unrelated residual noise at
        # a displacement that no longer aligns the dominant narration.
        alignment = (voice_dot ** 2 / voice_energy + dot ** 2 / energy) / np.maximum(total_energies, 1e-20)
        alignment[(voice_dot < 0) | (dot < -1e-8 * energy)] = -1.  # Allow round-off around absent music.
        best = int(np.argmax(alignment))
    else:
        best = int(np.argmax(correlations))
    return {'correlation': round(float(correlations[best]), 4),
            'estimated_gain': round(float(dot[best] / energy), 6), 'voice_projected': projected}


def measure_music(path: Path, duration: float, author: str, plan, bundle, store,
                  voice_span: tuple[float, float] | None, voice_path: Path | None = None) -> dict:
    """Probe admitted BGM in the mix, without claiming a listening review.

    Only native once/loop audio placement is reconstructed. An
    unsupported transform or inseparable signals are an evidence gap, never
    an automatic pass or authority to buy another soundtrack.
    """
    from fractions import Fraction
    from . import service

    needs = [n for n in plan.needs if getattr(n.modality_spec, 'kind', None) == 'bgm']
    result = {'scope': 'sampled BGM signal presence with known narration projection; not music style or vocals',
              'assets': [], 'defects': []}
    if not needs:
        return result
    audio = [_attrs(m[0]) for m in re.finditer(r'<media:Audio\b[^>]*/>', author)]
    norms = [_attrs(m[0]) for m in re.finditer(r'<pipeline:Normalize\b[^>]*/>', author)]
    items = [_attrs(m[0]) for m in re.finditer(r'<audio:Item\b[^>]*/>', author)]
    timelines = [_attrs(m[0]) for m in re.finditer(r'<time:Timeline\b[^>]*/>', author)]
    clocks = [_attrs(m[0]) for m in re.finditer(r'<time:Clock\b[^>]*/>', author)]
    pcm, voice_pcm = None, None
    for need in needs:
        matched = {m.asset_id for m in bundle.matches if m.need_id == need.need_id and m.qualified}
        candidates = [(a, media) for a in bundle.assets if a.asset_id in matched for media in audio
                      if media.get('src') == store.hypit_source_path(a, 'productions/easel-authoring/authors/main.svml')]
        if not candidates and need.importance.value != 'required':
            continue  # Optional, unused music is not required to appear in output.
        row = {'need_id': need.need_id, 'windows': []}
        result['assets'].append(row)
        try:
            if len(candidates) != 1 or len(timelines) != 1:
                raise ValueError('没有唯一的已选配乐或播放时间线')
            asset, media = candidates[0]
            row.update(asset_id=asset.asset_id, sha256=asset.file.sha256)
            source = store.resolve_asset_locator(asset.file.path)
            if service._sha256_file(source) != asset.file.sha256:
                raise HypitIntegrationError('已选配乐字节已变化，不能核对错误版本')
            normalized = [n for n in norms if n.get('source') == '{' + media['id'] + '}']
            if (len(normalized) != 1 or set(normalized[0]) - {'id', 'source', 'video', 'audio', 'span-authority', 'clock'}
                    or normalized[0].get('audio') != 'default'
                    or normalized[0].get('clock') != timelines[0].get('clock')):
                raise ValueError('配乐包含尚不能重建的媒体变换')
            clips = [i for i in items if i.get('source') == '{' + normalized[0]['id'] + '.media}']
            clock = [c for c in clocks if '{' + c.get('id', '') + '}' == timelines[0].get('clock')]
            if len(clips) != 1 or len(clock) != 1:
                raise ValueError('配乐包含多个片段或时钟不明确')
            clip = clips[0]
            if (set(clip) - {'id', 'source', 'at', 'for', 'during', 'playback', 'gain', 'fade-in', 'fade-out', 'trim-start', 'trim-end'}
                    or clip.get('playback') not in {None, 'once', 'once-start', 'once-end', 'loop', 'loop-start', 'loop-end'}):
                raise ValueError('配乐播放变换尚无可比较的声音依据')
            fps = Fraction(clock[0]['frame-rate'])
            def seconds(value):
                # Audio trim/fade durations resolve to samples, not whole video
                # frames (e.g. native 600ms at 24fps is valid).
                match = re.fullmatch(r'([0-9]+(?:\.[0-9]+)?)(ms|s|f)', value)
                if not match:
                    raise ValueError('声音时长表达尚不能换算为实际采样')
                return float(Fraction(match[1]) / {'ms': 1000, 's': 1, 'f': fps}[match[2]])
            if clip.get('during') == timelines[0]['id'] and 'at' not in clip and 'for' not in clip:
                start, stop = 0., duration
            elif 'during' not in clip and 'at' in clip and 'for' in clip:
                start = float(_frames(clip['at'], fps) / fps)
                stop = min(duration, start + float(_frames(clip['for'], fps) / fps))
            else:
                raise ValueError('配乐播放范围不明确')
            reference = np.frombuffer(_decode(source, '-vn', '-ac', '1', '-ar', '16000', '-t', '300', '-f', 'f32le'), dtype='<f4')
            trim_start = round(seconds(clip.get('trim-start', '0s')) * 16000)
            trim_end = round(seconds(clip['trim-end']) * 16000) if 'trim-end' in clip else len(reference)
            if not 0 <= trim_start < trim_end <= len(reference):
                raise ValueError('配乐截取超出可核对的源声音范围')
            reference = reference[trim_start:trim_end]
            if not len(reference) or not np.isfinite(reference).all():
                raise ValueError('配乐没有有效声音采样')
            loop = str(clip.get('playback', 'once')).startswith('loop')
            align_end = str(clip.get('playback', '')).endswith('-end')
            window_samples = round((stop - start) * 16000)
            phase = (len(reference) - window_samples % len(reference)) % len(reference) if loop and align_end else 0
            if not loop:
                audible = min(window_samples, len(reference))
                if align_end:
                    start = stop - audible / 16000
                    reference = reference[-audible:]
                else:
                    stop = start + audible / 16000
                    reference = reference[:audible]
            # Avoid authored fades, narration (including untranscribed gaps),
            # and the frozen Mode's maximum supported ducking release (2s).
            fade_in = seconds(clip.get('fade-in', '0s'))
            fade_out = seconds(clip.get('fade-out', '0s'))
            all_moments = [float(t) for t in np.arange(start + max(1., fade_in), stop - max(1., fade_out), 1.)
                           if t + 1 <= stop - max(1., fade_out)]
            moments = [t for t in all_moments if voice_span is None or t + 1 <= voice_span[0] - 2 or t >= voice_span[1] + 2]
            project_voice = len(moments) < 2 and voice_span is not None
            if project_voice and voice_path is not None:
                moments = all_moments
                if voice_pcm is None:
                    voice_pcm = np.frombuffer(_decode(voice_path, '-vn', '-ac', '1', '-ar', '16000', '-t', '300', '-f', 'f32le'), dtype='<f4')
                    if not len(voice_pcm) or not np.isfinite(voice_pcm).all():
                        raise ValueError('缺少有效的准入旁白声音，不能核对重叠配乐')
            if len(moments) < 2:
                raise ValueError('旁白以外没有足够的配乐比较区间')
            selected = sorted({moments[0], moments[len(moments) // 2], moments[-1]})
            if pcm is None:
                pcm = np.frombuffer(_decode(path, '-vn', '-ac', '1', '-ar', '16000', '-t', str(duration), '-f', 'f32le'), dtype='<f4')
            for t in selected:
                indices = np.arange(round((t - start) * 16000), round((t - start) * 16000) + 16000)
                ref = reference[(indices + phase) % len(reference)].astype(float)
                energy = float(ref @ ref)
                if energy / len(ref) < 1e-6:
                    continue  # A silent source passage cannot prove presence.
                position = round(t * 16000)
                candidates_pcm = pcm[max(0, position - 640):position + 16640].astype(float)
                if len(candidates_pcm) < len(ref):
                    raise ValueError('配乐对应输出采样不完整')
                voice_ref = None
                if project_voice and voice_pcm is not None:
                    voice_ref = np.zeros(len(ref), dtype=float)
                    positions = np.arange(round((t - voice_span[0]) * 16000), round((t - voice_span[0]) * 16000) + len(ref))
                    valid = (positions >= 0) & (positions < len(voice_pcm))
                    voice_ref[valid] = voice_pcm[positions[valid]]
                row['windows'].append({'time_seconds': round(t, 4),
                                      **music_signal_window(candidates_pcm, ref, voice_ref)})
            if len(row['windows']) < 2:
                raise ValueError('配乐采样过静，尚不能核实输出中的信号')
            for window in row['windows']:
                if window['correlation'] < .65 or window['estimated_gain'] < .0005:
                    result['defects'].append({'kind': 'music_missing', 'need_id': need.need_id,
                        'reason': '该段未检出已选配乐的可辨识信号，需要核对混音', **window})
        except HypitIntegrationError:
            raise
        except (ValueError, KeyError, ZeroDivisionError) as exc:
            result['defects'].append({'kind': 'music_unverifiable', 'need_id': need.need_id,
                'reason': '配乐信号尚不能核实：' + str(exc), 'time_seconds': 0.})
    return result


def validate_visual_review(manifest: dict, report: dict) -> None:
    from .secrets import SecretRedactor
    if SecretRedactor.contains_secret(report):
        raise ValueError('审片报告包含不允许保存的敏感内容')
    if (report.get('schema') != SCHEMA or report.get('input_sha256') != manifest['input_sha256']
            or not isinstance(report.get('checks'), dict) or set(report['checks']) != set(VISUAL_CHECKS)):
        raise ValueError('审片报告与当前输出或检查范围不一致')
    frames = report.get('frames')
    if (not isinstance(frames, list) or [f.get('index') for f in frames if isinstance(f, dict)]
            != list(range(len(manifest['frames'])))
            or any(type(f.get('observed')) is not bool or not isinstance(f.get('description'), str)
                   or not f['description'].strip() or len(f['description']) > 4000 for f in frames)):
        raise ValueError('系统审片必须逐张说明实际看到的成片预览')
    for key, check in report['checks'].items():
        if (not isinstance(check, dict) or check.get('status') not in {'pass', 'fail', 'unknown'}
                or not isinstance(check.get('reason'), str) or not check['reason'].strip() or len(check['reason']) > 4000
                or not isinstance(check.get('frame_indices'), list)
                or any(type(i) is not int or i < 0 or i >= len(frames) for i in check['frame_indices'])):
            raise ValueError('审片结论缺少有效状态与具体画面依据')
        if check['status'] == 'pass' and (not all(f['observed'] for f in frames) or not check['frame_indices']):
            raise ValueError('未看到画面或未引用依据不能通过审片')
        if check['status'] == 'fail' and (not check['frame_indices']
                or not all(frames[i]['observed'] for i in check['frame_indices'])):
            raise ValueError('缺陷必须引用已观察画面，证据不足应记为未知')
        if (key in CONTENT_CHECKS and check['status'] == 'fail'
                and check.get('repair_target') not in {'visual', 'visual_material', 'planning', 'unknown'}):
            raise ValueError('内容表达缺陷应区分画面修正、素材替换、内容调整或尚未定位')


def inspect_output(attempt_id: str, *, executor) -> dict:
    from fractions import Fraction
    from . import service
    from .handoff import load_frozen_creative_mode
    from easel.integrations.material_layer import PlanningIntegration, MaterialGateIntegration
    from easel.materials.application.voice_delivery import authoring_voice_timings
    from easel.materials.store import AttemptMaterialStore
    attempt = service.get_film_attempt(attempt_id)
    if attempt.get('execution_status') != 'BUILD_COMPLETE':
        raise HypitIntegrationError('只有已完成制作的导出视频可以进入系统审片')
    fingerprint = attempt.get('build', {}).get('operation', {}).get('execution_fingerprint', {}).get('sha256')
    if not fingerprint or service._execution_fingerprint(attempt)['sha256'] != fingerprint:
        raise HypitIntegrationError('当前编排输入与该视频实际提交时不一致，不能核对错误版本')
    outputs = attempt.get('outputs', {})
    if len(outputs) != 1:
        raise HypitIntegrationError('系统审片需要唯一的当前导出视频')
    name, output = next(iter(outputs.items()))
    path = service._output_path(attempt, output)
    if service._file_sha256(path) != output.get('sha256'):
        raise HypitIntegrationError('成片字节已变化，不能沿用审片身份')
    binding = {'output_name': name, 'sha256': output['sha256']}
    mode, mode_hash = load_frozen_creative_mode(attempt)
    root = Path(attempt['workspace']['path'])
    planning = PlanningIntegration().load(attempt)
    # load_frozen_creative_mode verifies every handoff hash, including these
    # existing files. Review must judge this Creator and this Content, not just
    # a generic Mode applied to whatever script happened to be rendered.
    try:
        context = {key: json.loads((root / 'handoff' / filename).read_text()) for key, filename in (
            ('creator_context', 'creator-context.json'), ('content_core', 'content-core.json'),
            ('truth', 'truth-packet.json'))}
        context.update(treatment=planning['treatment'], scenes=planning['scenes'])
    except (OSError, KeyError, ValueError) as exc:
        raise HypitIntegrationError('系统审片缺少已冻结的创作者、内容或导演方案，不能核实风格') from exc
    plan, bundle, _ = MaterialGateIntegration().assert_ready(attempt)
    store = AttemptMaterialStore(root)
    author = (root / 'productions/easel-authoring/authors/main.svml').read_text()
    timings = authoring_voice_timings(plan, bundle, store, planning['script'])
    voice_path, offset, cues, voice_span = None, 0., [], None
    for row in timings['assets']:
        asset = next(a for a in bundle.assets if a.asset_id == row['asset_id'])
        src = store.hypit_source_path(asset, 'productions/easel-authoring/authors/main.svml')
        media = next((_attrs(m[0]) for m in re.finditer(r'<media:Audio\b[^>]*/>', author) if _attrs(m[0]).get('src') == src), None)
        if media is None:
            continue
        normalized = next(_attrs(m[0]) for m in re.finditer(r'<pipeline:Normalize\b[^>]*/>', author)
                          if _attrs(m[0]).get('source') == '{' + media['id'] + '}')
        item = next(_attrs(m[0]) for m in re.finditer(r'<audio:Item\b[^>]*/>', author)
                    if _attrs(m[0]).get('source') == '{' + normalized['id'] + '.media}')
        clock = next(_attrs(m[0]) for m in re.finditer(r'<time:Clock\b[^>]*/>', author)
                     if '{' + _attrs(m[0]).get('id', '') + '}' == normalized['clock'])
        fps = Fraction(clock['frame-rate'])
        offset = float(_frames(item['at'], fps) / fps)
        voice_path, cues = store.resolve_asset_locator(asset.file.path), row['cues']
        voice_span = (offset, offset + row['audio_duration_seconds'])
        if service._sha256_file(voice_path) != asset.file.sha256:
            raise HypitIntegrationError('准入旁白已变化，无法核对成片')
        break
    identity = hashlib.sha256(json.dumps({'schema': SCHEMA, 'binding': binding, 'execution': fingerprint, 'mode': mode_hash,
        'script': planning['script'], 'author': author, 'timings': timings, 'context': context,
        'music_needs': [n.model_dump(mode='json') for n in plan.needs if getattr(n.modality_spec, 'kind', None) == 'bgm']}, sort_keys=True).encode()).hexdigest()
    previous = attempt.get('review', {}).get('system', {})
    same_input = previous.get('input_sha256') == identity
    if (same_input and previous.get('status') in {'READY', 'REPAIR_REQUIRED', 'INCOMPLETE'}
            and not needs_reobservation(previous)):
        return attempt
    observation_round = previous.get('observation_round', 1) + 1 if same_input else 1
    pending = attempt.get('review', {}).get('system_pending', {})
    if (pending.get('input_sha256') != identity
            or pending.get('observation_round') != observation_round):
        pending = {}

    def save_review(report, *, complete):
        # Keep the last completed review separate from in-progress evidence.
        # Neither a partial batch nor a transient failure constitutes PASS.
        if service._file_sha256(path) != binding['sha256']:
            raise HypitIntegrationError('检查期间成片发生变化，未保存审片结论')
        if service._execution_fingerprint(service.get_film_attempt(attempt_id))['sha256'] != fingerprint:
            raise HypitIntegrationError('检查期间编排输入发生变化，未保存审片结论')
        def save(item):
            if item.get('outputs', {}).get(name, {}).get('sha256') != binding['sha256']:
                raise HypitIntegrationError('检查期间输出身份变化')
            review = {**item.get('review', {})}
            if complete:
                review['system'] = report
                review.pop('system_pending', None)
            else:
                review['system_pending'] = report
            item['review'] = review
            return service._event(item, 'system_quality_recorded' if complete else 'system_quality_checkpoint',
                                  status=report['status'])
        return service._save_attempt(attempt_id, save)

    measurements = measure_output(path, output['metadata'], voice_path, offset, cues)
    if any(getattr(n.modality_spec, 'kind', None) == 'voice' for n in plan.needs) and voice_path is None:
        measurements['defects'].append({'kind': 'voice_unverifiable', 'reason': '当前旁白缺少可绑定的时序，尚不能核对完整性', 'time_seconds': 0.})
        voice_span = (0., output['metadata']['duration_seconds'])
    music = measure_music(path, output['metadata']['duration_seconds'], author, plan, bundle, store, voice_span, voice_path)
    measurements['music'] = music
    measurements['defects'].extend(music['defects'])
    # Actual output previews, never source thumbnails or authored screenshots.
    duration = output['metadata']['duration_seconds']
    moments = sorted({min(duration - .05, .5), *[min(duration - .05, offset + (c['start_seconds'] + c['end_seconds']) / 2) for c in cues]})
    if len(moments) < 5:
        moments = sorted(set(moments + [duration * n / 6 for n in range(1, 6)]))
    attachments, frames = [], []
    for index, t in enumerate(moments):
        raw = _decode(path, '-ss', str(max(0, t)), '-frames:v', '1', '-vf', 'scale=-2:640', '-f', 'image2pipe', '-vcodec', 'mjpeg')
        if not raw:
            raise HypitIntegrationError('无法取得成片预览，不提交空画面审片')
        buffer = io.BytesIO()
        with Image.open(io.BytesIO(raw)) as image:
            image.save(buffer, format='JPEG', quality=70)
        raw = buffer.getvalue()
        attachments.append({'type': 'image', 'mimeType': 'image/jpeg', 'content': base64.b64encode(raw).decode()})
        frames.append({'index': index, 'time_seconds': round(t, 4), 'sha256': hashlib.sha256(raw).hexdigest()})
    manifest = {'schema': SCHEMA, 'input_sha256': identity, 'binding': binding, 'frames': frames,
                'script': planning['script'], 'mode': mode, 'measurements': measurements,
                **context,
                'scope': 'sampled output frames and measured audio; no claimed full playback'}
    manifest['director'] = {name: (root / 'handoff/creative-mode' / name).read_text()
        for name in ('visual-bible.md', 'editing-bible.md', 'qc-rubric.md')
        if (root / 'handoff/creative-mode' / name).is_file()}
    # Batch readable previews instead of shrinking away subtitle evidence or
    # dropping later sentences. Every batch retains the whole narrative context.
    visual, start = [], 0
    attachment_budget = 90000 - len(json.dumps({**manifest, 'frames': []}, ensure_ascii=False).encode()) - 7000
    while start < len(frames):
        end, size = start, 0
        while end < len(frames) and size + len(attachments[end]['content']) <= min(80000, attachment_budget):
            size += len(attachments[end]['content'])
            end += 1
        if end == start:
            raise HypitIntegrationError('单张成片预览超过审片容量')
        batch = {**manifest, 'frames': [{**f, 'index': i} for i, f in enumerate(frames[start:end])],
                 'frame_offset': start, 'frame_total': len(frames)}
        batch_identity = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest()
        cached = next((v for v in previous.get('visual', [])
                       if same_input and v.get('batch_sha256') == batch_identity), None)
        checkpoint = next((v for v in pending.get('visual', [])
                           if v.get('batch_sha256') == batch_identity), None)
        reusable = checkpoint or (cached if cached is not None
            and all(not _unresolved_check(k, c) for k, c in cached['checks'].items()) else None)
        batch['observation_round'] = reusable['observation_round'] if reusable is not None else observation_round
        batch['review_focus'] = (reusable['review_focus'] if reusable is not None else {
            key: check['reason'][:500] for key, check in (cached or {}).get('checks', {}).items()
            if _unresolved_check(key, check)})
        batch['input_sha256'] = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest()
        report = reusable if reusable is not None else executor(attempt, batch, attachments[start:end])
        validate_visual_review(batch, report)
        visual.append({**report, 'frame_offset': start, 'batch_sha256': batch_identity,
                       'observation_round': batch['observation_round'], 'review_focus': batch['review_focus']})
        if reusable is None:
            save_review({'schema': SCHEMA, 'status': 'CHECKING', 'input_sha256': identity,
                         'binding': binding, 'observation_round': observation_round,
                         'visual': list(visual)}, complete=False)
        start = end
    failed = any(c['status'] == 'fail' for v in visual for c in v['checks'].values())
    unknown = any(c['status'] == 'unknown' for v in visual for c in v['checks'].values())
    report = {'schema': SCHEMA, 'input_sha256': identity, 'binding': binding,
              'observation_round': observation_round,
              'status': 'REPAIR_REQUIRED' if failed or measurements['defects'] else 'INCOMPLETE' if unknown else 'READY',
              'measurements': measurements, 'visual': visual, 'frames': frames,
              'scope': manifest['scope'], 'checked_at': service._now()}
    return save_review(report, complete=True)
