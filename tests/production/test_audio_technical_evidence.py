"""Real local-audio measurement stays a technical preview, not semantic listening."""
import shutil
import subprocess
import pytest

from easel.production.inspection import observe_audio_technical


@pytest.mark.skipif(not (shutil.which('ffmpeg') and shutil.which('ffprobe')),
                    reason='local audio measurement needs actual FFmpeg and FFprobe')
def test_technical_audio_evidence_never_claims_semantic_hearing(tmp_path):
    target=tmp_path/'tone.wav'
    subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error',
                    '-f','lavfi','-i','sine=frequency=400:duration=2',
                    '-c:a','pcm_s16le','-y',str(target)],check=True,timeout=15)
    observed=observe_audio_technical(target,sample_seconds=1)
    assert observed['audio_present'] is True
    assert observed['duration_seconds']==2
    assert observed['measured_seconds']==1
    assert observed['measurement']=='ffprobe_and_ffmpeg_volumedetect'
    assert 'mean_volume_db' in observed and 'max_volume_db' in observed
    assert observed['heard_by_model'] is False
    assert observed['auditory_semantics']=='not_tested'


def test_missing_audio_reports_absence_not_fabricated_listening(tmp_path):
    # The pre-probed no-audio branch is also used for stock videos without sound.
    observed=observe_audio_technical(tmp_path/'unused.mp4',
                                     info={'audio':False,'duration':2,'streams':[]})
    assert observed=={'audio_present':False,'auditory_semantics':'not_tested'}
