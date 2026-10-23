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


def test_measure_selected_tail_not_unrelated_intro(tmp_path):
    target = tmp_path/'changing.wav'
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi',
        '-i','sine=frequency=400:duration=2','-af',"volume=0.1:enable='gte(t,1)'",
        '-y',str(target)],check=True,timeout=15)
    intro=observe_audio_technical(target,sample_seconds=.5)
    tail=observe_audio_technical(target,source_start=1.5,sample_seconds=1)
    assert tail['source_start']==1.5 and tail['measured_seconds']==.5
    assert float(tail['mean_volume_db'])==pytest.approx(float(intro['mean_volume_db'])-20,abs=.5)
    with pytest.raises(ValueError):
        observe_audio_technical(target,source_start=2)


def test_closing_mix_arithmetic_exposes_quiet_music_without_rejecting_it():
    from types import SimpleNamespace as NS
    from easel.production.narration import closing_mix_evidence
    project=NS(duration=30,scenes=[],captions=[],audio=[
        NS(clip_id='voice',asset_id='v',role='voice',gain=1,at=.2,duration=24.984,fade_out=0),
        NS(clip_id='music',asset_id='m',role='music',gain=.13,at=0,duration=30,fade_out=3)])
    result=closing_mix_evidence(project,{'m':{'mean_volume_db':'-24','max_volume_db':'-10'}})
    assert result['timeline']['unvoiced_tail_seconds']==pytest.approx(4.816)
    assert result['clips'][1]['estimated_pre_fade_mean_volume_db']==pytest.approx(-41.72)
    assert result['clips'][1]['fade_out_start']==27
    assert 'estimated_pre_fade_mean_volume_db' not in result['clips'][0]
    project.audio[1].gain=0
    assert 'estimated_pre_fade_mean_volume_db' not in closing_mix_evidence(project,{'m':{'mean_volume_db':'-inf'}})['clips'][1]
