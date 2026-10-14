"""New Web video ingress is Delivery-owned; old rows remain read-only."""
from __future__ import annotations
import asyncio
from contextlib import nullcontext
import pytest
from fastapi.testclient import TestClient
from web import app as web

@pytest.fixture
def guarded_web(monkeypatch):
    from easel import creation
    from easel.creator_proposal import parse_video_plan
    from easel.integrations.result_protocols import current
    from hashlib import sha256
    from json import dumps
    creation_id = "cr_" + "a" * 32
    attempt_id = "fa_" + "b" * 32
    proposal = parse_video_plan(_u2_proposal_source('silent'))
    assert proposal is not None
    consent = creation.input_use_preview(plan=proposal)
    transcript = dumps([{"role": "assistant", "content": _u2_proposal_source('silent')}],
                       ensure_ascii=False, separators=(',', ':'))
    proposal_sha = sha256(transcript.encode()).hexdigest()
    work = {
        "id": creation_id, "route": "hypit_video", "profile": None,
        "origin": {"type": "chat", "session_hash": "c" * 64},
        "creative_mode": "clear_memo_video", "creative_mode_version": "1.0",
        "chat_workflow": {
            "video_plan_required": True, "proposal_status": "CONFIRMED",
            "confirmed_at": "2026-10-11T08:00:00+00:00",
            "confirmed_by_turn": "test-explicit-confirm",
            "proposal_sha256": proposal_sha,
            "production_specs": proposal["specs"], "video_plan": proposal,
        },
        "delivery": {
            "schema": "easel-creation-delivery@1", "video_plan": proposal,
            "proposal": transcript, "proposal_sha256": proposal_sha,
            "confirmed_at": "2026-10-11T08:00:00+00:00",
            "confirmed_by_turn": "test-explicit-confirm",
            "authorization": {"input_use": {
                **consent, "creation_id": creation_id, "proposal_sha256": proposal_sha,
                "confirmed_at": "2026-10-11T08:00:00+00:00",
                "confirmed_by_turn": "test-explicit-confirm",
            }},
            "production_contract": {
                "schema": "easel-new-video-commission@1",
                "creation_id": creation_id, "session_hash": "c" * 64,
                "creator_profile": None, "creative_mode": "clear_memo_video",
                "creative_mode_version": "1.0",
                "video_plan_sha256": proposal["sha256"],
                "input_use_sha256": consent["statement_sha256"],
                "confirmed_at": "2026-10-11T08:00:00+00:00",
            },
        },
    }
    attempt = {"attempt_id": attempt_id, "creation_id": creation_id,
               "result_protocols": current()}
    work["hypit_attempts"] = [attempt]
    monkeypatch.setattr(web, "get_creation", lambda _: work)
    monkeypatch.setattr(web, "get_film_attempt", lambda _: attempt)
    monkeypatch.setattr(web, "_hypit_runtime_profile", lambda: "/fixture/runtime.json")
    monkeypatch.setattr(web, "execution_lock", lambda _: nullcontext(True))
    web.app.dependency_overrides[web.require_local_operator] = lambda: None
    try:
        yield TestClient(web.app), creation_id, attempt_id, work, attempt
    finally:
        web.app.dependency_overrides.pop(web.require_local_operator, None)

@pytest.mark.parametrize("suffix", [
    "/runtime/resolve", "/validate", "/estimate", "/build", "/refresh",
    "/retry-failed-build", "/reconcile", "/export", "/author",
    "/material-generation/minimax", "/material-generation/minimax-video",
    "/materials/recover",
])
def test_direct_film_production_posts_are_physically_unregistered(suffix):
    route = "/api/film-attempts/{attempt_id}" + suffix
    assert not any(
        item.path == route and "POST" in getattr(item, "methods", set())
        for item in web.app.routes
    ), route


