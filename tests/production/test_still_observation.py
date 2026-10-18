"""Real still decoding must yield a frame, not a successful empty seek."""
import base64
from io import BytesIO
import shutil

from PIL import Image
import pytest

from easel.production.inspection import observe_media


@pytest.mark.skipif(not shutil.which('ffmpeg') or not shutil.which('ffprobe'),
                    reason='local media tools unavailable')
@pytest.mark.parametrize('extension', ['jpg', 'png', 'webp'])
def test_still_image_is_observed_at_start(tmp_path, extension):
    path = tmp_path / ('still.' + extension)
    Image.new('RGB', (96, 64), (240, 10, 10)).save(path)
    blocks, required, evidence = observe_media(path, max_frames=4)
    frames = [b for b in blocks if b['type'] == 'image_url']
    assert frames
    payload = base64.b64decode(frames[0]['image_url']['url'].split(',', 1)[1])
    decoded = Image.open(BytesIO(payload)).convert('RGB')
    red, green, blue = decoded.getpixel((0, 0))
    assert red > 200 and green < 40 and blue < 40
    assert evidence['frame_times'] and all(at == 0 for at in evidence['frame_times'])
    assert not evidence['audio_observed']
    assert 'image' in required
