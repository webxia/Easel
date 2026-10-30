"""Pure local FFmpeg timeline adapter. No provider, shell, or generation interface."""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from .base import (AssetManifest, CheckResult, EditError, EditProject, MediaAsset,
                   RenderJob, RenderOutput)
from ..media import MEDIA_FORMATS, atomic_json, caption_image, file_sha256, local_path, probe_media, process_environment

ENCODING = {"version":"1080p-h264-2","codec":"libx264","preset":"medium","crf":18,"pixel_format":"yuv420p"}

FEATURES = ("video", "image", "trim", "crop", "frame", "contain", "cover", "pan_zoom", "dissolve",
            "fade", "source_audio", "multi_audio", "captions", "caption_background")
SUFFIXES = {"video": {".mp4", ".mov", ".m4v", ".webm", ".mkv"},
            "audio": {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"},
            "image": {".png", ".jpg", ".jpeg", ".webp"}, "font": {".ttf", ".otf", ".ttc"}}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: dict) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                      ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@contextmanager
def _lock(path: Path, *, blocking: bool = True):
    """OS released locks avoid PID-reuse guesses when a renderer crashes."""
    if path.is_symlink():
        raise EditError("render lock cannot be a symlink")
    stream = path.open("a+b")
    acquired = False
    try:
        if os.name == "nt":
            import msvcrt
            stream.seek(0)
            if not stream.read(1):
                stream.write(b"0"); stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == "nt":
                import msvcrt
                stream.seek(0); msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)
        stream.close()


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
        raise EditError("render record unavailable")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise EditError("render record invalid") from exc
    if not isinstance(value, dict):
        raise EditError("render record invalid")
    return value


