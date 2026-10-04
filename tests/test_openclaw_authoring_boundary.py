import json
import subprocess
from pathlib import Path

import pytest
from easel.integrations.hypit.errors import HypitIntegrationError

from easel.integrations.openclaw_authoring import (
    OpenClawAuthoringBoundaryError,
    authoring_agent_policy,
    run_attempt_scoped_authoring,
    _agent_result,
)
from easel.integrations.hypit.revision import assert_composition_preserves_sound_and_copy, assert_video_trim_ranges


ATTEMPT_ID = "fa_0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize("change", ["gain", "source", "fade", "copy", "schedule", "clock", "visual"])
def test_composition_revision_cannot_change_accepted_sound_or_copy(tmp_path, change):
    base = tmp_path / "base.svml"
    source = '''<svml>
      <import as="a" from="@hypit/audio-track@1"/>
      <import as="m" from="@hypit/media@1"/>
      <import as="p" from="@hypit/media-pipeline@1"/>
      <import as="t" from="@hypit/timeline-author@1"/>
      <import as="copy" from="@hypit/text@1"/>
      <import as="typo" from="@hypit/typography-track@1"/>
      <import as="v" from="@hypit/media-track@1"/>
      <t:Clock id="clock" frame-rate="24"/>
      <t:Timeline id="program" clock={clock} end="36s"/>
      <m:Audio id="music" src="music.mp3"/>
      <p:Normalize id="normalized" source={music} clock={clock} audio="default"/>
      <a:Track id="sound" timeline={program.timeline}>
        <a:Item source={normalized.media} during="program" gain="0.4" fade-in="800ms"/>
      </a:Track>
      <copy:Value id="words">看窗外。</copy:Value>
      <typo:Track id="captions" timeline={program.timeline}>
        <typo:Area content={words} at="21s" for="8s"/>
      </typo:Track>
      <v:Item id="leaf" at="21s" for="8s" frame={leafFrame}/>
    </svml>'''
    base.write_text(source)
    replacements = {
        "gain": ('gain="0.4"', 'gain="0.28"'),
        "source": ('src="music.mp3"', 'src="other.mp3"'),
        "fade": ('fade-in="800ms"', 'fade-in="600ms"'),
        "copy": ('看窗外。', '换了内容。'),
        "schedule": ('content={words} at="21s"', 'content={words} at="22s"'),
        "clock": ('end="36s"', 'end="35s"'),
        "visual": ('frame={leafFrame}', 'frame={newLeafFrame}'),
    }
    authored = tmp_path / "authored.svml"
    authored.write_text(source.replace(*replacements[change]))
    if change == "visual":
        assert_composition_preserves_sound_and_copy(base, authored)
    else:
        with pytest.raises(HypitIntegrationError, match="声音、字幕或时序"):
            assert_composition_preserves_sound_and_copy(base, authored)


def test_authoring_process_diagnostics_do_not_expose_model_output_or_credentials():
    def failed(cmd, **kwargs):
        return subprocess.CompletedProcess(cmd, 1, "private model response", "502 HTML error page Authorization=private-credential")
    with pytest.raises(OpenClawAuthoringBoundaryError, match="异常网关响应") as result:
        _agent_result(failed, ["openclaw"], phase="执行")
    assert "private" not in str(result.value)
    def timed_out(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 5, output="private response")
    with pytest.raises(OpenClawAuthoringBoundaryError, match="超时"):
        _agent_result(timed_out, ["openclaw"], phase="执行")


@pytest.mark.parametrize("start,end,okay", [(120,312,True), (300,780,False), (-1,312,False), (312,120,False)])
def test_video_trim_uses_normalized_clock_and_admitted_source_span(tmp_path, start, end, okay):
    author = tmp_path / "main.svml"
    author.write_text('''<svml>
      <import as="v" from="@hypit/media-track@1"/>
      <import as="p" from="@hypit/media-pipeline@1"/>
      <import as="m" from="@hypit/media@1"/>
      <import as="t" from="@hypit/timeline-author@1"/>
      <import as="recipes" source="./recipes.svs"/>
      <t:Clock id="clock" frame-rate="24"/>
      <m:Video id="leaf" src="leaf.mp4"/>
      <p:Normalize id="normalized" source={leaf} clock={clock}/>
      <v:Item media={normalized.media} appearance={recipes.media.leaf}/>
    </svml>''')
    (tmp_path / "recipes.svs").write_text(f'media.leaf {{ fit: cover; trim-start: {start}; trim-end: {end}; }}')
    if okay:
        assert_video_trim_ranges(author, {"leaf.mp4":27.605})
    else:
        with pytest.raises(HypitIntegrationError, match="超出原片范围"):
            assert_video_trim_ranges(author, {"leaf.mp4":27.605})


