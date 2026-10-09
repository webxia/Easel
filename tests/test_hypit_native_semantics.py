"""Semantic regression graphs expressed in installed Hypit 0.2.7 vocabulary."""
import json

import pytest

from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.hypit import native_audio_graph as audio, native_revision as revision
from easel.integrations.hypit.native_graph import audio_placement
from easel.integrations.hypit.native_source import parse_file, parse_text
from tests.test_hypit_native_source import native_fixture


SHEET = '''<?svml using="@hypit/svs@1"?>
<sheet version="1">
film.memo { background: #101820; }
text.caption { stack-order: 10; size: 48; fill: #FFFFFF; }
media.frame { stack-order: 0; }
media.sample { trim-start: 0; trim-end: 48; }
media.direct { stack-order: 0; trim-start: 0; trim-end: 48; }
media.transition { operator: crossfade; duration-frames: 12; audio: cut; }
</sheet>
'''

VIDEO = '''
<media:Video id="footage" src="./clip.mp4"/>
<pipeline:Normalize id="normalized" source={footage} video="primary-moving"
  audio="default" span-authority="video" clock={clock}/>
'''

ASSETS = [{"src": "./clip.mp4", "source_duration_seconds": 4,
           "observed_video_uses": [{"need_id": "demo", "required": True,
                                    "element_id_prefix": "scene-", "source_interval_seconds": [0, 2]}]}]


def semantic_source(root):
    path, source, timings, paths = native_fixture(root)
    path.with_name("recipes.svs").write_text(SHEET)
    source = source.replace('<import as="recipes"', '<import as="picture" from="@hypit/media-track@1"/>\n<import as="recipes"')
    source = source.replace('<film:Film', '<space:Frame id="other-frame" within={canvas} left="90px" top="1360px" right="990px" bottom="1640px"/>\n<film:Film')
    source = audio.compile_measured_narration(parse_text(source, path), timings, paths)
    path.write_text(source)
    return path, source, timings, paths


def with_picture(source, picture, *, sound=False, visual=True):
    source = source.replace("<film:Film", VIDEO + picture + "\n<film:Film")
    links = ('<Track source={pictures.visual}/>' if visual else '') + ('<Track source={pictures.audio}/>' if sound else '')
    return source.replace("</film:Film>", links + "</film:Film>")


def sequence(*, layers, sound=False):
    if layers:
        left = '<Layer id="voice-layer" media={normalized.media} appearance={recipes.media.sample}/>'
        right = '<Layer id="next-layer" media={normalized.media} appearance={recipes.media.sample}/>'
        a = 'source-audio="voice-layer"' if sound else ''
        b = 'source-audio="next-layer"' if sound else ''
        members = f'<Member id="scene-a" at="0s" {a}>{left}</Member><Handoff id="handoff-a" from="scene-a" transition={{recipes.media.transition}}/><Member id="scene-b" at="2s" {b}>{right}</Member>'
    else:
        members = '<Member id="scene-a" at="0s" media={normalized.media} appearance={recipes.media.direct}/><Handoff id="handoff-a" from="scene-a" transition={recipes.media.transition}/><Member id="scene-b" at="2s" media={normalized.media} appearance={recipes.media.direct}/>'
    return '<picture:Track id="pictures" canvas={canvas} timeline={program.timeline}><Sequence id="sequence" frame={easel-caption-frame} appearance={recipes.media.frame} until="4s">' + members + '</Sequence></picture:Track>'


@pytest.mark.parametrize("before,after", [
    ("trim-start: 0; trim-end: 48", "trim-start: 24; trim-end: 72"),
    ("audio: cut", "audio: crossfade"),
])
def test_visual_scope_keeps_source_audio_sampling_and_handoff(tmp_path, before, after):
    base, source, _, _ = semantic_source(tmp_path / "base")
    target, _, _, _ = semantic_source(tmp_path / "target")
    source = with_picture(source, sequence(layers=True, sound=True), sound=True)
    base.write_text(source)
    target.write_text(source.replace('id="sequence" frame={easel-caption-frame}',
                                     'id="sequence" frame={other-frame}'))
    revision.assert_quality_revision(base, target, {"visual"})
    target.with_name("recipes.svs").write_text(SHEET.replace(before, after))
    with pytest.raises(HypitIntegrationError, match="未授权部分"):
        revision.assert_quality_revision(base, target, {"visual"})


def test_caption_scope_does_not_move_independent_director_headline(tmp_path):
    base, source, _, _ = semantic_source(tmp_path / "base")
    target, _, _, _ = semantic_source(tmp_path / "target")
    headline = '<typo:Track id="headline-track" timeline={program.timeline}><Area id="headline" placement={easel-caption-frame} style={easel-caption-style} at="0s" for="4s">导演标题</Area></typo:Track>'
    source = source.replace("<film:Film", headline + "<film:Film").replace("</film:Film>", '<Track source={headline-track.track}/></film:Film>')
    base.write_text(source)
    target.write_text(source.replace('id="headline" placement={easel-caption-frame}', 'id="headline" placement={other-frame}'))
    with pytest.raises(HypitIntegrationError, match="未授权部分"):
        revision.assert_quality_revision(base, target, {"captions"})


@pytest.mark.parametrize("intruder", ["extra_area", "direct_copy"])
def test_caption_compiler_preserves_unowned_content_by_rejecting_it(tmp_path, intruder):
    path, source, timings, paths = semantic_source(tmp_path)
    doc = parse_text(source, path)
    track = doc.nodes["easel-captions"]
    if intruder == "extra_area":
        original = doc.source.slice(track.range)
        changed = original.replace("</typo:Track>", '<Area id="headline" placement={easel-caption-frame} style={easel-caption-style} at="0s" for="4s">导演标题</Area></typo:Track>')
    else:
        area = doc.nodes["easel-caption-0"]
        original = doc.source.slice(area.range)
        changed = '<typo:Area id="easel-caption-0" placement={easel-caption-frame} style={easel-caption-style} at="14f" for="27f">导演自写正文</typo:Area>'
    with pytest.raises(HypitIntegrationError, match="程序字幕区域"):
        audio.compile_measured_narration(parse_text(source.replace(original, changed), path), timings, paths)


