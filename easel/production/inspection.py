"""Bounded actual-media observations for creative and quality tasks."""
from __future__ import annotations
import base64
import hashlib
import json
import math
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import shutil
import subprocess
import tempfile
from .media import probe_media, process_environment, MEDIA_FORMATS, file_sha256, atomic_json, local_path
from .model_tasks import ModelTaskError


def observe_media(path: Path, *, include_audio: bool = False, max_frames: int = 12, frame_times: tuple[float, ...] | None = None) -> tuple[tuple[dict,...],frozenset[str],dict]:
    info=probe_media(path)
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise ModelTaskError('media_inspection_unavailable','本地媒体检查需要 FFmpeg')
    blocks=[];required={'structured'};timestamps=[]
    if info['video']:required.add('image')
    if max_frames < 1:raise ValueError('max_frames must be positive')
    count=max(1,min(max_frames,int(info['duration'] or 1)+1)) if info['video'] else 0
    video=next((stream for stream in info['streams'] if stream.get('codec_type')=='video'),{})
    try:
        fps=float(Fraction(video.get('avg_frame_rate') or video.get('r_frame_rate') or '25'))
        if fps<=0 or not math.isfinite(fps):raise ValueError
    except (ValueError,ZeroDivisionError):fps=25
    # Seek to the last frame's presentation time, not an arbitrary .05 seconds
    # before EOF: a 10 fps file has no frame at .95 of a one-second video.
    video_duration=float(video.get('duration') or info['duration'] or 0)
    last=max(0,video_duration-1/fps-.000001)
    if str(video.get('nb_frames','')).isdigit():
        frame_count=int(video['nb_frames'])
        if frame_count>0:
            last=min(last,max(0,(frame_count-1)/fps-.000001))
            count=min(count,frame_count)
    if frame_times is not None:
        if (not info['video'] or not 1 <= len(frame_times) <= 8 or
                any(not math.isfinite(t) or t < 0 or t > last + .000002 for t in frame_times)):
            raise ValueError('Frame times outside actual video bounds')
        count = len(frame_times)
    with tempfile.TemporaryDirectory(prefix='easel-observe-') as folder:
        for index in range(count):
            # Spread the actual count across the full span, including the tail.
            at=min(frame_times[index],last) if frame_times is not None else (index*last/(count-1) if count>1 else last/2)
            frame=Path(folder)/f'{index}.jpg'
            # Seeking even to zero can discard the sole frame in a still-image
            # demuxer. Decode from the beginning when the requested time is zero.
            seek=['-ss',str(at)] if at>0 else []
            result=subprocess.run([ffmpeg,'-hide_banner','-loglevel','error',*seek,'-protocol_whitelist','file,pipe','-format_whitelist',MEDIA_FORMATS,'-i',str(path),'-frames:v','1','-vf','scale=768:-2','-y',str(frame)],capture_output=True,timeout=30,env=process_environment(Path(folder)))
            if not result.returncode and not frame.is_file():
                # VFR timestamps can be sparse. Decode a bounded tail and retain
                # its last frame; never silently reuse an early screenshot.
                window=min(video_duration,max(2,2/fps))
                result=subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-sseof',str(-window),
                    '-protocol_whitelist','file,pipe','-format_whitelist',MEDIA_FORMATS,'-i',str(path),
                    '-vf','scale=768:-2','-update','1','-y',str(frame)],capture_output=True,timeout=30,env=process_environment(Path(folder)))
                # The exact last VFR timestamp is unavailable here; do not label
                # the substituted tail image as the originally requested instant.
                at=None
            if result.returncode or not frame.is_file():raise ModelTaskError('media_inspection_failed','无法读取实际视频画面')
            label=f'实际画面，时间 {at:.3f} 秒' if at is not None else f'实际尾部画面，来自末尾 {window:.3f} 秒范围（精确时间未测）'
            blocks.extend([{'type':'text','text':label},
                {'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(frame.read_bytes()).decode()}}])
            timestamps.append(at)
        if include_audio and info['audio']:
            # Bound each chunk and retain all intervals; no semantic pass from filenames/transcripts alone.
            required.add('audio')
            for start in range(0,int(info['duration'])+1,30):
                if start>=info['duration']:break
                audio=Path(folder)/f'audio-{start}.wav'
                result=subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-ss',str(start),'-protocol_whitelist','file,pipe','-format_whitelist',MEDIA_FORMATS,'-i',str(path),'-t','30','-vn','-ac','1','-ar','16000','-c:a','pcm_s16le','-y',str(audio)],capture_output=True,timeout=30,env=process_environment(Path(folder)))
                if result.returncode:raise ModelTaskError('media_inspection_failed','无法读取实际视频声音')
                blocks.extend([{'type':'text','text':f'实际音轨，从 {start} 秒开始'},
                    {'type':'input_audio','input_audio':{'data':base64.b64encode(audio.read_bytes()).decode(),'format':'wav'}}])
    return tuple(blocks),frozenset(required),{'frame_times':timestamps,'audio_observed':bool(include_audio and info['audio']),'sampling':'bounded_frames_full_audio'}



def observe_audio_technical(path: Path, *, info: dict | None = None, sample_seconds: float = 10.0, source_start: float = 0.0) -> dict:
    """Bounded real local acoustic measurements, NOT audio understanding/listening.

    Supported for text-and-vision edit planning when the configured model cannot
    accept input_audio. It cannot establish music genre, emotion, lyrics, SFX
    semantic fitness or audiovisual synchrony; final semantic QC stays separate.
    """
    info = info or probe_media(path)
    if not info['audio']:
        return {'audio_present': False, 'auditory_semantics': 'not_tested'}
    if not 0 < sample_seconds <= 15:
        raise ValueError('audio measurement sample must be bounded')
    if not math.isfinite(source_start) or not 0 <= source_start < info['duration']:
        raise ValueError('audio measurement start must lie inside the source')
    measured_seconds = min(sample_seconds, info['duration'] - source_start)
    stream = next((x for x in info['streams'] if x.get('codec_type') == 'audio'), {})
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ModelTaskError('media_inspection_unavailable', '音轨技术检查需要 FFmpeg')
    with tempfile.TemporaryDirectory(prefix='easel-audio-measure-') as folder:
        try:
            result = subprocess.run([
                ffmpeg, '-hide_banner', '-nostdin', '-loglevel', 'info',
                '-protocol_whitelist', 'file,pipe', '-format_whitelist', MEDIA_FORMATS,
                '-ss', str(source_start), '-i', str(path), '-map', '0:a:0', '-t', str(measured_seconds),
                '-af', 'volumedetect', '-f', 'null', '-'
            ], capture_output=True, timeout=25, env=process_environment(Path(folder)))
        except subprocess.TimeoutExpired:
            raise ModelTaskError('audio_measurement_failed', '音轨技术测量超时') from None
    if result.returncode != 0:
        raise ModelTaskError('audio_measurement_failed', '音轨技术测量失败') from None
    stderr = result.stderr.decode('utf-8', 'replace')
    import re
    levels = {}
    for name in ('mean', 'max'):
        match = re.search(r'\b' + name + r'_volume:\s*(-?(?:\d+(?:\.\d+)?|inf)) dB', stderr)
        if match:
            levels[name + '_volume_db'] = match.group(1)
    return {
        'audio_present': True, 'duration_seconds': round(info['duration'], 3),
        'codec': str(stream.get('codec_name', 'unknown'))[:40],
        'channels': stream.get('channels'), 'sample_rate': str(stream.get('sample_rate',''))[:20],
        'measured_seconds': round(measured_seconds, 3), 'source_start': source_start,
        **levels, 'measurement': 'ffprobe_and_ffmpeg_volumedetect',
        'heard_by_model': False, 'auditory_semantics': 'not_tested'
    }

VIDEO_DIALECTS = frozenset({'qwen-omni-video-url', 'qwen-vl-video-url', 'minimax-video-url'})
MAX_VIDEO_BASE64 = 9_900_000  # Qwen's documented encoded payload ceiling is <10 MB.
INSPECTION_VERSION = 'native-video-1'


@dataclass(frozen=True)
class VideoChunk:
    start: float
    end: float
    path: Path
    sha256: str
    audio: bool

    def evidence(self) -> dict:
        return {'start': self.start, 'end': self.end, 'sha256': self.sha256,
                'audio_in_video': self.audio, 'filename': self.path.name}

    def blocks(self) -> tuple[dict, ...]:
        if self.path.is_symlink() or not self.path.is_file() or file_sha256(self.path) != self.sha256:
            raise ModelTaskError('inspection_changed', '审片媒体片段发生变化，不能继续使用旧审阅结果')
        data = base64.b64encode(self.path.read_bytes()).decode('ascii')
        if len(data) >= MAX_VIDEO_BASE64:
            raise ModelTaskError('inspection_too_large', '实际视频片段超过模型输入限制')
        return ({'type': 'text', 'text': f'实际成片片段：全片时间 {self.start:.6f}–{self.end:.6f} 秒；'
                 f'片段内时间从 0 开始；实际音轨：{self.audio}。'},
                {'type': 'video_url', 'video_url': {'url': 'data:video/mp4;base64,' + data}})


def native_video_requirements(transport, *, audio: bool) -> tuple[str, float, frozenset[str]]:
    """Capabilities are configured assertions, never inferred from an API URL/model name."""
    dialect = getattr(transport, 'video_dialect', '')
    if dialect not in VIDEO_DIALECTS:
        raise ModelTaskError('video_protocol_unavailable', '完整审片需要明确配置支持实际视频文件的模型协议')
    required = frozenset({'text', 'structured', 'video'} | ({'audio'} if audio else set()))
    if not required <= getattr(transport, 'capabilities', frozenset()):
        raise ModelTaskError('capability_unavailable', '当前模型缺少完整审片所需的视频或声音能力')
    if audio and dialect != 'qwen-omni-video-url':
        raise ModelTaskError('audio_video_protocol_unavailable', '已配置的视频协议只读取画面，不能确认有声作品的完整质量')
    try:
        seconds = float(getattr(transport, 'quality_chunk_seconds', 30))
        if not math.isfinite(seconds) or not 1 <= seconds <= 60:
            raise ValueError
    except (ValueError, TypeError):
        raise ModelTaskError('inspection_configuration_invalid', '审片分段时长需要在 1～60 秒之间') from None
    return dialect, seconds, required


def _video_chunks_complete(chunks: tuple[VideoChunk, ...], duration: float) -> bool:
    covered = 0.0
    for chunk in chunks:
        if chunk.start > covered + 0.000001 or chunk.end <= chunk.start or chunk.start < 0:
            return False
        covered = max(covered, chunk.end)
    return bool(chunks) and abs(covered - duration) < 0.000001


def prepare_video_chunks(path: Path, *, cache_root: Path, seconds: float = 30) -> tuple[tuple[VideoChunk, ...], dict]:
    """Cache real, full-resolution clips before any model call for byte-stable replay.

    Adjacent clips overlap by up to one second so edits at boundaries are visible.
    Payload pressure shortens a clip; it never drops frames, scales the image,
    drops audio or changes the delivered movie. This is input coverage, not proof
    that a provider internally examines every frame.
    """
    if not math.isfinite(seconds) or not 1 <= seconds <= 60:
        raise ModelTaskError('inspection_configuration_invalid', '审片分段时长需要在 1～60 秒之间')
    info = probe_media(path)
    duration = float(info['duration'])
    if not info['video'] or not math.isfinite(duration) or not 0 < duration <= 901:
        raise ModelTaskError('media_inspection_failed', '无法确认实际成片的完整视频时长')
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise ModelTaskError('media_inspection_unavailable', '本地媒体检查需要 FFmpeg')
    source_sha = file_sha256(path)
    identity = {'version': INSPECTION_VERSION, 'source_sha256': source_sha, 'seconds': seconds,
                'duration': duration, 'audio': info['audio'], 'width': info['width'], 'height': info['height']}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if cache_root.is_symlink():
        raise ModelTaskError('inspection_changed', '审片缓存路径无效')
    cache_root.mkdir(parents=True, exist_ok=True)
    folder = cache_root / key
    if folder.is_symlink():
        raise ModelTaskError('inspection_changed', '审片缓存路径无效')
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / 'manifest.json'
    if manifest.exists():
        try:
            if manifest.is_symlink():raise ValueError
            saved = json.loads(manifest.read_text())
            if saved['identity'] != identity:raise ValueError
            chunks = tuple(VideoChunk(float(c['start']), float(c['end']), local_path(folder,c['filename']),
                                      c['sha256'], c['audio_in_video']) for c in saved['chunks'])
            if not _video_chunks_complete(chunks, duration) or any(file_sha256(c.path) != c.sha256 or c.audio != info['audio'] for c in chunks):
                raise ValueError
            return chunks, saved['evidence']
        except (ValueError, KeyError, TypeError, OSError):
            raise ModelTaskError('inspection_changed', '审片缓存发生变化，不能重建后冒用已有模型回执') from None
    chunks = []
    start = 0.0
    while start < duration - 0.000001:
        length = min(seconds, duration - start)
        output = folder / f'{len(chunks):04d}.mp4'
        if output.is_symlink():
            raise ModelTaskError('inspection_changed', '审片缓存路径无效')
        while True:
            command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-xerror', '-ss', f'{start:.6f}',
                '-protocol_whitelist', 'file,pipe', '-format_whitelist', MEDIA_FORMATS, '-i', str(path),
                '-t', f'{length:.6f}', '-map', '0:v:0', '-map_metadata', '-1',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough']
            if info['audio']:
                command += ['-map', '0:a:0', '-c:a', 'aac', '-b:a', '192k']
            else:
                command += ['-an']
            command += ['-movflags', '+faststart', '-y', str(output)]
            try:
                result = subprocess.run(command, capture_output=True, timeout=180,
                                        env=process_environment(folder))
            except (subprocess.TimeoutExpired, OSError):
                raise ModelTaskError('media_inspection_failed', '实际视频分段未完成，原成片已保留') from None
            if result.returncode or not output.is_file():
                raise ModelTaskError('media_inspection_failed', '无法生成保留画面与音轨的实际审片片段')
            if (output.stat().st_size + 2)//3*4 < MAX_VIDEO_BASE64:
                break
            if length <= .25:
                raise ModelTaskError('inspection_too_large', '视频片段无法适配模型输入限制；未缩小分辨率或省略帧')
            length /= 2
        actual = probe_media(output)
        if (actual['audio'] != info['audio'] or not actual['video'] or
                (actual['width'], actual['height']) != (info['width'], info['height']) or
                abs(actual['duration'] - length) > .1):
            raise ModelTaskError('media_inspection_failed', '实际审片片段未保留完整画面、时长或声音')
        end = min(duration, start + length)
        chunks.append(VideoChunk(start, end, output, file_sha256(output), info['audio']))
        if end >= duration - .000001:break
        # Avoid duplicate-only chunks and retain real context across every join.
        start = end - min(1.0, length / 4)
    result = tuple(chunks)
    if not _video_chunks_complete(result, duration) or file_sha256(path) != source_sha:
        raise ModelTaskError('inspection_incomplete', '实际视频输入没有覆盖完整成片')
    evidence = {**identity, 'sampling': 'native_video_full_timeline', 'coverage_complete': True,
                'provider_frame_sampling': 'provider_internal_not_verified',
                'encoding': 'full_resolution_original_frame_rate_h264_crf18_aac192k',
                'chunks': [chunk.evidence() for chunk in result]}
    atomic_json(manifest, {'identity': identity, 'chunks': evidence['chunks'], 'evidence': evidence})
    return result, evidence