def _seed_attempt(root: Path) -> Path:
    root.mkdir()
    (root / "AUTHORING_TASK.md").write_text("write only authoring outputs", encoding="utf-8")
    (root / "package.json").write_text("{}", encoding="utf-8")
    (root / "handoff").mkdir()
    (root / "handoff" / "truth.json").write_text('{"truth": "frozen"}', encoding="utf-8")
    (root / "planning").mkdir()
    (root / "planning" / "SCRIPT.md").write_text("frozen script", encoding="utf-8")
    (root / "materials" / "assets" / "asset-1").mkdir(parents=True)
    (root / "materials" / "assets" / "asset-1" / "asset.json").write_text(
        '{"asset_id":"asset-1"}', encoding="utf-8")
    (root / "materials" / "assets" / "asset-1" / "private-media.bin").write_bytes(b"not staged")
    (root / "productions" / "easel-authoring").mkdir(parents=True)
    (root / "productions" / "easel-authoring" / "SCRIPT.md").write_text(
        "frozen script", encoding="utf-8")
    return root


def test_authoring_policy_has_only_workspace_text_tools(tmp_path):
    policy = authoring_agent_policy(tmp_path / "workspace", tmp_path / "agent")
    tools = policy["tools"]
    assert tools["profile"] == "minimal"
    assert tools["alsoAllow"] == ["read", "write", "edit"]
    assert tools["fs"] == {"workspaceOnly": True}
    assert tools["elevated"] == {"enabled": False}
    assert "group:runtime" in tools["deny"]
    assert "group:media" in tools["deny"]
    assert policy["skills"] == []


def test_attempt_authoring_stages_inputs_and_promotes_only_approved_files(tmp_path):
    attempt = _seed_attempt(tmp_path / "attempt")
    stage_parent = tmp_path / "openclaw" / "authoring-staging"
    config = {}
    agent_workspace = None
    calls = []

    def runner(cmd, **kwargs):
        nonlocal config, agent_workspace
        calls.append(cmd)
        if "config" in cmd and "patch" in cmd:
            config = json.loads(kwargs["input"])
            entry = config["agents"]["entries"]
            agent_id, value = next(iter(entry.items()))
            if value is not None:
                agent_workspace = Path(value["workspace"])
            return subprocess.CompletedProcess(cmd, 0, "{}", "")
        if "config" in cmd and "validate" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "valid", "")
        if "agents" in cmd and "list" in cmd:
            agent_id = next(iter(config["agents"]["entries"]))
            payload = [{"id": agent_id, "workspace": str(agent_workspace)}]
            return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")
        if "agents" in cmd and "delete" in cmd:
            return subprocess.CompletedProcess(cmd, 0, '{"removed":[]}', "")
        if "agent" in cmd:
            assert agent_workspace is not None
            assert (agent_workspace / "hypit-contracts/media-track.json").read_text() == '{"contract":"installed"}'
            message = cmd[cmd.index("--message") + 1]
            assert str(attempt) not in message
            assert str(agent_workspace) in message
            (agent_workspace / "productions/easel-authoring/authors").mkdir(parents=True, exist_ok=True)
            (agent_workspace / "productions/easel-authoring/runs").mkdir(parents=True, exist_ok=True)
            (agent_workspace / "productions/easel-authoring/material-selection.json").write_text(
                '{"schema":"test"}', encoding="utf-8")
            (agent_workspace / "productions/easel-authoring/authors/main.svml").write_text(
                "<svml/>", encoding="utf-8")
            (agent_workspace / "productions/easel-authoring/authors/recipes.svs").write_text(
                '<?svml using="@hypit/svs@1"?><sheet version="1">'
                'media.still { stack-order: 10; fit: cover; }</sheet>', encoding="utf-8")
            (agent_workspace / "productions/easel-authoring/runs/main.svrun").write_text(
                "<svrun/>", encoding="utf-8")
            (agent_workspace / "outside.txt").write_text("must not promote", encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, "done", "")
        raise AssertionError(f"unexpected OpenClaw command: {cmd}")

    def prepare_contracts(staged):
        target = staged / "hypit-contracts"
        target.mkdir()
        (target / "media-track.json").write_text('{"contract":"installed"}')

    result = run_attempt_scoped_authoring(
        attempt_id=ATTEMPT_ID,
        attempt_workspace=attempt,
        message=f"workspace={attempt}",
        command_prefix=["openclaw"],
        profile="easel",
        staging_parent=stage_parent,
        timeout=5,
        thinking="off",
        cwd=tmp_path,
        env={},
        runner=runner,
        prepare_workspace=prepare_contracts,
    )

    assert result == "done"
    assert (attempt / "productions/easel-authoring/material-selection.json").is_file()
    assert (attempt / "productions/easel-authoring/authors/main.svml").is_file()
    assert (attempt / "productions/easel-authoring/authors/recipes.svs").is_file()
    assert (attempt / "productions/easel-authoring/runs/main.svrun").is_file()
    assert not (attempt / "outside.txt").exists()
    assert not (attempt / "hypit-contracts").exists()
    assert (attempt / "materials/assets/asset-1/private-media.bin").read_bytes() == b"not staged"
    assert any("agent" in call and "--agent" in call for call in calls)
    assert any("config" in call and "patch" in call for call in calls)
    assert any("agents" in call and "delete" in call for call in calls)
    assert list(stage_parent.iterdir()) == []

    trusted = attempt / "productions/easel-authoring/authors/main.svml"
    trusted.write_text("trusted previous source", encoding="utf-8")
    def reject_invalid(_staged: Path) -> None:
        raise HypitIntegrationError("Hypit check 失败：无效结构")
    with pytest.raises(HypitIntegrationError, match="无效结构"):
        run_attempt_scoped_authoring(
            attempt_id=ATTEMPT_ID, attempt_workspace=attempt, message=f"workspace={attempt}; repair",
            command_prefix=["openclaw"], profile="easel", staging_parent=stage_parent,
            timeout=5, thinking="off", cwd=tmp_path, env={}, runner=runner,
            validate_artifacts=reject_invalid,
            prepare_workspace=prepare_contracts,
        )
    assert trusted.read_text(encoding="utf-8") == "trusted previous source"
    calls_before = len(calls)
    def missing_contracts(_staged: Path) -> None:
        raise HypitIntegrationError("installed vocabulary unavailable")
    with pytest.raises(HypitIntegrationError, match="vocabulary unavailable"):
        run_attempt_scoped_authoring(
            attempt_id=ATTEMPT_ID, attempt_workspace=attempt, message=f"workspace={attempt}",
            command_prefix=["openclaw"], profile="easel", staging_parent=stage_parent,
            timeout=5, thinking="off", cwd=tmp_path, env={}, runner=runner,
            prepare_workspace=missing_contracts,
        )
    assert len(calls) == calls_before  # No Agent provision or execution without its contracts.
    assert trusted.read_text(encoding="utf-8") == "trusted previous source"
    assert list(stage_parent.iterdir()) == []


