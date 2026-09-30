"""Lower the frozen Director's music ducking into Hypit's native AudioTrack."""
from __future__ import annotations

import html
import json
import math
import os
import re
import tempfile
from fractions import Fraction
from pathlib import Path

from .narration import _attrs, _frames, _one

BEGIN = '<!-- Easel measured music: begin -->'
END = '<!-- Easel measured music: end -->'
IMPORT = '<import as="easelmix" from="@easel/audio-mix@1"/>'


def install_music_component(root: Path) -> None:
    """Only checked-in implementation bytes may enter the executable package."""
    for name in ('package.json', 'activation.mjs', 'envelope.mjs'):
        target = root / 'packages/audio-mix' / name
        for parent in (target, *target.parents):
            if parent == root:
                break
            if parent.is_symlink():
                raise ValueError('配乐组件不能经过符号链接')
        expected = (Path(__file__).with_name('native_audio') / name).read_bytes()
        if target.exists() and target.read_bytes() != expected:
            raise ValueError('配乐组件与已核对版本不一致，拒绝覆盖')
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(prefix='.component-', dir=target.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(expected)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, target)
            finally:
                Path(temporary).unlink(missing_ok=True)


def music_envelope(cues: list[dict], offset: float, duration: float, policy: dict) -> list[dict]:
    if set(policy) != {'gain_ratio', 'attack_seconds', 'release_seconds'}:
        raise ValueError('配乐压低参数不完整')
    ratio, attack, release = (policy[k] for k in ('gain_ratio', 'attack_seconds', 'release_seconds'))
    if (any(type(v) not in (int, float) or not math.isfinite(v) for v in (ratio, attack, release))
            or not 0 < ratio < 1 or not 0 < attack <= 2 or not 0 < release <= 2):
        raise ValueError('配乐压低参数越界')
    # Merge short breathing gaps: no pump back to full music between sentences.
    windows = []
    for cue in cues:
        start = max(0., offset + cue['start_seconds'])
        end = min(duration, offset + cue['end_seconds'])
        if windows and start - attack <= windows[-1][1] + release:
            windows[-1][1] = max(windows[-1][1], end)
        else:
            windows.append([start, end])
    def sample(seconds: float) -> int:
        return math.floor(seconds * 48000 + 0.5)  # Native positive sample rounding.

    points = {0: 1., sample(duration): 1.}
    for start, end in windows:
        # Reconstruct the leading/trailing ramp; merged windows hold the floor.
        start_sample = sample(max(0, start - attack))
        end_sample = sample(min(duration, end + release))
        floor_start, floor_end = sample(start), sample(end)
        points[start_sample] = 1.
        points[floor_start] = ratio
        points[floor_end] = ratio
        if end_sample > floor_end:
            points[end_sample] = 1.
    return [{'sample': sample, 'gain': gain} for sample, gain in sorted(points.items())]


def compile_music_ducking(source: str, timings: dict, sources: dict[str, str], bgm_ids: set[str], policy: dict | None) -> str:
    if not policy or not bgm_ids:
        return source
    audio = {_attrs(m[0]).get('src'): _attrs(m[0]).get('id')
             for m in re.finditer(r'<media:Audio\b[^>]*/?>', source)}
    voices = [r for r in timings.get('assets', []) if sources.get(r['asset_id']) in audio]
    music = {audio[sources[i]] for i in bgm_ids if sources.get(i) in audio}
    if not music:
        return source
    if len(voices) != 1:
        raise ValueError('配乐压低需要当前旁白的可信句级时序')
    timeline = _attrs(_one(r'<time:Timeline\b[^>]*/?>', source, 'Timeline')[0])
    clock = next((_attrs(m[0]) for m in re.finditer(r'<time:Clock\b[^>]*/?>', source)
                  if '{' + _attrs(m[0]).get('id', '') + '}' == timeline.get('clock')), {})
    fps = Fraction(clock.get('frame-rate', '0'))
    duration = float(_frames(timeline['end'], fps) / fps)
    norms = {_attrs(m[0]).get('id'): _attrs(m[0]).get('source')
             for m in re.finditer(r'<pipeline:Normalize\b[^>]*/?>', source)}
    voice_norms = {name for name, ref in norms.items() if ref == '{' + audio[sources[voices[0]['asset_id']]] + '}'}
    music_norms = {name for name, ref in norms.items() if ref in {'{' + i + '}' for i in music}}
    tracks = list(re.finditer(r'<audio:Track\b[^>]*>.*?</audio:Track>', source, re.DOTALL))
    voice_items = [_attrs(i[0]) for t in tracks for i in re.finditer(r'<audio:Item\b[^>]*/?>', t[0])
                   if _attrs(i[0]).get('source') in {'{' + n + '.media}' for n in voice_norms}]
    if len(voice_items) != 1:
        raise ValueError('配乐压低不能确定旁白的实际位置')
    offset = float(_frames(voice_items[0].get('at', '0f'), fps) / fps)
    points = music_envelope(voices[0]['cues'], offset, duration, policy)
    encoded = html.escape(json.dumps(points, separators=(',', ':')), quote=True)
    declarations = []
    for track in tracks:
        items = [_attrs(i[0]) for i in re.finditer(r'<audio:Item\b[^>]*/?>', track[0])]
        music_refs = {'{' + n + '.media}' for n in music_norms}
        if not any(i.get('source') in music_refs for i in items):
            continue
        if any(i.get('source') not in music_refs for i in items):
            raise ValueError('配乐压低不能影响同轨的旁白或音效')
        track_id = _attrs(track[0].split('>', 1)[0])['id']
        duck_id = 'easel-duck-' + track_id
        declarations.append(f'<easelmix:Duck id="{duck_id}" source={{{track_id}.audio}} points="{encoded}"/>')
        refs = [m for m in re.finditer(r'<film:Track\b[^>]*/>', source)
                if _attrs(m[0]).get('source') in {'{' + track_id + '.audio}', '{' + duck_id + '.audio}'}]
        if len(refs) != 1:
            raise ValueError('配乐需要唯一的 Film 引用，不能叠加原音轨')
        ref = refs[0]
        source = source[:ref.start()] + f'<film:Track source={{{duck_id}.audio}}/>' + source[ref.end():]
    if not declarations:
        raise ValueError('配乐未编排到独立音轨')
    block = BEGIN + '\n' + '\n'.join(declarations) + '\n' + END
    if BEGIN in source or END in source:
        match = _one(re.escape(BEGIN) + '.*?' + re.escape(END), source, '配乐压低区域')
        source = source[:match.start()] + block + source[match.end():]
    else:
        film = _one(r'<film:Film\b', source, 'Film')
        source = source[:film.start()] + block + '\n' + source[film.start():]
    if IMPORT not in source:
        imports = list(re.finditer(r'<import\b[^>]*/>', source))
        end = imports[-1].end()
        source = source[:end] + '\n' + IMPORT + source[end:]
    return source
