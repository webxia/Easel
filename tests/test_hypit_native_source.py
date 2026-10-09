"""Actual installed native parser through Easel's production-domain consumers."""
import json
from pathlib import Path

import pytest

from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.hypit.native_source import NativeSourceError, Reference, parse_file, parse_run, parse_text
from easel.integrations.hypit import native_audio_graph as audio
from easel.integrations.hypit import native_revision as revision
from easel.integrations.hypit.music import install_music_component


def native_fixture(root):
    from tests.test_hypit_integration import measured_narration_fixture
    source, timings, paths = measured_narration_fixture()
    root.mkdir(parents=True, exist_ok=True)
    path = root / "main.svml"
    path.write_bytes(source.encode())
    path.with_name("recipes.svs").write_text(
        '<?svml using="@hypit/svs@1"?>\n<sheet version="1">\n'
        'film.memo { background: #101820; }\n'
        'text.caption { size: 48; fill: #FFFFFF; features: {"text":"trim-start: 0; }","weight":1}; }\n'
        'media.clip { trim-start: 0; trim-end: 48; enabled: true; quoted: "24"; }\n'
        '</sheet>\n')
    return path, source, timings, paths


def test_native_parsers_bind_typed_recipes_run_aliases_and_exact_source(tmp_path):
    path, source, _, _ = native_fixture(tmp_path)
    source = source.replace('as="audio"', "as='sound'").replace("audio:", "sound:")
    source = source.replace("<sound:Item", "<Item").replace("<film:Track", "<Track")
    source = source.replace('<time:Clock', '<copy:Value id="lead">😀 &amp;\r\n原文</copy:Value>\r<time:Clock')
    source = source.replace('<import as="recipes"', '<import as="same" source="./recipes.svs"/>\n<import as="recipes"')
    source = source.replace("\n", "\r\n")
    path.write_bytes(source.encode())
    doc = parse_file(path)
    assert doc.source.raw == path.read_bytes()
    assert doc.kind(doc.nodes["voice-track"].children[1]) == ("@hypit/audio-track", "Item")
    node = doc.nodes["voice-source"]
    assert doc.source.slice(node.range).startswith('<media:Audio id="voice-source"')
    assert doc.source.slice(node.attribute_ranges["src"]) == "./voice.wav"
    assert doc.recipe(Reference("recipes.media.clip")) == {
        "trim-start": 0, "trim-end": 48, "enabled": True, "quoted": "24"}
    assert doc.sheets["same"][0] is doc.sheets["recipes"][0]
    literal = parse_text(source.replace("clock={clock}", 'clock="{clock}"'), path)
    assert literal.nodes["program"].ref("clock") is None
    assert literal.nodes["program"].literal("clock") == "{clock}"
    run_path = tmp_path / "main.svrun"
    run_path.write_text('<?svml using="@hypit/run-markup@1"?>\n'
                        "<svrun version='1'><author source='main.svml'/><target output='final.video'/></svrun>")
    snapshot, run, identity = parse_run(run_path)
    assert run["author"]["source"] == "main.svml" and run["targets"] == [{"output": "final.video"}]
    assert snapshot.raw == run_path.read_bytes()
    assert identity == doc.identity


@pytest.mark.parametrize("mutation,code", [
    (lambda text: text.replace("</svml>", '<import as="late" from="@hypit/script@1"/></svml>'), "EASEL_IMPORT_AFTER_BODY"),
    (lambda text: text.replace('id="voice-source"', 'id="recipes.media.clip"'), "EASEL_REFERENCE_COLLISION"),
    (lambda text: text.replace('id="voice-source"', 'id="voice-source" id="duplicate"'), "MARKUP_ATTRIBUTE_DUPLICATE"),
    (lambda text: text.replace('as="audio"', 'as="media"'), "EASEL_ALIAS_COLLISION"),
])
def test_native_source_rejects_ambiguous_or_out_of_profile_input(tmp_path, mutation, code):
    path, source, _, _ = native_fixture(tmp_path)
    with pytest.raises(NativeSourceError) as error:
        parse_text(mutation(source), path)
    assert error.value.diagnostic["code"] == code
    assert path.read_bytes() == source.encode()


