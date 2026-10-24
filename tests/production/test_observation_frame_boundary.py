import shutil, subprocess
import pytest
from easel.production.inspection import observe_media
from easel.production.tools import ToolInputError

@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg required')
def test_exact_last_frame_is_valid_but_after_last_is_rejected(tmp_path):
    p=tmp_path/'boundary.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=96x64:r=25','-frames:v','331','-y',str(p)],check=True)
    blocks,_,e=observe_media(p,frame_times=(13.2,))
    assert blocks and abs(e['frame_times'][0]-13.2)<.00001
    with pytest.raises(ToolInputError,match='bounds') as error:
        observe_media(p,frame_times=(13.21,))
    assert error.value.feedback['executed'] is False
    assert error.value.feedback['max_seconds'] == pytest.approx(13.2, abs=.000002)
    blocks, _, evidence = observe_media(p, frame_times=(error.value.feedback['max_seconds'],))
    assert blocks and evidence['frame_times'][0] <= 13.2