def test_newonly_creator_material_clue_cannot_dispatch_retired_recovery_api():
    """The Creator UI may discuss supplied clues; only Delivery owns recovery."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / 'web/frontend/src'
    page = (root / 'components/FilmOperatorPage.tsx').read_text(encoding='utf-8')
    api = (root / 'lib/api.ts').read_text(encoding='utf-8')
    assert 'recoverFilmMaterials' not in page + api
    assert '/materials/recover' not in page + api
    assert 'easel-material-recovery-' not in page
    assert 'allowLicensedBgm: true' not in page
    assert '讨论素材线索' in page and 'onClick={onOpenConversation}' in page
    # A silent HTTP 404 or a React button hidden by a flag is not retirement.
    assert not any(
        item.path == '/api/film-attempts/{attempt_id}/materials/recover'
        and 'POST' in getattr(item, 'methods', set())
        for item in web.app.routes)


@pytest.mark.parametrize("path,method", [
    ("/api/creations/{creation_id}/handoff", "POST"),
    ("/api/creations/{creation_id}/film-attempts", "POST"),
    ("/api/creations/{creation_id}/stage/{stage}", "PATCH"),
])
def test_retired_creation_stage_routes_are_physically_unregistered(path, method):
    assert not any(
        item.path == path and method in getattr(item, "methods", set())
        for item in web.app.routes
    ), path


@pytest.mark.parametrize("name", ["auto-short-video", "video-production", "short-drama"])
def test_retired_video_producer_skills_are_unavailable(monkeypatch, name):
    from easel.commands import skill as cli_skill
    monkeypatch.setattr(web, "run_agent_sync", lambda *_args, **_kw: pytest.fail(
        "retired video producer must never invoke the agent"))
    assert web.find_skill(name) is None
    assert cli_skill._find_skill(name) is None
    assert name not in {item["name"] for item in web.get_skills()}
    client = TestClient(web.app)
    assert client.get(f"/api/skill/{name}").status_code == 404
    assert client.post("/api/skill", json={"skill": name, "input": "retired"}).status_code == 404


def test_unrelated_nonvideo_skill_remains_discoverable():
    assert web.find_skill("copywriting") is not None


def test_historical_attempt_is_readable_but_not_upgraded(guarded_web):
    client, _, attempt_id, work, attempt = guarded_web
    work["delivery"] = {}
    work["origin"] = {"type": "legacy"}
    attempt["result_protocols"] = {"schema": "agent-result-protocols@1", "profiles": {}}
    reply = client.get(f"/api/film-attempts/{attempt_id}")
    assert reply.status_code == 200
    assert reply.json()["result_protocols"]["profiles"] == {}
    assert attempt["result_protocols"]["profiles"] == {}


@pytest.mark.parametrize('invalid', [None, 'proposal', 'pins', 'consent'])
def test_creation_projection_controls_actual_frontend_delivery_gate(guarded_web, invalid):
    """Full server admission reaches the real TS gate; old schema cannot grant it."""
    import copy
    import json
    import subprocess
    from pathlib import Path
    client, creation_id, _, work, attempt = guarded_web
    if invalid == 'proposal':
        work['chat_workflow']['video_plan']['schema'] = 'easel-video-proposal@2'
    elif invalid == 'pins':
        attempt['result_protocols']['profiles'] = {}
    elif invalid == 'consent':
        work['delivery']['authorization']['input_use'] = {}
    before = copy.deepcopy(work)
    reply = client.get(f'/api/creations/{creation_id}')
    assert reply.status_code == 200
    assert reply.json()['delivery']['schema'] == 'easel-creation-delivery@1'
    assert reply.json()['operator_admission']['production_managed'] is (invalid is None)
    assert work == before
    program = r'''
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const snapshot = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = ts.createSourceFile('FilmOperatorPage.tsx', fs.readFileSync('src/components/FilmOperatorPage.tsx', 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
let gate;
function visit(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(source) === 'backendDelivery') gate = node.initializer;
  ts.forEachChild(node, visit);
}
visit(source);
assert.ok(gate);
const js = ts.transpileModule('const admitted = ' + gate.getText(source), {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
const admitted = vm.runInNewContext(js + ';admitted', {creationSnapshot: snapshot, record: value => value || {}});
assert.equal(admitted, snapshot.operator_admission.production_managed);
delete snapshot.operator_admission;
assert.equal(vm.runInNewContext(js + ';admitted', {creationSnapshot: snapshot, record: value => value || {}}), false);
const workspace = ts.createSourceFile('creatorWorkspace.ts', fs.readFileSync('src/lib/creatorWorkspace.ts', 'utf8'), ts.ScriptTarget.Latest, true);
const projection = workspace.statements.find(node => ts.isFunctionDeclaration(node) && node.name.text === 'projectCreatorWorkspace');
let managed;
function findManaged(node) {
  if (ts.isVariableDeclaration(node) && node.name.getText(workspace) === 'managed') managed = node.initializer;
  ts.forEachChild(node, findManaged);
}
findManaged(projection);
const projectionJs = ts.transpileModule('const managed = ' + managed.getText(workspace), {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
snapshot.operator_admission = {production_managed: admitted};
assert.equal(vm.runInNewContext(projectionJs + ';managed', {work: snapshot, asRecord: value => value || {}}), admitted);
delete snapshot.operator_admission;
assert.equal(vm.runInNewContext(projectionJs + ';managed', {work: snapshot, asRecord: value => value || {}}), false);
'''
    result = subprocess.run(['node', '-e', program], input=json.dumps(reply.json()),
        text=True, capture_output=True, cwd=Path(__file__).resolve().parents[1] / 'web/frontend')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('saved_plan', ['old', 'missing'])
def test_historical_reopen_never_reads_old_planning_or_retries(guarded_web, monkeypatch, tmp_path, saved_plan):
    import copy
    from pathlib import Path
    from easel import creation
    client, creation_id, _, work, attempt = guarded_web
    work['chat_workflow']['video_plan']['schema'] = 'easel-video-proposal@2'
    if saved_plan == 'missing':
        work['chat_workflow']['video_plan'] = None
    work['delivery']['status'] = 'failed'
    attempt['workspace'] = {'path': str(tmp_path)}
    planning = tmp_path / 'planning'
    planning.mkdir()
    for name in ('TREATMENT.md', 'SCRIPT.md', 'SCENES.md'):
        (planning / name).write_text('历史规划原件', encoding='utf-8')
    original_read = Path.read_text
    def guarded_read(path, *args, **kwargs):
        if path.parent == planning:
            pytest.fail('historical Planning must not seed a new proposal')
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'read_text', guarded_read)
    before = copy.deepcopy(work)
    monkeypatch.setattr(creation, 'get_creation', lambda _: work)
    monkeypatch.setattr(creation, 'edit_creation', lambda _: nullcontext(work))
    monkeypatch.setattr(web, 'retry_delivery', lambda *_: pytest.fail('historical retry reached Owner'))
    assert client.post(f'/api/creations/{creation_id}/delivery/retry').status_code == 400
    assert client.post(f'/api/creations/{creation_id}/proposal/reopen').status_code == 409
    assert work == before

def test_managed_human_cost_approval_remains_available(guarded_web, monkeypatch):
    client, _, attempt_id, _, _ = guarded_web
    calls = []
    def cost_approval(attempt_id_arg, amount):
        calls.append((attempt_id_arg, amount))
        return {"approved": True}
    monkeypatch.setattr(web, "approve_film_cost", cost_approval)
    reply = client.post(f"/api/film-attempts/{attempt_id}/approve-cost",
                        json={"maxBudgetUsd": 0.0})
    assert reply.status_code == 200, reply.text
    assert calls == [(attempt_id, 0.0)]


def test_historical_truth_review_rejects_before_any_write(guarded_web):
    client, _, attempt_id, work, _ = guarded_web
    work["delivery"] = {}
    work["origin"] = {"type": "legacy"}
    reply = client.post(f"/api/film-attempts/{attempt_id}/script-truth/review",
                        json={"scriptSha256": "a" * 64, "truthPacketSha256": "b" * 64,
                              "confirmAllClaimsReviewed": True})
    assert reply.status_code == 410


def test_historical_chat_completion_does_not_dispatch_old_preparation(monkeypatch):
    async def forbidden(*_args, **_kwargs):
        pytest.fail("old Preparation must never be dispatched")
    monkeypatch.setattr(web, "prepare_creation_for_hypit", forbidden)
    work = {"id": "cr_" + "a" * 32, "delivery": {},
            "chat_workflow": {"video_plan_required": True}}
    reply = asyncio.run(web._finish_ai_film_turn(work, "generate", succeeded=True, response="legacy"))
    assert reply == ""
    reply = asyncio.run(web._resume_confirmed_preparation(work))
    assert "旧版 Preparation 已停用" in reply


def test_current_web_frontend_does_not_dispatch_old_stages():
    from pathlib import Path
    source = (Path(__file__).resolve().parents[1] / "web/frontend/src/components/FilmOperatorPage.tsx").read_text()
    for old in ("legacyDelivery", "startFilmAuthoring(", "submitFilmBuild(",
                "resolveFilmRuntime(", "generateMiniMaxMaterial(", "retryFailedFilmBuild(",
                "validateFilmAttempt(", "exportFilmOutput(", "reconcileFilmBuild("):
        assert old not in source, old
    backend = (Path(__file__).resolve().parents[1] / "web/app.py").read_text()
    assert "def _start_film_authoring(" not in backend
    assert "async def _run_film_authoring(" in backend  # The live Delivery-owned executor.

def test_output_delete_preserves_historical_and_registered_media(tmp_path, monkeypatch):
    """Only an isolated ordinary upload may be removed via the generic DELETE."""
    import json
    root = tmp_path / "outputs"
    root.mkdir()
    monkeypatch.setattr(web, "OUTPUTS_DIR", root)

    creation = root / "_creations" / ("cr_" + "a" * 32)
    creation.mkdir(parents=True)
    original = creation / "receipt.json"
    original.write_bytes(b"original-model-receipt")

    selected = root / ("creation-cr_" + "b" * 32 + "-123456789abc")
    selected.mkdir()
    movie = selected / "final.mp4"
    movie.write_bytes(b"selected-mp4")

    registered = root / "custom-library-name"
    registered.mkdir()
    registered_media = registered / "final.mp4"
    registered_media.write_bytes(b"registered-mp4")
    (registered / ".easel.json").write_text(
        json.dumps({"schema": "easel-content-asset@1"}), encoding="utf-8")

    corrupt = root / "corrupt-library-name"
    corrupt.mkdir()
    (corrupt / ".easel.json").write_text("{bad-json", encoding="utf-8")

    shortcut = root / "original-link"
    shortcut.symlink_to(creation, target_is_directory=True)

    upload = root / "unregistered-upload"
    upload.mkdir()
    free_file = upload / "note.txt"
    free_file.write_text("ordinary upload", encoding="utf-8")

    client = TestClient(web.app)
    for relative in (
        "_creations",
        f"_creations/{creation.name}/receipt.json",
        selected.name,
        f"{selected.name}/final.mp4",
        registered.name,
        "custom-library-name/final.mp4",
        corrupt.name,
        "original-link",
    ):
        result = client.delete(f"/api/output/{relative}")
        assert result.status_code == 403, (relative, result.text)

    assert original.read_bytes() == b"original-model-receipt"
    assert movie.read_bytes() == b"selected-mp4"
    assert registered_media.read_bytes() == b"registered-mp4"
    assert client.delete("/api/output/unregistered-upload/note.txt").status_code == 200
    assert not free_file.exists()

def test_old_static_video_pages_cannot_serve(monkeypatch, tmp_path):
    """React is the only Web entrypoint; a missing build fails closed."""
    from pathlib import Path
    client = TestClient(web.app)
    for retired in ("/onepage", "/static/index.html", "/static/onepage.html",
                    "/static/main.html"):
        assert client.get(retired).status_code == 404, retired
    monkeypatch.setattr(web, "REACT_DIR", tmp_path / "not-built")
    response = client.get("/")
    assert response.status_code == 503
    assert "尚未构建" in response.text

def _u2_proposal_source(mode: str, seconds: int = 45) -> str:
    from easel.integrations.voice_identity import HANDLE
    sound = {
        'silent': '全片静音，不添加声音。',
        'music': '只使用有明确 Rights 的背景音乐。',
        'voice': '预置旁白：' + HANDLE,
        'mixed': '预置旁白：' + HANDLE + '\n旁白与背景音乐要同时保留。',
    }[mode]
    label = {'silent': '静音', 'music': '纯音乐',
             'voice': '纯旁白', 'mixed': '旁白与音乐'}[mode]
    fence = chr(96) * 3
    return ('## 创作表达\n克制的导演表达。\n'
            '## 文案\n' + fence + 'text\n确认的一句正文。\n' + fence + '\n'
            '## 分镜与节奏\n围绕正文分镜。\n'
            '## 声音设计\n' + sound + '\n'
            '## 制作规格\n时长：' + str(seconds)
            + ' 秒\n画幅：9:16\n音轨：' + label + '\n语言：简体中文\n')


@pytest.mark.parametrize('mode', ['silent', 'music', 'voice', 'mixed'])
def test_u2_single_proposal_at4_four_sound_modes_and_consent(mode):
    from easel.creator_proposal import parse_video_plan, validate_video_plan
    from easel.creation import input_use_preview
    from easel.integrations.voice_identity import verified_profile, derived_catalog
    offer = verified_profile() if mode in {'voice', 'mixed'} else None
    plan = parse_video_plan(_u2_proposal_source(mode), voice_profile=offer)
    assert plan is not None and plan['schema'] == 'easel-video-proposal@4'
    assert validate_video_plan(plan)
    assert plan['specs']['audio_mode'] == mode
    declaration = input_use_preview(plan=plan)
    assert declaration['schema'] == 'easel-input-use@3'
    assert declaration['video_plan_sha256'] == plan['sha256']
    assert declaration['audio_mode'] == mode
    assert ('preset_voice_synthesis' in declaration['operations']) == (
        mode in {'voice', 'mixed'})
    assert ('voice_profile_sha256' in declaration) == (mode in {'voice', 'mixed'})
    derived = derived_catalog(plan, plan['script'])
    if mode in {'silent', 'music'}:
        assert derived is None  # No implicit voice or TTS right.
        assert 'voice_profile' not in plan and 'sound_source' not in plan
    else:
        assert derived['profile'] == offer
        assert derived['plan_sha256'] == plan['sha256']
    with pytest.raises(ValueError, match='SCRIPT'):
        derived_catalog(plan, plan['script'] + 'tampered')


@pytest.mark.parametrize('invalid_seconds', [0, 901, 999])
def test_u2_at4_duration_out_of_bounds_not_confirmable(invalid_seconds):
    from easel.creator_proposal import parse_video_plan, validate_video_plan
    draft = parse_video_plan(_u2_proposal_source('silent', invalid_seconds))
    assert draft is not None
    assert not validate_video_plan(draft)


@pytest.mark.parametrize('prefix', ['', '- ', '* ', '+ '])
def test_at4_voice_list_decoration_preserves_source_and_digest(prefix):
    from easel.creator_proposal import parse_video_plan, validate_video_plan
    from easel.integrations.voice_identity import HANDLE, verified_profile, render_sound
    source = _u2_proposal_source('mixed').replace('预置旁白：', prefix + '预置旁白：')
    plan = parse_video_plan(source, voice_profile=verified_profile())
    assert plan is not None and validate_video_plan(plan)
    original_sound = prefix + '预置旁白：' + HANDLE + '\n旁白与背景音乐要同时保留。'
    assert plan['sound_source'] == original_sound
    assert plan['sound'] == render_sound(original_sound, verified_profile())
    assert plan['script'] == '确认的一句正文。'
    # Presentation bytes still participate in the digest; they are not erased.
    changed = {**plan, 'sound_source': original_sound + '\n其他说明。'}
    changed['sound'] = render_sound(changed['sound_source'], verified_profile())
    assert not validate_video_plan(changed)


@pytest.mark.parametrize('declarations', [
    '', '- 预置旁白：unknown', '- 预置旁白：preset-cmn-youth（说明）',
    '- 预置旁白：preset-cmn-youth # 说明', '  - 预置旁白：preset-cmn-youth',
    '- - 预置旁白：preset-cmn-youth', '1. 预置旁白：preset-cmn-youth',
    '预置旁白：preset-cmn-youth\n- 预置旁白：preset-cmn-youth',
    '预置旁白：preset-cmn-youth\n- 预置旁白：unknown',
    '预置旁白：preset-cmn-youth\n**预置旁白**：unknown',
    '预置旁白：preset-cmn-youth\n> 预置旁白：preset-cmn-youth（说明）',
    '预置旁白：preset-cmn-youth\n- 预置旁白:unknown',
])
def test_at4_voice_ambiguous_declarations_rejected_by_parser_and_validator(declarations):
    import hashlib, json
    from easel.creator_proposal import parse_video_plan, validate_video_plan, _plan_payload
    from easel.integrations.voice_identity import verified_profile, render_sound
    source = _u2_proposal_source('voice')
    candidate = source.replace('预置旁白：preset-cmn-youth', declarations)
    assert parse_video_plan(candidate, voice_profile=verified_profile()) is None
    plan = parse_video_plan(source, voice_profile=verified_profile())
    # A correctly rehashed object must not bypass the parser's declaration rules.
    plan['sound_source'] = declarations or '没有旁白声明。'
    plan['sound'] = render_sound(plan['sound_source'], verified_profile())
    plan['sha256'] = hashlib.sha256(json.dumps(_plan_payload(plan), ensure_ascii=False,
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    assert not validate_video_plan(plan)


def test_at4_captured_voice_list_turn_saves_without_production(tmp_path, monkeypatch):
    """Replay a completed real reply through the existing Web/Creation Owner.

    This generic scene contains no personal claims or credentials. No model,
    Worker, Provider or production confirmation is dispatched by this replay.
    """
    import hashlib, json
    from fastapi import HTTPException
    from easel import creation
    from easel.chat_capability import bind_chat_creation, get_chat_creation
    from easel.creator_proposal import validate_video_plan
    from easel.creation_delivery import is_managed
    from easel.integrations.voice_identity import verified_profile, derived_catalog
    monkeypatch.setattr(creation, 'CREATIONS_DIR', tmp_path / '_creations')
    monkeypatch.setattr(creation, 'OUTPUTS_DIR', tmp_path)
    monkeypatch.setattr(web, 'run_agent_sync', lambda *a, **kw: pytest.fail('No model request'))
    monkeypatch.setattr(web, '_execute_creation_delivery', lambda *a, **kw: pytest.fail('No production'))
    response = '''## 创作表达

**Content Core**
- 核心议题：把收桌面当成一天结束的"合页"，而不是另一项待办
- 内容分类：场景里说的事实 = 普通生活观察；不引用数据、不宣称功效
- 一句话张力：我们常把"忙完"等同于"再撑一下"，但真正的停顿来自一个具体的小动作

**Director Treatment**
- 观众情绪路径：平视 → 微顿 → 放下
- 第一个具体画面：一杯还冒着热气的水、旁边是合了一半的笔记本
- "识别瞬间"：当旁白说出"把这一天的边角合上"时
- 收尾：不喊口号，让画面停在关掉的台灯和安静桌面，留两秒白噪声般的留白

## 文案

```text
忙完不是再加一件事，
是把这一天的边角合上。
水杯归位，笔放回原处，
笔记本合起来。
灯可以先关，
让桌面替你说，已经停一下了。
```

## 分镜与节奏

总时长 45 秒；9:16 竖屏；7 个镜头，连续不重叠。

| # | 时长 | 画面 | 对应文案 | 节奏说明 |
|---|---|---|---|---|
| 1 | 0.0–5.5s | 俯拍一张半乱的桌面：杯垫、水杯、散落的笔、翻开的笔记本一角。浅景深，光是傍晚的窗光。 | 忙完不是再加一件事， | 静态长镜头，慢慢轻微推近，旁白先起 |
| 2 | 5.5–11.0s | 平视侧拍：一只手把水杯挪回杯垫，轻放。声音：杯底接触桌面的"嗒"。 | 是把这一天的边角合上。 | 动作跟"合上"一词同步 |
| 3 | 11.0–17.5s | 俯拍特写：手指把一支笔滚回笔筒或笔搁。 | 水杯归位，笔放回原处， | 节奏由旁白带，画面只做一个动作 |
| 4 | 17.5–24.0s | 侧面中景：双手合上笔记本盖子，轻轻"啪"一声。 | 笔记本合起来。 | 盖子合上的声音点对"合起来" |
| 5 | 24.0–32.0s | 中景：手伸向台灯开关，按下。画面亮度自然降下来，桌面的高光收缩。 | 灯可以先关， | 压暗过程约 2 秒，配合"先"字 |
| 6 | 32.0–40.0s | 静帧中景：空桌面、台灯灭后的轮廓、窗光更明显。镜头几乎不动。 | 让桌面替你说，已经停一下了。 | 长留白，让句子在画面里走完 |
| 7 | 40.0–45.0s | 缓推：只剩桌面边缘与窗外一片安静的天色。 | （无旁白） | 完全留白，BGM 渐弱但不切断 |

字幕规格：每行 ≤ 12 个汉字，9:16 安全区居中偏下，字号统一，黑白两色按背景切换；不出现 emoji、表情、动效字。

## 声音设计

- 预置旁白：preset-cmn-youth
- 音色说明：青涩青年音色 / 中文普通话；旁白气质平静、像自己跟自己说，不上扬不拖腔；语速中等，每句之间留半拍
- 旁白执行参数：pace_ratio 0.95（比默认略慢一档，给"停顿"留余地）、pitch_semitones 0、tone neutral
- 段落标点对应节奏：逗号 = 0.3s 气口，句号 = 0.6s 停顿；分镜 6 末尾的句号后留 2.0s
- BGM：无歌词、轻柔 pad 为主，可加极少量木吉他拨弦；不抢人声，旁白时自动压低（音乐闪避）
- SFX：仅 3 处点状出现——分镜 2 杯底触桌的轻"嗒"、分镜 4 笔记本合盖的"啪"、分镜 5 台灯开关的"咔"；其余时段无 SFX
- 留白：分镜 7 整段无旁白，仅 BGM 渐弱收尾
- 音轨组成与本版"旁白与音乐"规格一致：旁白全程存在，BGM 全程不省略并在末镜自然渐弱

## 制作规格

时长：45 秒
画幅：9:16
音轨：旁白与音乐
语言：简体中文

**规格说明**
- 沿用用户硬要求：时长 45 秒、9:16 1080×1920、简体中文、普通话预置旁白 + 轻柔无歌词 BGM 且 BGM 不省略、笔记本屏幕不出现可读内容/品牌/通知/个人信息、写通用场景不写亲历、不宣称功效、预置旁白 preset-cmn-youth 不替换
- Easel 推荐（仅作本草案的创作取舍，不是用户已确认的事实）：7 镜结构、首镜俯拍半乱桌面到末镜空桌面收尾、旁白语速比默认略慢、中性偏暖光、台灯关掉作为"停顿"的可视化锚点、SFX 仅放在与具体动作对齐的三处、字幕单行 ≤ 12 字
- 镜头数、措辞、节奏属于制作层常规取舍，已在分镜表里写明推荐值，可逐项调整
- 素材来源与 Rights：待核验——画面需确认是图库授权素材 / 现场实拍 / AI 生成；普通图库不承诺同一只手、同一张桌子或精确连续动作，制作时若无可用授权镜头，允许按本草案"桌面物件归位"的核心动作做等效替换，并在替换记录中注明差异
- 旁白版权：使用预置旁白 preset-cmn-youth，不做声音克隆、不另选音色
- 文案字数：约 64 个汉字（含标点），分 6 个语义行，对应分镜 1–6；分镜 7 无旁白

等你看完作品卡片，告诉我按这个版本推进，或者哪里要改。'''
    assert hashlib.sha256(response.encode()).hexdigest() == '758769888c8d952859ef6125aa30f3824629e0c2af8141bb17da8183b52435c9'
    session, turn = 'captured-current-proposal', 'completed-proposal-turn'
    work = bind_chat_creation(session, turn, '收好桌面', profile=None,
        creative_mode='clear_memo_video', capability='ai-film')
    cid = work['id']
    work = creation.begin_video_proposal(cid, turn, preset_contract=True,
        voice_profile_offer=verified_profile())
    assert asyncio.run(web._finish_ai_film_turn(work, 'proposal', succeeded=True,
        response=response)) == ''
    saved = creation.get_creation(cid)
    workflow = saved['chat_workflow']; plan = workflow['video_plan']
    assert workflow['proposal_status'] == 'READY_FOR_CONFIRMATION'
    assert workflow['proposal_turn_id'] == turn and not workflow.get('confirmed_at')
    assert workflow['output_decision']['outcome'] == 'ACCEPT'
    assert workflow['output_decision']['input_sha256'] == hashlib.sha256(response.encode()).hexdigest()
    assert validate_video_plan(plan) and plan['revision'] == 1
    assert plan['sound_source'] == response.split('## 声音设计')[1].split('## 制作规格')[0].strip()
    assert plan['script'] == response.split('```text\n')[1].split('\n```')[0]
    assert derived_catalog(plan, plan['script'])['sound_source_sha256'] == hashlib.sha256(plan['sound_source'].encode()).hexdigest()
    context = [{'role': 'assistant', 'content': response}]
    client = TestClient(web.app)
    projected = client.post(f'/api/creations/{cid}/proposal-preview',
        json={'proposalContext': context})
    assert projected.status_code == 200
    preview = projected.json()
    assert preview['confirmable'] and not preview['missing']
    assert preview['video_plan'] == plan
    # A stale turn cannot replace the valid plan, even with a valid new response.
    stale = creation.save_video_proposal(cid, 'stale-turn', response.replace('忙完不是', '忙完并非'))
    assert stale['chat_workflow'] == workflow
    for changes in ({'videoPlanSha256': '0' * 64},
                    {'inputUseStatementSha256': '0' * 64}):
        request = dict(message='', sessionId=session, turnId='rejected-confirm',
            capability='ai-film', creationAction='confirm_production',
            proposalContext=context, videoPlanSha256=plan['sha256'],
            inputUseStatementSha256=preview['input_use']['statement_sha256'])
        request.update(changes)
        with pytest.raises(HTTPException) as caught:
            web._prepare_chat_request(web.ChatRequest(**request))
        assert caught.value.status_code == 409
        rejected = creation.get_creation(cid)
        assert not is_managed(rejected) and not rejected.get('delivery')
        assert not rejected.get('hypit_attempts')
        assert rejected['chat_workflow'] == workflow
    # Identical replay preserves the revision; it never creates a second work.
    replayed = creation.save_video_proposal(cid, turn, response)
    assert replayed['chat_workflow']['video_plan']['sha256'] == plan['sha256']
    assert replayed['chat_workflow']['video_plan']['revision'] == 1
    assert get_chat_creation(session)['id'] == cid
    assert len(list(creation.CREATIONS_DIR.glob('cr_*/creation.json'))) == 1
    assert not replayed.get('delivery') and not replayed.get('hypit_attempts')
    assert replayed['preparation']['status'] == 'CREATED'


def test_u2_at4_rejects_old_schema_bool_extra_voice_and_tampered_sha():
    from easel.creator_proposal import parse_video_plan, validate_video_plan
    plan = parse_video_plan(_u2_proposal_source('silent'))
    assert plan is not None and validate_video_plan(plan)
    for candidate in (
        {**plan, 'schema': 'easel-video-proposal@3'},
        {**plan, 'schema': 'easel-video-proposal@2'},
        {**plan, 'specs': {**plan['specs'], 'duration_seconds': True}},
        {**plan, 'specs': {**plan['specs'], 'audio_mode': 'voice'}},
        {**plan, 'voice_profile': {'fake': True}},
        {**plan, 'sha256': '0' * 64},
        {**plan, 'extra_source': 'not admitted'},
    ):
        assert not validate_video_plan(candidate)
    assert parse_video_plan(_u2_proposal_source('voice')) is None


@pytest.mark.parametrize('duration', [300, 301, 900])
def test_u2_unverified_long_video_confirmable_but_no_new_dispatch(tmp_path, monkeypatch, duration):
    """@4 may confirm 900s; unverified 301+ cannot buy Preparation or Build."""
    import hashlib, json
    from easel import creation, creation_preparation
    from easel.creation_delivery import next_operation, is_managed, advance_creation
    monkeypatch.setattr(creation, 'CREATIONS_DIR', tmp_path/'_creations')
    monkeypatch.setattr(creation, 'OUTPUTS_DIR', tmp_path)
    work=creation.create_creation('R4 limited execution',route='hypit_video',
        creative_mode='clear_memo_video',origin={'type':'chat','session_hash':'a'*64})
    cid=work['id']; turn='long-v1'
    creation.begin_video_proposal(cid, turn)
    draft=_u2_proposal_source('silent',duration)
    plan=creation.save_video_proposal(cid,turn,draft)['chat_workflow']['video_plan']
    from easel.creator_proposal import validate_video_plan
    assert validate_video_plan(plan) and plan['specs']['duration_seconds']==duration
    consent=creation.input_use_preview(plan=plan)
    transcript=json.dumps([{'role':'assistant','content':draft}],ensure_ascii=False,separators=(',',':'))
    work=creation.confirm_chat_proposal(cid,turn,delivery_proposal=transcript,
        proposal_sha256=hashlib.sha256(transcript.encode()).hexdigest(),
        video_plan_sha256=plan['sha256'],production_specs=plan['specs'],
        input_use_statement_sha256=consent['statement_sha256'])
    assert is_managed(work)
    if duration==300:
        assert next_operation(work)==('prepare','preparing')
        return
    original=creation.get_creation(cid)
    assert next_operation(work)==(None,'long_video_qualification_required')
    async def forbidden(*_):
        pytest.fail('unqualified long film dispatched paid or Planning work')
    assert asyncio.run(advance_creation(cid,forbidden)) is False
    with pytest.raises(creation_preparation.PreparationError,match='U3-L|长片.*资格'):
        creation_preparation.prepare_creation_for_hypit(cid,runtime_profile=None)
    blocked=creation.get_creation(cid)
    assert blocked['delivery']['status']=='long_video_qualification_required'
    assert blocked['delivery']['video_plan']==original['delivery']['video_plan']
    assert blocked['delivery']['authorization']==original['delivery']['authorization']
    assert blocked['delivery']['production_contract']==original['delivery']['production_contract']
    assert blocked['chat_workflow']==original['chat_workflow']
    assert blocked['preparation']==original['preparation']
    assert blocked.get('hypit_attempts')==original.get('hypit_attempts')
    assert not blocked.get('hypit_attempts')
    assert not blocked['delivery'].get('agent_calls')
    assert not blocked['delivery'].get('material_generations')
    with creation.edit_creation(cid) as pending:
        pending['delivery']['agent_calls']={'original-id':{
            'status':'pending','runtime_release':'pending','operation_id':'original'}}
    assert next_operation(creation.get_creation(cid))==('observe_agent','observing_execution')
    # Direct internal Pricing / Cost Approval / Build / Final Admission are not
    # alternative long-video dispatchers. The immutable confirmed commission
    # still wins if a mutable Attempt Handoff loses its long duration.
    from easel.integrations.hypit import service
    from easel.integrations.hypit.errors import HypitIntegrationError
    from easel.integrations import result_protocols
    fake_attempt={'creation_id':cid,'attempt_id':'fa_'+'b'*32,
        'result_protocols':result_protocols.current(),
        'production_request':{'video_plan':plan}}
    monkeypatch.setattr(service,'get_film_attempt',lambda *_:fake_attempt)
    monkeypatch.setattr(service,'_cli',
        lambda *_a,**_k: pytest.fail('No Hypit CLI before U3-L real qualification'))
    for request in (
        {'video_plan':plan},
        {'video_plan':{**plan,'specs':{**plan['specs'],'duration_seconds':15}}},
        {},
    ):
        fake_attempt['production_request']=request
        for action in (
            lambda:service.estimate_film_attempt(fake_attempt['attempt_id']),
            lambda:service.approve_film_cost(fake_attempt['attempt_id'],0),
            lambda:service.submit_film_build(fake_attempt['attempt_id'],title='blocked'),
            lambda:service.require_final_admission(fake_attempt,'final.mp4'),
        ):
            with pytest.raises(HypitIntegrationError,match='U3-L|长片.*资格'):
                action()


def test_u2_current_commission_pre_and_post_attempt_admission(tmp_path, monkeypatch):
    import hashlib
    import json
    from easel import creation
    from easel.creation_delivery import is_managed, next_operation
    from easel.integrations import result_protocols
    from easel.creator_proposal import validate_video_plan
    monkeypatch.setattr(creation, 'CREATIONS_DIR', tmp_path / '_creations')
    monkeypatch.setattr(creation, 'OUTPUTS_DIR', tmp_path)
    work = creation.create_creation('safe new creation', route='hypit_video',
        creative_mode='clear_memo_video', origin={'type':'chat','session_hash':'a'*64})
    cid = work['id']
    creation.begin_video_proposal(cid, 'turn1')
    draft = _u2_proposal_source('silent')
    saved = creation.save_video_proposal(cid, 'turn1', draft)
    plan = saved['chat_workflow']['video_plan']
    assert validate_video_plan(plan)
    consent = creation.input_use_preview(plan=plan)
    transcript = json.dumps([{'role':'assistant','content':draft}],
                            ensure_ascii=False, separators=(',', ':'))
    args = {'proposal_sha256': hashlib.sha256(transcript.encode()).hexdigest(),
            'delivery_proposal': transcript, 'production_specs': plan['specs'],
            'video_plan_sha256': plan['sha256']}
    with pytest.raises(creation.CreationError, match='文字使用声明'):
        creation.confirm_chat_proposal(cid, 'turn1', **args)
    confirmed = creation.confirm_chat_proposal(
        cid, 'turn1', input_use_statement_sha256=consent['statement_sha256'], **args)
    assert is_managed(confirmed)
    assert next_operation(confirmed) == ('prepare', 'preparing')
    old = {**confirmed, 'delivery': {**confirmed['delivery']}}
    old['delivery'].pop('production_contract')
    assert not is_managed(old)
    old = {**confirmed, 'delivery': {**confirmed['delivery'],
        'video_plan': {**plan, 'schema':'easel-video-proposal@3'}}}
    assert not is_managed(old)
    current_attempt = {'creation_id':cid,'attempt_id':'fa_'+'c'*32,
                       'attempt_number':1,'result_protocols':result_protocols.current()}
    with creation.edit_creation(cid) as store:
        store['hypit_attempts'] = [current_attempt]
    assert is_managed(creation.get_creation(cid))
    with creation.edit_creation(cid) as store:
        store['hypit_attempts'][0]['result_protocols']['profiles'] = {}
    assert not is_managed(creation.get_creation(cid))

def test_u2_server_actions_are_read_only_and_quality_bound(guarded_web, monkeypatch):
    """The GET projection never grants historical review or bypasses Final Admission."""
    from copy import deepcopy
    from easel.integrations.hypit import service
    from easel.integrations.hypit.quality import SCHEMA
    client, _, attempt_id, work, attempt = guarded_web
    response = client.get(f"/api/film-attempts/{attempt_id}")
    assert response.status_code == 200
    initial = response.json()["operator_admission"]
    assert initial["allowed_actions"]["approve_final"] is False
    assert initial["allowed_actions"]["select_film"] is False

    digest = "sha256:" + "1" * 64
    attempt["outputs"] = {"final": {"sha256": digest, "path": "fixture.mp4"}}
    attempt["review"] = {"system": {"schema": SCHEMA, "status": "READY",
                                     "binding": {"output_name": "final",
                                                 "sha256": digest}},
                         "human": {"status": "pending"}}
    original = deepcopy(attempt)
    response = client.get(f"/api/film-attempts/{attempt_id}")
    assert response.status_code == 200
    assert response.json()["operator_admission"]["allowed_actions"]["approve_final"] is False
    assert attempt == original
    # Isolate the HTTP projection from its independently tested domain gate.
    monkeypatch.setattr(service, "require_final_admission",
                        lambda current, name: current["outputs"][name])
    admitted = client.get(f"/api/film-attempts/{attempt_id}").json()["operator_admission"]
    assert admitted["allowed_actions"]["approve_final"] is True
    assert admitted["allowed_actions"]["select_film"] is False
    assert admitted["current_output_sha256"] == digest
    attempt["review"].update({
        "binding": {"output_name": "final", "sha256": digest},
        "human": {"status": "approved"},
        "truth": {"status": "pass"}, "style": {"status": "pass"},
        "technical": {"status": "pass"},
    })
    attempt["review_status"] = "APPROVED"
    admitted = client.get(f"/api/film-attempts/{attempt_id}").json()["operator_admission"]
    assert admitted["allowed_actions"]["select_film"] is True
    work["origin"] = {"type": "legacy"}
    blocked = client.get(f"/api/film-attempts/{attempt_id}").json()["operator_admission"]
    assert blocked["allowed_actions"]["approve_final"] is False
    assert blocked["allowed_actions"]["select_film"] is False


def test_u2_human_approval_has_no_write_before_final_admission(
        guarded_web, monkeypatch, tmp_path):
    from easel import creation
    from easel.integrations.hypit import service
    from easel.integrations.hypit.errors import HypitIntegrationError
    _, _, attempt_id, work, attempt = guarded_web
    movie = tmp_path / "final.mp4"
    movie.write_bytes(b"isolated-current-output")
    sha = service._file_sha256(movie)
    attempt["outputs"] = {
        "final": {
            "path": "fixture/final.mp4", "sha256": sha,
            "technical_qc": {"status": "pass", "output_name": "final",
                              "sha256": sha},
        },
    }
    monkeypatch.setattr(service, "get_film_attempt", lambda _: attempt)
    monkeypatch.setattr(creation, "get_creation", lambda _: work)
    monkeypatch.setattr(service, "_output_path", lambda *_: movie)
    monkeypatch.setattr(service, "_save_attempt", lambda *_args, **_kwargs: pytest.fail(
        "rejected human approval must never write the Attempt"))
    human = {"output_name": "final", "sha256": sha,
             "truth": {"status": "pass", "notes": ["Fixture truth reviewed."]},
             "style": {"status": "pass", "notes": ["Fixture style reviewed."]},
             "human": {"status": "approved"}, "feedback": []}
    with pytest.raises(HypitIntegrationError, match="Material/Rights Readiness"):
        service.record_film_review(attempt_id, human)
    assert movie.read_bytes() == b"isolated-current-output"


@pytest.mark.parametrize('change', ['quality', 'historical'])
def test_review_rechecks_locked_owner_before_approval(guarded_web, monkeypatch, tmp_path, change):
    """A valid pre-lock read cannot authorize a changed Quality/commission."""
    from contextlib import contextmanager
    from copy import deepcopy
    from easel import creation
    from easel.integrations.hypit import service
    from easel.integrations.hypit.errors import HypitIntegrationError
    _, _, aid, work, attempt = guarded_web
    movie = tmp_path / 'final.mp4'
    movie.write_bytes(b'isolated-output')
    sha = service._file_sha256(movie)
    attempt['outputs'] = {'final': {'sha256': sha, 'technical_qc': {
        'status': 'pass', 'output_name': 'final', 'sha256': sha}}}
    attempt['review'] = {'system': {'status': 'READY'}}
    before = deepcopy(attempt)
    monkeypatch.setattr(service, 'get_film_attempt', lambda _: deepcopy(before))
    monkeypatch.setattr(creation, 'get_creation', lambda _: work)
    monkeypatch.setattr(service, '_output_path', lambda *_: movie)
    # Only the separately-covered expensive media gate is replaced; the actual
    # record_film_review read/lock/write path and signed commission are exercised.
    def admission(item, _name):
        if item.get('review', {}).get('system', {}).get('status') != 'READY':
            raise HypitIntegrationError('Quality no longer READY')
    monkeypatch.setattr(service, 'require_final_admission', admission)
    locked_snapshot = []
    @contextmanager
    def concurrent_change(_cid):
        if change == 'quality':
            attempt['review']['system']['status'] = 'NOT_READY'
        else:
            work['delivery'] = {}
        locked_snapshot.append(deepcopy(work))
        yield work
    monkeypatch.setattr(creation, 'edit_creation', concurrent_change)
    with pytest.raises(HypitIntegrationError, match='Quality|历史|委托'):
        service.record_film_review(aid, {'output_name': 'final', 'sha256': sha,
            'truth': {'status': 'pass', 'notes': ['fixture truth']},
            'style': {'status': 'pass', 'notes': ['fixture style']},
            'human': {'status': 'approved'}})
    assert work == locked_snapshot[0]


def test_selection_cleanup_is_read_only_without_reference_proof(guarded_web, monkeypatch):
    from easel import creation
    from easel.integrations.hypit import service
    from copy import deepcopy
    _, cid, aid, work, _ = guarded_web
    work.update(selected_attempt_id=aid, content_asset={'asset_id': 'fixture'})
    work['hypit_attempts'].append({'attempt_id': 'historical', 'cost': {'status': 'UNKNOWN'}})
    before = deepcopy(work)
    monkeypatch.setattr(creation, 'get_creation', lambda _: deepcopy(work))
    monkeypatch.setattr(creation, 'edit_creation', lambda _: pytest.fail('No cleanup write without proof'))
    assert service._cleanup_completed_materials(cid) == before
    assert work == before


@pytest.mark.parametrize('mode', ['silent', 'music', 'voice', 'mixed'])
def test_current_browser_restore_binds_backend_proposal_and_original_session(mode):
    """Execute the actual TS recovery function against Python-produced @4 bytes.

    No browser/server/Worker is started; fetch is a read-only fixture. TypeScript
    AST selects the production function rather than duplicating its logic.
    """
    import hashlib
    import json
    import subprocess
    from pathlib import Path
    from easel.creator_proposal import parse_video_plan
    from easel.integrations.voice_identity import verified_profile
    plan = parse_video_plan(_u2_proposal_source(mode), voice_profile=(
        verified_profile() if mode in {'voice', 'mixed'} else None))
    work = {'id': 'cr_' + 'a' * 32, 'route': 'hypit_video',
        'origin': {'type': 'chat', 'session_hash': hashlib.sha256(b'original-session').hexdigest()},
        'chat_workflow': {'proposal_status': 'READY_FOR_CONFIRMATION', 'video_plan': plan}}
    program = r'''
const ts = require('typescript');
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto').webcrypto;
const initial = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = ts.createSourceFile('App.tsx', fs.readFileSync('src/App.tsx', 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
const fn = source.statements.find(s => ts.isFunctionDeclaration(s) && s.name.text === 'restoreCreationConversation');
assert.ok(fn);
const js = ts.transpileModule(fn.getText(source), {compilerOptions: {target: ts.ScriptTarget.ES2022}}).outputText;
let work = structuredClone(initial); let reads = 0;
const restore = vm.runInNewContext(js + ';restoreCreationConversation', {
  crypto, TextEncoder, fetchCreation: async id => {reads++; assert.equal(id, initial.id); return work;}
});
(async () => {
  const restored = await restore(initial.id, 'original-session');
  assert.equal(restored.activeCreationId, initial.id);
  assert.equal(restored.activeCreationPhase, 'proposal_ready');
  assert.equal(reads, 1);
  assert.deepEqual(work, initial);
  await assert.rejects(restore(initial.id, 'foreign-session'));
  work.chat_workflow.video_plan.script += '篡改';
  await assert.rejects(restore(initial.id, 'original-session'));
  work = structuredClone(initial);
  work.chat_workflow.video_plan.schema = 'easel-video-proposal@3';
  await assert.rejects(restore(initial.id, 'original-session'));
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    result = subprocess.run(['node', '-e', program], input=json.dumps(work, ensure_ascii=False),
        text=True, capture_output=True, cwd=Path(__file__).resolve().parents[1] / 'web/frontend')
    assert result.returncode == 0, result.stderr