@pytest.mark.parametrize("outcome", ["run_only", "missing_sources", "still_missing"])
def test_attempt_authoring_repairs_only_missing_allowlisted_artifacts_once(tmp_path, outcome):
    attempt = _seed_attempt(tmp_path / "attempt")
    stage_parent = tmp_path / "openclaw" / "authoring-staging"
    config = {}
    agent_workspace = None
    agent_messages = []

    def runner(cmd, **kwargs):
        nonlocal config, agent_workspace
        if "config" in cmd and "patch" in cmd:
            config = json.loads(kwargs["input"])
            policy = next(iter(config["agents"]["entries"].values()))
            if policy is not None:
                agent_workspace = Path(policy["workspace"])
            return subprocess.CompletedProcess(cmd, 0, "{}", "")
        if "config" in cmd and "validate" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "valid", "")
        if "agents" in cmd and "list" in cmd:
            agent_id = next(iter(config["agents"]["entries"]))
            return subprocess.CompletedProcess(
                cmd, 0, json.dumps([{"id": agent_id, "workspace": str(agent_workspace)}]), "",
            )
        if "agents" in cmd and "delete" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "{}", "")
        if "agent" in cmd:
            message = cmd[cmd.index("--message") + 1]
            agent_messages.append(message)
            authoring = agent_workspace / "productions/easel-authoring"
            (authoring / "authors").mkdir(parents=True, exist_ok=True)
            (authoring / "runs").mkdir(parents=True, exist_ok=True)
            if len(agent_messages) == 1:
                (authoring / "material-selection.json").write_text('{"schema":"test"}', encoding="utf-8")
                if outcome == "run_only":
                    (authoring / "authors/main.svml").write_text("<svml/>", encoding="utf-8")
            if len(agent_messages) == 2:
                assert "样式依赖" in message
                assert (authoring / "material-selection.json").read_text() == '{"schema":"test"}'
                if outcome != "still_missing":
                    (authoring / "runs/main.svrun").write_text("<svrun/>", encoding="utf-8")
                if outcome == "missing_sources":
                    (authoring / "authors/main.svml").write_text(
                        '<svml><import as="recipes" source="./recipes.svs"/></svml>')
                    (authoring / "authors/recipes.svs").write_text("media.still { fit: cover; }")
            return subprocess.CompletedProcess(cmd, 0, "done", "")
        raise AssertionError(f"unexpected OpenClaw command: {cmd}")

    def run():
        return run_attempt_scoped_authoring(
            attempt_id=ATTEMPT_ID,
            attempt_workspace=attempt,
            message=f"workspace={attempt}",
            command_prefix=["openclaw"],
            profile="easel",
            staging_parent=stage_parent,
            timeout=5,
            thinking="off",
            cwd=tmp_path,
            env={},
            runner=runner,
        )

    if outcome == "still_missing":
        with pytest.raises(OpenClawAuthoringBoundaryError, match="补齐后仍缺少"):
            run()
        assert not (attempt / "productions/easel-authoring/authors/main.svml").exists()
    else:
        run()
        assert (attempt / "productions/easel-authoring/runs/main.svrun").is_file()
        if outcome == "missing_sources":
            assert (attempt / "productions/easel-authoring/authors/recipes.svs").is_file()

    assert len(agent_messages) == 2
    assert "productions/easel-authoring/runs/main.svrun" in agent_messages[1]
    assert list(stage_parent.iterdir()) == []


