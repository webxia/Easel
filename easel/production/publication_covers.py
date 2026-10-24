"""Local cover candidates for an existing publication, without production jobs."""
from __future__ import annotations

import base64
import io
import re
import tempfile
import subprocess
import warnings
from pathlib import Path

from PIL import Image, ImageOps

from .media import file_sha256, local_path
from .service import fail

MAX_IMAGE_BYTES = 20 * 1024 * 1024


def cover_path(publications, draft, cover):
    if not isinstance(cover, dict) or set(cover) != {'digest', 'width', 'height'}:
        fail('invalid_cover', '封面引用无效，请重新选择')
    checksum = cover['digest']
    if not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum):
        fail('invalid_cover', '封面引用无效，请重新选择')
    locator = f"_production/publication-covers/{draft['id']}/{checksum}.jpg"
    try:
        path = local_path(publications.service.outputs, locator)
        if file_sha256(path) != checksum:
            raise ValueError('cover changed')
        with Image.open(path) as image:
            if image.size != (cover['width'], cover['height']):
                raise ValueError('cover dimensions changed')
        return path
    except (ValueError, OSError):
        fail('cover_changed', '封面文件缺失或变化，请重新选择并保存', 409)


def prepare_cover(publications, identity, revision, *, data=None, library_path=None, at=None):
    draft = publications.get(identity)
    if draft['state'] != 'draft' or draft['revision'] != revision:
        fail('stale_publication', '草稿已变化或已提交，不能修改封面', 409)
    with publications.store.connection() as conn:
        _, _, _, video = publications._source(conn, draft['work_id'], draft['output_id'], draft['acceptance_id'])
    if sum(x is not None for x in (data, library_path, at)) != 1:
        fail('invalid_cover', '请选择图片或一个成片时点')
    if library_path is not None:
        # Same public outputs tree as the existing media picker; never credentials,
        # inboxes or production internals via an arbitrary filesystem path.
        first = library_path.split('/')[0]
        if first.startswith(('_', '.')) or first in {'works', 'analytics', 'wechat'}:
            fail('invalid_cover', '请从图片素材列表选择图片')
        try:
            source = local_path(publications.service.outputs, library_path)
            if source.stat().st_size > MAX_IMAGE_BYTES:
                fail('cover_too_large', '封面图片不能超过20MB')
            data = source.read_bytes()
        except (ValueError, OSError):
            fail('invalid_cover', '图片不可用，请重新选择')
    if at is not None:
        from .inspection import observe_media
        from .tools import ToolInputError
        from .model_tasks import ModelTaskError
        try:
            blocks, _, evidence = observe_media(video, max_frames=1, frame_times=(at,))
            block = next(b for b in blocks if b.get('type') == 'image_url')
            data = base64.b64decode(block['image_url']['url'].split(',', 1)[1])
        except (ToolInputError, ModelTaskError, ValueError, StopIteration, OSError, subprocess.TimeoutExpired):
            fail('cover_frame_unavailable', '无法截取该时点，请选择成片内的其他时间')
    if not data or len(data) > MAX_IMAGE_BYTES:
        fail('invalid_cover', '请选择20MB以内的有效图片')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as original:
                if original.format not in {'PNG', 'JPEG', 'WEBP'}:
                    raise ValueError('unsupported image')
                image = ImageOps.exif_transpose(original).convert('RGB')
                image.thumbnail((1920, 1080), Image.Resampling.LANCZOS)
        encoded = io.BytesIO()
        image.save(encoded, format='JPEG', quality=85, optimize=True)
    except (ValueError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        fail('invalid_cover', '请选择有效的 JPG、PNG 或 WebP 图片')
    # Preparation is not selection: save() subsequently binds these exact bytes
    # into the draft revision and its existing final-confirmation hash.
    folder = publications.service.outputs
    for part in ('_production', 'publication-covers', identity):
        folder = folder / part
        if folder.is_symlink():
            fail('invalid_cover_storage', '封面存储目录不可用')
        folder.mkdir(exist_ok=True)
    from hashlib import sha256
    checksum = sha256(encoded.getvalue()).hexdigest()
    target = folder / (checksum + '.jpg')
    if target.is_symlink():
        fail('invalid_cover_storage', '封面存储目录不可用')
    if not target.exists():
        with tempfile.NamedTemporaryFile(dir=folder, suffix='.tmp', delete=False) as tmp:
            tmp.write(encoded.getvalue())
        Path(tmp.name).replace(target)
    cover = {'digest': checksum, 'width': image.width, 'height': image.height}
    cover_path(publications, draft, cover)
    current = publications.get(identity)
    if current['state'] != 'draft' or current['revision'] != revision:
        fail('stale_publication', '准备封面期间草稿已变化，请刷新', 409)
    return cover