def test_voice_graph_rejects_second_extract_audio_chain_in_actual_film(tmp_path):
    path, source, _, _ = semantic_source(tmp_path)
    extra = '''<pipeline:ExtractAudio id="voice-extract" source={voice-source} audio="default"/>
<pipeline:Normalize id="voice-extra-media" source={voice-extract.audio} video="none" audio="default" span-authority="audio" clock={clock}/>
<audio:Track id="voice-extra-track" timeline={program.timeline}><Item source={voice-extra-media.media} at="12f" for="73f" playback="once"/></audio:Track>'''
    source = source.replace("<film:Film", extra + "<film:Film").replace("</film:Film>", '<Track source={voice-extra-track.audio}/></film:Film>')
    with pytest.raises(HypitIntegrationError, match="另一条处理链"):
        audio_placement(parse_text(source, path), "./voice.wav")


def test_audio_port_cannot_satisfy_visual_observation_or_expression(tmp_path):
    path, source, _, _ = semantic_source(tmp_path)
    picture = '<picture:Track id="pictures" canvas={canvas} timeline={program.timeline}><Item id="scene-demo" frame={easel-caption-frame} media={normalized.media} appearance={recipes.media.direct} source-audio="content" at="0s" for="2s"/></picture:Track>'
    source = with_picture(source, picture, visual=False, sound=True)
    source += "\n<!-- Easel expression: " + json.dumps({
        "need_id": "demo", "element_ids": ["scene-demo"], "at_seconds": 0, "end_seconds": 2,
        "responsibility": "material"}) + " -->"
    doc = parse_text(source, path)
    with pytest.raises(HypitIntegrationError, match="未进入 Film"):
        revision.expression_uses(doc, required_need_ids={"demo"})
    with pytest.raises(HypitIntegrationError, match="必要视频场景"):
        revision.assert_observed_video_uses(doc, ASSETS)


def test_extract_frame_cannot_bypass_observed_video_window(tmp_path):
    path, source, _, _ = semantic_source(tmp_path)
    picture = '''<pipeline:ExtractFrame id="late-frame" source={footage} video="primary-moving" at="last"/>
<space:Extent id="frame-extent" width="1080" height="1920"/>
<picture:Track id="pictures" canvas={canvas} timeline={program.timeline}><Item id="scene-demo" frame={easel-caption-frame} image={late-frame.image} extent={frame-extent} appearance={recipes.media.frame} at="0s" for="2s"/></picture:Track>'''
    doc = parse_text(with_picture(source, picture), path)
    with pytest.raises(HypitIntegrationError, match="静帧"):
        revision.assert_observed_video_uses(doc, ASSETS)


@pytest.mark.parametrize("layers", [False, True], ids=["member", "layer"])
def test_member_and_layer_trim_obey_observation_and_actual_source_duration(tmp_path, layers):
    path, source, _, _ = semantic_source(tmp_path)
    path.write_text(with_picture(source, sequence(layers=layers)))
    doc = parse_file(path)
    revision.assert_observed_video_uses(doc, ASSETS)
    revision.assert_video_trim_ranges(doc, {"./clip.mp4": 4})
    path.with_name("recipes.svs").write_text(SHEET.replace("trim-end: 48", "trim-end: 49"))
    with pytest.raises(HypitIntegrationError, match="越过已观察区间"):
        revision.assert_observed_video_uses(parse_file(path), ASSETS)
    path.with_name("recipes.svs").write_text(SHEET.replace("trim-end: 48", "trim-end: 97"))
    with pytest.raises(HypitIntegrationError, match="超出原片范围"):
        revision.assert_video_trim_ranges(parse_file(path), {"./clip.mp4": 4})

@pytest.mark.parametrize("media,route", [("voice", "second_track"), ("voice", "extract"), ("music", "extract")])
def test_quality_measurement_keeps_ambiguous_native_audio_unverifiable(tmp_path, media, route):
    from easel.integrations.hypit import quality
    path, source, _, _ = semantic_source(tmp_path)
    normal = parse_text(source, path)
    if media == "voice":
        assert quality._native_voice_placement(normal, "./voice.wav") == pytest.approx(.5)
    else:
        quality._native_music_clip(normal, "./music.wav")
    prefix = ""
    normal_id = media + "-media"
    if route == "extract":
        prefix = (f'<pipeline:ExtractAudio id="{media}-extract" source={{{media}-source}} audio="default"/>'
                  f'<pipeline:Normalize id="{media}-extra-media" source={{{media}-extract.audio}} '
                  'video="none" audio="default" span-authority="audio" clock={clock}/>')
        normal_id = media + "-extra-media"
    extra = (prefix + f'<audio:Track id="{media}-extra-track" timeline={{program.timeline}}>'
             f'<Item source={{{normal_id}.media}} at="12f" for="73f" playback="once"/></audio:Track>')
    changed = source.replace("<film:Film", extra + "<film:Film").replace(
        "</film:Film>", f'<Track source={{{media}-extra-track.audio}}/></film:Film>')
    doc = parse_text(changed, path)
    if media == "voice":
        assert quality._native_voice_placement(doc, "./voice.wav") is None
    else:
        with pytest.raises(ValueError, match="原生图尚不能核实"):
            quality._native_music_clip(doc, "./music.wav")