def test_native_narration_and_music_share_actual_graph_and_preserve_unicode(tmp_path):
    path, source, timings, paths = native_fixture(tmp_path)
    timings["assets"][0]["cues"][0]["display_text"] = "😀第一句<&>。\r\n冻结原文"
    source = source.replace('as="audio"', "as='sound'").replace("audio:", "sound:")
    source = source.replace("<sound:Item", "<Item").replace("<film:Track", "<Track")
    source = source.replace('at="12f"', "at='12f'")
    doc = parse_text(source, path)
    compiled = audio.compile_measured_narration(doc, timings, paths)
    assert 'at="12f" for="73f"' in compiled
    assert "😀第一句&lt;&amp;&gt;。\r\n冻结原文" in compiled
    doc = parse_text(compiled, path)
    assert audio.compile_measured_narration(doc, timings, paths) == compiled
    paths["music"] = "./music.wav"
    policy = {"gain_ratio": .25, "attack_seconds": .12, "release_seconds": .45}
    lowered = audio.compile_music_ducking(doc, timings, paths, {"music"}, policy)
    install_music_component(tmp_path)
    final = parse_text(lowered, path)
    assert audio.compile_music_ducking(final, timings, paths, {"music"}, policy) == lowered
    from easel.integrations.hypit.native_graph import audio_placement
    assert audio_placement(final, "./voice.wav").duck is None
    music = audio_placement(final, "./music.wav", allow_trusted_duck=True)
    assert music.duck.literal("id") == "easel-duck-music-track"
    with pytest.raises(HypitIntegrationError):
        audio.compile_measured_narration(parse_text(source.replace("clock={clock}", 'clock="{clock}"'), path), timings, paths)
    with pytest.raises(HypitIntegrationError, match="程序编排区域"):
        injected = lowered.replace("<!-- Easel measured music: end -->",
                                   '<copy:Value id="unowned">不可删除</copy:Value><!-- Easel measured music: end -->')
        audio.compile_music_ducking(parse_text(injected, path), timings, paths, {"music"}, policy)


def test_native_revision_protects_typed_dependencies_and_all_text(tmp_path):
    base, source, timings, paths = native_fixture(tmp_path / "base")
    target, _, _, _ = native_fixture(tmp_path / "target")
    original = audio.compile_measured_narration(parse_file(base), timings, paths)
    base.write_text(original)
    target.write_text(original.replace('gain="0.1"', 'gain="0.04"'))
    revision.assert_quality_revision(base, target, {"audio"})
    sheet = target.with_name("recipes.svs")
    original_sheet = sheet.read_text()
    sheet.write_text(original_sheet.replace('"weight":1', '"weight":2'))
    with pytest.raises(HypitIntegrationError, match="未授权部分"):
        revision.assert_quality_revision(base, target, {"audio"})
    sheet.write_text(original_sheet)
    target.write_text(original.replace('top="1420px"', 'top="1360px"'))
    sheet.write_text(original_sheet.replace("size: 48", "size: 56"))
    revision.assert_quality_revision(base, target, {"captions"})
    sheet.write_text(original_sheet)
    for old, new in [('第一句', '新增事实'), ('source={voice-track.audio}', 'source="{voice-track.audio}"'),
                     ('at="12f"', 'at="24f"')]:
        target.write_text(original.replace(old, new))
        with pytest.raises(HypitIntegrationError, match="未授权部分"):
            revision.assert_quality_revision(base, target, {"visual", "captions", "audio"})


def test_native_observation_trim_and_expression_use_actual_reachable_graph(tmp_path):
    path, source, _, _ = native_fixture(tmp_path)
    source = source.replace('<import as="recipes"', '<import as="picture" from="@hypit/media-track@1"/>\n<import as="recipes"')
    source = source.replace('<film:Film', '''
<media:Video id="footage" src="./clip.mp4"/>
<pipeline:Normalize id="normalized" source={footage} clock={clock}/>
<picture:Track id="pictures" canvas={canvas} timeline={program.timeline}>
  <Item id="scene-demo" media={normalized.media} appearance={recipes.media.clip} at="0s" for="2s"/>
</picture:Track><film:Film''').replace('<film:Track source={voice-track.audio}/>',
                                   '<Track source={pictures.visual}/><film:Track source={voice-track.audio}/>')
    row = {"need_id": "demo", "element_ids": ["scene-demo"], "at_seconds": 0, "end_seconds": 2,
           "responsibility": "material"}
    source += "\n<!-- Easel expression: " + json.dumps(row) + " -->"
    path.write_text(source)
    doc = parse_file(path)
    assets = [{"src": "./clip.mp4", "source_duration_seconds": 4,
               "observed_video_uses": [{"need_id": "demo", "required": True,
                                       "element_id_prefix": "scene-", "source_interval_seconds": [0, 2]}]}]
    revision.assert_observed_video_uses(doc, assets)
    revision.assert_video_trim_ranges(doc, {"./clip.mp4": 4})
    assert revision.expression_uses(doc, required_need_ids={"demo"}) == [row]
    sheet = path.with_name("recipes.svs")
    initial = sheet.read_text()
    for value in ('"48"', "true", "49"):
        sheet.write_text(initial.replace("trim-end: 48", "trim-end: " + value))
        with pytest.raises(HypitIntegrationError):
            revision.assert_observed_video_uses(parse_file(path), assets)
    sheet.write_text(initial)
    invisible = parse_text(source.replace('<Track source={pictures.visual}/>', ""), path)
    with pytest.raises(HypitIntegrationError, match="未进入 Film"):
        revision.expression_uses(invisible, required_need_ids={"demo"})