class FFmpegEditor:
    def __init__(self, job_root: Path, *, ffmpeg: str | None = None, ffprobe: str | None = None):
        self.root = Path(job_root)
        if self.root.is_symlink():
            raise EditError("render root cannot be a symlink")
        self.root.mkdir(parents=True, exist_ok=True)
        self.root = self.root.resolve()
        self.ffmpeg = shutil.which(ffmpeg or "ffmpeg")
        self.ffprobe = shutil.which(ffprobe or "ffprobe")
        self._version = ""
        self._missing: tuple[str, ...] = ()

    def capabilities(self) -> dict:
        if not self.ffmpeg or not self.ffprobe:
            return {"available": False, "editor": "ffmpeg-timeline-v1", "reason": "ffmpeg_or_ffprobe_missing"}
        if not self._version:
            with tempfile.TemporaryDirectory(prefix="easel-engine-") as td:
                result = subprocess.run([self.ffmpeg, "-version"], capture_output=True, timeout=10,
                                        env=process_environment(Path(td)))
                filters = subprocess.run([self.ffmpeg, "-hide_banner", "-filters"], capture_output=True, timeout=10,
                                         env=process_environment(Path(td))).stdout.decode(errors="replace")
                encoders = subprocess.run([self.ffmpeg, "-hide_banner", "-encoders"], capture_output=True, timeout=10,
                                          env=process_environment(Path(td))).stdout.decode(errors="replace")
            lines = result.stdout.decode("utf-8", errors="replace").splitlines()
            self._version = lines[0] if result.returncode == 0 and lines else ""
            self._missing = tuple(name for name in ("overlay", "xfade", "amix", "zoompan", "scale", "crop")
                                  if not re.search(r"\s" + name + r"\s", filters))
            self._missing += tuple(name for name in ("libx264", "aac") if not re.search(r"\s" + name + r"\s", encoders))
        return {"available": bool(self._version) and not self._missing, "editor": "ffmpeg-timeline-v1", "version": self._version,
                "missing_components": list(self._missing),
                "features": list(FEATURES), "duration_seconds": [1, 900],
                "sizes": [[1080, 1920], [1920, 1080]], "audio_modes": ["silent", "music", "voice", "mixed"],
                "max_scenes": 128, "generates_media": False,
                "unsupported": ["arbitrary_code", "external_uri", "3d", "custom_shader"]}

    def _job(self, job_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", job_id):
            raise EditError("invalid render job identity")
        path = self.root / job_id
        if path.is_symlink():
            raise EditError("render job cannot be a symlink")
        return path

    @staticmethod
    def _assets(project: EditProject) -> set[str]:
        return {s.asset_id for s in project.scenes} | {a.asset_id for a in project.audio} | {
            c.font_asset_id for c in project.captions}

    def check(self, project: EditProject, manifest: AssetManifest) -> CheckResult:
        try:
            # Revalidate model_copy updates too; frozen models are not recursively immutable.
            project = EditProject.model_validate(project.model_dump())
            manifest = AssetManifest.model_validate(manifest.model_dump())
            caps = self.capabilities()
            if not caps["available"]:
                raise EditError("FFmpeg/ffprobe unavailable", "capability_unavailable")
            if len(project.scenes) > 128 or set(project.required_features) - set(FEATURES):
                raise EditError("requested editing capability is unavailable", "capability_unavailable")
            observed = {}
            for identity in self._assets(project):
                asset = manifest.assets.get(identity)
                if asset is None:
                    raise EditError("referenced media handle is unavailable")
                path = local_path(manifest.root, asset.locator)
                if path.suffix.lower() not in SUFFIXES[asset.kind]:
                    raise EditError("media file type is not supported")
                if file_sha256(path) != asset.sha256:
                    raise EditError("media identity does not match its bytes")
                if asset.kind != "font":
                    observed[identity] = probe_media(path, ffprobe=self.ffprobe)
            for scene in project.scenes:
                asset, info = manifest.assets[scene.asset_id], observed.get(scene.asset_id, {})
                if asset.kind not in {"video", "image"} or not info.get("video"):
                    raise EditError("scene requires an actual image or video")
                if asset.kind == "video" and scene.source_start + scene.duration > info["duration"] + 0.5 / project.fps:
                    raise EditError("scene extends beyond source; looping or freezing is not implicit")
                if asset.kind == "image" and (scene.source_start or scene.source_audio):
                    raise EditError("still images have no source time or audio")
                if scene.source_audio and not info["audio"]:
                    raise EditError("required source audio is absent")
            for audio in project.audio:
                info = observed.get(audio.asset_id, {})
                if not info.get("audio"):
                    raise EditError("audio handle has no actual audio stream")
                if audio.source_start >= info["duration"] or (
                        not audio.loop and audio.source_start + audio.duration > info["duration"] + 0.02):
                    raise EditError("audio extends beyond the actual source")
            for caption in project.captions:
                if manifest.assets[caption.font_asset_id].kind != "font":
                    raise EditError("caption font handle is not a font")
            return CheckResult(valid=True, engine_version=self._version)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            # Do not return provider env, absolute private paths or raw process stderr.
            reason = str(exc) if isinstance(exc, EditError) else "invalid or unreadable local editing input"
            return CheckResult(valid=False, code=exc.code if isinstance(exc, EditError) else "invalid_edit_project",
                               diagnostics=(reason,), engine_version=self._version)

    def build(self, project: EditProject, manifest: AssetManifest, *, job_id: str) -> RenderJob:
        project = EditProject.model_validate(project.model_dump())
        manifest = AssetManifest.model_validate(manifest.model_dump())
        fingerprint = _hash({"mix_policy": "narration-music-1", "encoding": ENCODING, "project": project.model_dump(mode="json"), "assets": {
            k: manifest.assets[k].model_dump() for k in sorted(self._assets(project)) if k in manifest.assets}})
        path = self._job(job_id)
        path.mkdir(exist_ok=True)
        with _lock(path / "registration.lock"):
            if (path / "job.json").exists():
                current = self.observe(job_id)
                if current.project_hash != fingerprint:
                    raise EditError("render identity already binds different inputs", "stale_revision")
                if current.status != "interrupted":
                    return current
                # Pure local re-render; no new model/media generation is possible here.
                if (path / "cancel.request").exists():
                    return self.cancel(job_id)
            result = self.check(project, manifest)
            if not result.valid:
                raise EditError("; ".join(result.diagnostics), result.code or "invalid_edit_project")
            staged = {}
            if (path / "assets").is_symlink():
                raise EditError("staged media directory cannot be a symlink")
            (path / "assets").mkdir(exist_ok=True)
            for identity in sorted(self._assets(project)):
                asset = manifest.assets[identity]
                source = local_path(manifest.root, asset.locator)
                locator = "assets/" + asset.sha256 + source.suffix.lower()
                destination = path / locator
                if destination.is_symlink():
                    raise EditError("staged media cannot be a symlink")
                if not destination.exists():
                    temporary = destination.with_suffix(destination.suffix + ".partial")
                    shutil.copyfile(source, temporary)
                    if file_sha256(temporary) != asset.sha256:
                        temporary.unlink(missing_ok=True)
                        raise EditError("source changed while staging media")
                    os.replace(temporary, destination)
                elif file_sha256(destination) != asset.sha256:
                    raise EditError("staged media identity changed")
                staged[identity] = MediaAsset(locator=locator, sha256=asset.sha256, kind=asset.kind).model_dump()
            atomic_json(path / "project.json", project.model_dump(mode="json"))
            atomic_json(path / "manifest.json", {"assets": staged})
            atomic_json(path / "engine.json", {"ffmpeg": self.ffmpeg, "ffprobe": self.ffprobe, "version": self._version,"encoding": ENCODING})
            job = RenderJob(job_id=job_id, project_hash=fingerprint, status="queued", updated_at=_now(),
                            total_steps=len(project.scenes) + 3)
            atomic_json(path / "job.json", job.model_dump())
            env = process_environment(path / "process-home")
            env["PYTHONPATH"] = str(Path(__file__).resolve().parents[3])
            with (path / "worker.log").open("ab") as log:
                try:
                    subprocess.Popen([sys.executable, "-m", "easel.production.editors.render_worker", str(path)],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, env=env,
                                     start_new_session=os.name != "nt", close_fds=True)
                except OSError as exc:
                    atomic_json(path / "job.json", {**job.model_dump(), "status": "failed", "error": "renderer_start_failed"})
                    raise EditError("renderer could not start") from exc
            return job

    def observe(self, job_id: str) -> RenderJob:
        path = self._job(job_id)
        job = RenderJob.model_validate(_read(path / "job.json"))
        if job.status == "running":
            try:
                with _lock(path / "execution.lock", blocking=False):
                    # Re-read under lock; a completed renderer may have just exited.
                    job = RenderJob.model_validate(_read(path / "job.json"))
                    if job.status == "running":
                        job = job.model_copy(update={"status": "interrupted", "updated_at": _now(),
                                                     "error": "renderer_interrupted"})
                        atomic_json(path / "job.json", job.model_dump())
            except (BlockingIOError, PermissionError):
                pass
        elif job.status == "queued" and (datetime.now(timezone.utc) - datetime.fromisoformat(job.updated_at)).total_seconds() > 30:
            try:
                with _lock(path / "execution.lock", blocking=False):
                    current = RenderJob.model_validate(_read(path / "job.json"))
                    if current.status == "queued":
                        job = current.model_copy(update={"status": "interrupted", "error": "renderer_did_not_start", "updated_at": _now()})
                        atomic_json(path / "job.json", job.model_dump())
            except (BlockingIOError, PermissionError):
                pass
        return job

    def cancel(self, job_id: str) -> RenderJob:
        path = self._job(job_id)
        with _lock(path / "terminal.lock"):
            job = self.observe(job_id)
            if job.status in {"completed", "failed", "cancelled"}:
                return job
            (path / "cancel.request").touch()
            if job.status == "interrupted":
                job = job.model_copy(update={"status": "cancelled", "updated_at": _now()})
                atomic_json(path / "job.json", job.model_dump())
        # Running cancellation is a request, not a fabricated completed cancel.
        return job

    def collect(self, job_id: str) -> RenderOutput:
        if self.observe(job_id).status != "completed":
            raise EditError("render output is not complete")
        path = self._job(job_id)
        output = RenderOutput.model_validate(_read(path / "output.json"))
        video = local_path(path, "final.mp4")
        if output.video_path != video or file_sha256(video) != output.sha256:
            raise EditError("render output identity changed")
        return output

    def caption_base(self, job_id: str, *, work_id: str) -> tuple[Path, str]:
        """Verified same-composition video before burned captions, for previews."""
        output = self.collect(job_id)
        folder = self._job(job_id)
        project = EditProject.model_validate(_read(folder / "project.json"))
        if project.work_id != work_id or output.caption_base_path is None or output.caption_base_sha256 is None:
            raise EditError("caption-free frame for this version is unavailable")
        try:
            relative = output.caption_base_path.relative_to(folder).as_posix()
        except ValueError:
            raise EditError("caption preview base is outside its render job") from None
        path = local_path(folder, relative)
        if file_sha256(path) != output.caption_base_sha256:
            raise EditError("caption preview base identity changed")
        return path, output.caption_base_sha256


class RenderCancelled(Exception):
    pass


class LocalRender:
    """Runs inside a separate managed process; all inputs have been staged and hashed."""
    def __init__(self, path: Path):
        self.path = path
        self.project = EditProject.model_validate(_read(path / "project.json"))
        self.manifest = AssetManifest(root=path, **_read(path / "manifest.json"))
        self.engine = _read(path / "engine.json")
        if self.engine.get("encoding")!=ENCODING:raise EditError("render encoding specification changed; create a new render job")
        self.job = RenderJob.model_validate(_read(path / "job.json"))
        self.env = process_environment(path / "process-home")
        # A crashed Python worker may leave an encoding subprocess alive. Its
        # unique temporary output cannot clobber a resumed worker's files.
        self.attempt_token = uuid.uuid4().hex
        self.cache = path.parent / "cache"
        self.cache.mkdir(exist_ok=True)

    def update(self, **changes):
        self.job = self.job.model_copy(update={**changes, "updated_at": _now()})
        atomic_json(self.path / "job.json", self.job.model_dump())

    def source(self, identity: str) -> Path:
        asset = self.manifest.assets[identity]
        path = local_path(self.path, asset.locator)
        if file_sha256(path) != asset.sha256:
            raise EditError("staged source changed")
        return path

    def run(self, args: list[str]):
        if (self.path / "cancel.request").exists():
            raise RenderCancelled()
        command = [self.engine["ffmpeg"], "-hide_banner", "-loglevel", "error", "-nostdin", "-y", *args]
        with (self.path / "ffmpeg.log").open("ab") as log:
            process = subprocess.Popen(command, cwd=self.path, env=self.env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.DEVNULL, stderr=log)
            try:
                heartbeat = time.monotonic()
                while process.poll() is None:
                    if (self.path / "cancel.request").exists():
                        raise RenderCancelled()
                    if time.monotonic() - heartbeat > 2:
                        self.update()
                        heartbeat = time.monotonic()
                    time.sleep(0.05)
                if process.returncode:
                    raise EditError("local renderer failed; inspect the private diagnostic log")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill(); process.wait(timeout=5)

    @staticmethod
    def input(path: Path) -> list[str]:
        return ["-protocol_whitelist", "file,pipe", "-format_whitelist", MEDIA_FORMATS, "-i", str(path)]

    def encode(self) -> list[str]:
        encoding=self.engine["encoding"]
        return ["-c:v", encoding["codec"], "-preset", encoding["preset"], "-crf", str(encoding["crf"]), "-threads", "2",
                "-pix_fmt", "yuv420p", "-movflags", "+faststart"]

    def scene(self, index: int) -> Path:
        p = self.project
        scene = p.scenes[index]
        asset = self.manifest.assets[scene.asset_id]
        key = _hash({"scene": scene.model_dump(), "sha": asset.sha256,
                     "size": [p.width, p.height], "fps": p.fps, "engine": self.engine["version"],
                     "color_range": "limited-1", "encoding": self.engine["encoding"]})
        target = self.path / "scenes" / f"{index:04d}.mp4"
        target.parent.mkdir(exist_ok=True)
        receipt = target.with_suffix(".json")
        if target.is_file() and receipt.is_file():
            old = _read(receipt)
            if old.get("key") == key and old.get("sha256") == file_sha256(target):
                return target
        source = self.source(scene.asset_id)
        info = probe_media(source, ffprobe=self.engine["ffprobe"], home=self.path / "process-home")
        crop = scene.crop
        sw, sh = int(info["width"]), int(info["height"])
        cw, ch = max(2, int(sw * crop.width) // 2 * 2), max(2, int(sh * crop.height) // 2 * 2)
        cx, cy = min(sw - cw, int(sw * crop.x)), min(sh - ch, int(sh * crop.y))
        vf = [f"crop={cw}:{ch}:{cx}:{cy}"]
        frame = scene.frame
        fw, fh = max(2, int(p.width * frame.width) // 2 * 2), max(2, int(p.height * frame.height) // 2 * 2)
        fx, fy = min(p.width - fw, int(p.width * frame.x) // 2 * 2), min(p.height - fh, int(p.height * frame.y) // 2 * 2)
        if scene.fit == "cover":
            vf += [f"scale={fw}:{fh}:force_original_aspect_ratio=increase:out_range=tv", f"crop={fw}:{fh}"]
        else:
            vf += [f"scale={fw}:{fh}:force_original_aspect_ratio=decrease:out_range=tv",
                   f"pad={fw}:{fh}:(ow-iw)/2:(oh-ih)/2:color=black"]
        vf += ["setsar=1", f"fps={p.fps}", "setpts=PTS-STARTPTS"]
        frames = round(scene.duration * p.fps)
        if scene.motion != "none":
            z = f"1+0.08*on/{max(1, frames - 1)}" if scene.motion == "push_in" else f"1.08-0.08*on/{max(1, frames - 1)}"
            vf += [f"zoompan=z='{z}':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=1:s={fw}x{fh}:fps={p.fps}"]
        if (fw, fh, fx, fy) != (p.width, p.height, 0, 0):
            vf += [f"pad={p.width}:{p.height}:{fx}:{fy}:color=black"]
        if scene.fade_in:
            vf += [f"fade=t=in:st=0:d={scene.fade_in}"]
        if scene.fade_out:
            vf += [f"fade=t=out:st={scene.duration-scene.fade_out}:d={scene.fade_out}"]
        # Stream-copy montage must not switch yuv420p/yuvj420p at a cut:
        # subtitle overlay keeps its graph alive to preserve sparse frames.
        vf += ["setparams=range=limited"]
        args = []
        if asset.kind == "image":
            args += ["-loop", "1", "-framerate", str(p.fps)]
        else:
            args += ["-ss", str(scene.source_start)]
        temporary = target.with_suffix(f".{self.attempt_token}.partial.mp4")
        self.run([*args, *self.input(source), "-an", "-vf", ",".join(vf), "-frames:v", str(frames),
                  *self.encode(), str(temporary)])
        os.replace(temporary, target)
        atomic_json(receipt, {"key": key, "sha256": file_sha256(target)})
        return target

    def montage(self, scenes: list[Path]) -> Path:
        p = self.project
        target = self.path / ("montage-" + self.attempt_token + ".mp4")
        if len(scenes) == 1:
            shutil.copyfile(scenes[0], target)
            return target
        if not any(s.transition_seconds for s in p.scenes):
            listing = self.path / "scenes.ffconcat"
            listing.write_text("ffconcat version 1.0\n" + "".join(
                f"file 'scenes/{i:04d}.mp4'\n" for i in range(len(scenes))), encoding="utf-8")
            self.run(["-protocol_whitelist", "file,pipe", "-safe", "1", "-f", "concat", "-i", str(listing),
                      "-an", "-c:v", "copy", "-movflags", "+faststart", str(target)])
            return target
        args, filters = [], []
        for index, path in enumerate(scenes):
            args += self.input(path)
            filters.append(f"[{index}:v]settb=AVTB,setpts=PTS-STARTPTS[v{index}]")
        prior, duration = "v0", p.scenes[0].duration
        for index, scene in enumerate(p.scenes[1:], 1):
            out = f"joined{index}"
            if scene.transition_seconds:
                filters.append(f"[{prior}][v{index}]xfade=transition=fade:duration={scene.transition_seconds}:offset={duration-scene.transition_seconds}[{out}]")
            else:
                filters.append(f"[{prior}][v{index}]concat=n=2:v=1:a=0[{out}]")
            duration += scene.duration - scene.transition_seconds
            prior = out
        graph = self.path / "montage.filter"
        graph.write_text(";".join(filters), encoding="utf-8")
        self.run([*args, "-filter_complex_threads", "1", "-filter_complex_script", str(graph),
                  "-map", f"[{prior}]", "-an", "-frames:v", str(round(p.duration * p.fps)),
                  *self.encode(), str(target)])
        return target

    def _mean_level(self, clip):
        """Measure the actual trimmed source, not its container or model label."""
        args = [self.engine['ffmpeg'], '-hide_banner', '-nostdin', '-loglevel', 'info',
                *self.input(self.source(clip['asset_id'])), '-map', '0:a:0',
                '-af', f"atrim=start={clip['source_start']}:duration={clip['duration']},volumedetect",
                '-f', 'null', '-']
        try:
            result = subprocess.run(args, cwd=self.path, env=self.env, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            raise EditError('audio balance source measurement timed out') from None
        match = re.search(rb'mean_volume:\s*(-?(?:[0-9.]+|inf)) dB', result.stderr)
        if result.returncode or not match:
            raise EditError('audio balance source measurement failed')
        return float(match.group(1))

    def _music_levels(self, clips):
        # Attenuation only: explicit silence, SFX, source sound and voice gains
        # remain intact. Music outside narration keeps its requested level.
        voices = [c for c in clips if c.get('role') == 'voice' and c['gain'] > 0]
        music = [c for c in clips if c.get('role') == 'music' and c['gain'] > 0]
        levels, evidence = {}, []
        if not voices or not music:
            return levels
        measured = {}
        def level(c):
            key = (c['asset_id'], c['source_start'], c['duration'])
            if key not in measured:
                measured[key] = self._mean_level(c)
            return measured[key] + 20*math.log10(c['gain'])
        for m in music:
            spans = []
            for v in voices:
                start, end = max(m['at'], v['at']), min(m['at']+m['duration'], v['at']+v['duration'])
                if end <= start:
                    continue
                voice_db, music_db = level(v), level(m)
                if not math.isfinite(voice_db) or not math.isfinite(music_db):
                    continue
                gain = m['gain'] * min(1.0, 10**((voice_db-music_db-12)/20))
                spans.append((start-m['at'], end-m['at'], gain))
                evidence.append({'music_clip':m['clip_id'], 'voice_clip':v['clip_id'],
                    'start':start, 'end':end, 'voice_mean_db':voice_db, 'music_mean_db':music_db,
                    'requested_gain':m['gain'], 'narration_gain':gain})
            if spans:
                merged = []
                for start, end, gain in sorted(spans):
                    if merged and start <= merged[-1][1] + .5:
                        a, b, g = merged[-1]
                        merged[-1] = (a, max(b, end), min(g, gain))
                    else:
                        merged.append((start, end, gain))
                levels[m['clip_id']] = merged
        atomic_json(self.path/'audio-balance.json', {'version':'narration-music-1',
                    'method':'trimmed_source_mean_level', 'margin_db':12, 'spans':evidence,
                    'listening_verified':False})
        return levels

    def audio(self) -> Path | None:
        p = self.project
        if p.audio_mode == "silent":
            return None
        clips = [a.model_dump() for a in p.audio]
        for scene, at in zip(p.scenes, p.scene_starts()):
            if scene.source_audio:
                clips.append({"asset_id": scene.asset_id, "source_start": scene.source_start,
                              "at": at, "duration": scene.duration, "gain": scene.source_gain,
                              "fade_in": 0, "fade_out": 0, "loop": False})
        key = _hash({"clips": clips, "assets": {c["asset_id"]: self.manifest.assets[c["asset_id"]].sha256 for c in clips},
                     "duration": p.duration, "engine": self.engine["version"], "mix_policy": "narration-music-1"})
        destination = self.cache / ("audio-" + key + ".m4a")
        with _lock(self.cache / (key + ".lock")):
            receipt = destination.with_suffix(".json")
            if destination.is_file() and receipt.is_file() and _read(receipt).get("sha256") == file_sha256(destination):
                cached_balance = _read(receipt).get('balance')
                if cached_balance:
                    atomic_json(self.path/'audio-balance.json', cached_balance)
                return destination
            music_levels = self._music_levels(clips)
            args, filters = [], []
            for index, clip in enumerate(clips):
                if clip["loop"]:
                    args += ["-stream_loop", "-1"]
                args += self.input(self.source(clip["asset_id"]))
                gain = str(clip['gain'])
                for start, end, value in music_levels.get(clip.get('clip_id'), []):
                    weight = f"min(1,min(max(0,(t-{start}+.1)/.1),max(0,({end}+.25-t)/.25)))"
                    gain = f"min({gain},{clip['gain']}+({value}-{clip['gain']})*{weight})"
                af = [f"atrim=start={clip['source_start']}:duration={clip['duration']}", "asetpts=PTS-STARTPTS",
                      "aresample=48000", "aformat=sample_fmts=fltp:channel_layouts=stereo", f"volume='{gain}':eval=frame"]
                if clip["fade_in"]:
                    af.append(f"afade=t=in:st=0:d={clip['fade_in']}")
                if clip["fade_out"]:
                    af.append(f"afade=t=out:st={clip['duration']-clip['fade_out']}:d={clip['fade_out']}")
                af += [f"adelay={round(clip['at'] * 48000)}S:all=1", f"apad=whole_dur={p.duration}"]
                filters.append(f"[{index}:a]" + ",".join(af) + f"[a{index}]")
            filters.append("".join(f"[a{i}]" for i in range(len(clips))) +
                           f"amix=inputs={len(clips)}:duration=longest:normalize=0,atrim=duration={p.duration}[mix]")
            graph = self.path / "audio.filter"
            graph.write_text(";".join(filters), encoding="utf-8")
            temporary = destination.with_suffix(f".{self.attempt_token}.partial.m4a")
            self.run([*args, "-filter_complex_script", str(graph), "-map", "[mix]", "-vn", "-c:a", "aac",
                      "-b:a", "192k", "-threads", "2", "-t", str(p.duration), str(temporary)])
            os.replace(temporary, destination)
            balance_path = self.path/'audio-balance.json'
            atomic_json(receipt, {"sha256": file_sha256(destination),
                                  **({'balance':_read(balance_path)} if balance_path.is_file() else {})})
        return destination

    def captions(self) -> Path | None:
        p = self.project
        if not p.captions:
            return None
        root = self.path / "captions"
        root.mkdir(exist_ok=True)
        layers = {}
        boundaries = {0, round(p.duration * p.fps)}
        for index, caption in enumerate(p.captions):
            image = caption_image(caption, self.source(caption.font_asset_id), width=p.width, height=p.height,
                                  destination=root / f"text-{index}.png")
            layers[index] = image
            boundaries.update({round(caption.start * p.fps), round(caption.end * p.fps)})
        ticks = sorted(boundaries)
        lines = ["ffconcat version 1.0"]
        for index, (start, end) in enumerate(zip(ticks, ticks[1:])):
            canvas = Image.new("RGBA", (p.width, p.height))
            for ci, caption in enumerate(p.captions):
                if round(caption.start * p.fps) <= start < round(caption.end * p.fps):
                    with Image.open(layers[ci]) as layer:
                        canvas.alpha_composite(layer)
            name = f"captions/frame-{index}.png"
            canvas.save(self.path / name)
            lines += [f"file '{name}'", f"option framerate {p.fps}", f"duration {(end-start)/p.fps:.9f}"]
        lines += [f"file '{name}'", f"option framerate {p.fps}"]
        listing = self.path / "captions.ffconcat"
        listing.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return listing

    def finish(self, video: Path, audio: Path | None, captions: Path | None) -> Path:
        p = self.project
        target = self.path / ("final-" + self.attempt_token + ".partial.mp4")
        # The montage has fixed geometry/pixel format, but stock clips can carry
        # different color tags across cuts. Reinitializing the overlay graph at
        # those metadata changes discards buffered sparse caption frames.
        video_input = ["-reinit_filter", "0", *self.input(video)] if captions else self.input(video)
        args = video_input.copy()
        audio_index = 1
        if captions:
            args += ["-protocol_whitelist", "file,pipe", "-safe", "0", "-f", "concat", "-i", str(captions)]
            args += ["-filter_complex_threads", "1", "-filter_complex", "[0:v][1:v]overlay=0:0:eof_action=pass[v]",
                     "-map", "[v]"]
            audio_index = 2
        else:
            args += ["-map", "0:v"]
        if audio:
            # All -i must precede output options; assemble again for strict FFmpeg parsing.
            input_args = video_input.copy()
            if captions:
                input_args += ["-protocol_whitelist", "file,pipe", "-safe", "0", "-f", "concat", "-i", str(captions)]
            input_args += self.input(audio)
            options = (["-filter_complex_threads", "1", "-filter_complex", "[0:v][1:v]overlay=0:0:eof_action=pass[v]", "-map", "[v]"]
                       if captions else ["-map", "0:v"])
            args = input_args + options + ["-map", f"{audio_index}:a", "-c:a", "copy"]
        else:
            args += ["-an"]
        args += self.encode() if captions else ["-c:v", "copy", "-movflags", "+faststart"]
        self.run([*args, "-t", str(p.duration), str(target)])
        final = self.path / "final.mp4"
        os.replace(target, final)
        return final

    def execute(self):
        with _lock(self.path / "execution.lock"):
            current = RenderJob.model_validate(_read(self.path / "job.json"))
            if current.status not in {"queued", "interrupted"}:
                return
            self.job = current
            self.update(status="running", stage="checking_inputs")
            try:
                if (self.path / "cancel.request").exists():
                    raise RenderCancelled()
                scenes = []
                for index in range(len(self.project.scenes)):
                    self.update(stage=f"scene:{self.project.scenes[index].scene_id}", completed_steps=index)
                    scenes.append(self.scene(index))
                self.update(stage="montage", completed_steps=len(scenes))
                video = self.montage(scenes)
                self.update(stage="audio", completed_steps=len(scenes) + 1)
                audio = self.audio()
                self.update(stage="captions_and_export", completed_steps=len(scenes) + 2)
                final = self.finish(video, audio, self.captions())
                info = probe_media(final, ffprobe=self.engine["ffprobe"], home=self.path / "process-home")
                if (not info["video"] or (info["width"], info["height"]) != (self.project.width, self.project.height)
                        or abs(info["duration"] - self.project.duration) > max(0.1, 2 / self.project.fps)
                        or info["audio"] != (self.project.audio_mode != "silent")):
                    raise EditError("rendered media does not match the confirmed specifications")
                output = RenderOutput(job_id=self.job.job_id, project_hash=self.job.project_hash,
                    project_path=self.path / "project.json", video_path=final, sha256=file_sha256(final),
                    duration=info["duration"], width=info["width"], height=info["height"],
                    audio_present=info["audio"], engine_version=self.engine["version"], encoding=self.engine["encoding"],
                    caption_base_path=video, caption_base_sha256=file_sha256(video))
                with _lock(self.path / "terminal.lock"):
                    if (self.path / "cancel.request").exists():
                        raise RenderCancelled()
                    atomic_json(self.path / "output.json", output.model_dump(mode="json"))
                    self.update(status="completed", stage="completed", completed_steps=self.job.total_steps, error=None)
            except RenderCancelled:
                self.update(status="cancelled", stage="cancelled", error=None)
            except Exception as exc:
                self.update(status="failed", error=str(exc) if isinstance(exc, EditError) else "local_render_failed")
