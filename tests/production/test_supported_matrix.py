"""Duration bounds are software checks; named renders are actual local media evidence."""
import shutil
import time
from pathlib import Path
import pytest
from PIL import Image
from easel.production.contracts import VideoSettings
from easel.production.editors import AssetManifest,MediaAsset,EditProject,Scene,FFmpegEditor
from easel.production.media import file_sha256


@pytest.mark.parametrize('duration',[1,90,900])
@pytest.mark.parametrize('aspect',['9:16','16:9'])
@pytest.mark.parametrize('mode',['silent','music','voice','mixed'])
def test_declared_settings_matrix(duration,aspect,mode):
    value=VideoSettings(duration_seconds=duration,aspect_ratio=aspect,audio_mode=mode)
    assert value.duration_seconds==duration


@pytest.mark.skipif(not shutil.which('ffmpeg'),reason='real local FFmpeg unavailable')
def test_actual_ninety_second_horizontal_silent_render(tmp_path):
    source=tmp_path/'source.png';Image.new('RGB',(320,180),'#334455').save(source)
    manifest=AssetManifest(root=tmp_path,assets={'image':MediaAsset(locator=source.name,sha256=file_sha256(source),kind='image')})
    project=EditProject(work_id='fixture',plan_revision=1,revision=1,width=1920,height=1080,fps=24,duration=90,
        scenes=(Scene(scene_id='s',asset_id='image',duration=90),))
    editor=FFmpegEditor(tmp_path/'jobs');editor.build(project,manifest,job_id='ninety')
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        job=editor.observe('ninety')
        if job.status in {'completed','failed','cancelled','interrupted'}:break
        time.sleep(.1)
    assert job.status=='completed',job
    output=editor.collect('ninety')
    assert abs(output.duration-90)<.1
    assert (output.width,output.height)==(1920,1080)
    assert not output.audio_present