def test_attempt_authoring_preserves_restricted_workspace_when_agent_cleanup_fails(tmp_path):
    attempt = _seed_attempt(tmp_path / "attempt")
    stage_parent = tmp_path / "openclaw" / "authoring-staging"
    agent_workspace = None

    def runner(cmd, **kwargs):
        nonlocal agent_workspace
        if "config" in cmd and "patch" in cmd:
            patch = json.loads(kwargs["input"])
            policy = next(iter(patch["agents"]["entries"].values()))
            if policy is not None:
                agent_workspace = Path(policy["workspace"])
            return subprocess.CompletedProcess(cmd, 0, "{}", "")
        if "config" in cmd and "validate" in cmd:
            return subprocess.CompletedProcess(cmd, 0, "valid", "")
        if "agents" in cmd and "list" in cmd:
            agent_id = cmd[cmd.index("--agent") + 1] if "--agent" in cmd else "easel-author"
            return subprocess.CompletedProcess(
                cmd, 0, json.dumps([{"id": agent_id, "workspace": str(agent_workspace)}]), "",
            )
        if "agent" in cmd and "delete" not in cmd:
            return subprocess.CompletedProcess(cmd, 0, "done", "")
        if "agents" in cmd and "delete" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "delete failed")
        raise AssertionError(f"unexpected OpenClaw command: {cmd}")

    with pytest.raises(OpenClawAuthoringBoundaryError, match="受限 Agent 配置保持有效"):
        run_attempt_scoped_authoring(
            attempt_id=ATTEMPT_ID,
            attempt_workspace=attempt,
            message="author",
            command_prefix=["openclaw"],
            profile="easel",
            staging_parent=stage_parent,
            timeout=5,
            thinking="off",
            cwd=tmp_path,
            env={},
            runner=runner,
        )
    retained = list(stage_parent.iterdir())
    assert len(retained) == 1
    assert agent_workspace is not None and agent_workspace.is_dir()


def test_attempt_authoring_fails_closed_on_symlink_input(tmp_path):
    attempt = _seed_attempt(tmp_path / "attempt")
    (attempt / "handoff" / "escape").symlink_to(tmp_path / "outside")
    with pytest.raises(OpenClawAuthoringBoundaryError, match="符号链接"):
        run_attempt_scoped_authoring(
            attempt_id=ATTEMPT_ID,
            attempt_workspace=attempt,
            message="author",
            command_prefix=["openclaw"],
            profile="easel",
            staging_parent=tmp_path / "stage",
            timeout=5,
            thinking="off",
            cwd=tmp_path,
            env={},
            runner=lambda *_args, **_kwargs: pytest.fail("must not invoke OpenClaw"),
        )


def test_attempt_authoring_rejects_missing_or_symlinked_authoring_output(tmp_path):
    attempt = _seed_attempt(tmp_path / "attempt")
    staged = _seed_attempt(tmp_path / "staged")
    author = staged / "productions/easel-authoring/authors"
    author.mkdir(parents=True)
    (author / "main.svml").symlink_to(tmp_path / "outside.svml")
    with pytest.raises(OpenClawAuthoringBoundaryError, match="普通文件"):
        # Drive the internal promotion boundary via an isolated fake CLI turn.
        from easel.integrations.openclaw_authoring import _promote_authoring_artifacts
        _promote_authoring_artifacts(staged, attempt)
