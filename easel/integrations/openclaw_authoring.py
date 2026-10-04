"""Attempt-scoped, least-privilege OpenClaw Production Authoring turns."""

from __future__ import annotations

import json
import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Callable, Sequence


class OpenClawAuthoringBoundaryError(RuntimeError):
    """The isolated Authoring turn could not be safely provisioned or checked."""


_ATTEMPT_ID = re.compile(r"^fa_[0-9a-f]{32}$")
_PROMOTED_ARTIFACTS = (
    "productions/easel-authoring/material-selection.json",
    "productions/easel-authoring/authors/main.svml",
    "productions/easel-authoring/runs/main.svrun",
)
_OPTIONAL_PROMOTED_ARTIFACTS = (
    "productions/easel-authoring/authors/recipes.svs",
)
_INPUT_DIRS = ("handoff", "planning", "references", "productions/easel-authoring")
_INPUT_FILES = ("AUTHORING_TASK.md", "package.json", "materials/plan.json",
                "materials/bundle.json", "materials/readiness.json")

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _agent_result(runner: CommandRunner, cmd: Sequence[str], *, phase: str, **kwargs):
    """Retain a safe failure category, never raw model output or credentials."""
    try:
        from easel.integrations.openclaw_delivery import run_delivery_agent
        result = run_delivery_agent(cmd, runner=runner, **kwargs)
    except subprocess.TimeoutExpired as exc:
        raise OpenClawAuthoringBoundaryError(f"视频编排{phase}超时；已保留原内容和素材，可阶段重试") from exc
    if result.returncode != 0:
        detail = ((result.stderr or "") + (result.stdout or "")).lower()
        if any(word in detail for word in ("502", "503", "504", "bad gateway", "upstream_html", "html error page")):
            reason = "编排模型服务返回异常网关响应"
        elif any(word in detail for word in ("timed out", "timeout")):
            reason = "编排模型服务响应超时"
        elif any(word in detail for word in ("401", "unauthorized", "authentication")):
            reason = "编排模型服务认证失败"
        else:
            reason = "编排模型调用失败"
        raise OpenClawAuthoringBoundaryError(
            f"{reason}（{phase}，退出码 {result.returncode}）；已保留原内容和素材，未提交视频合成"
        )
    return result


def _delivery_stage(source: Path, parent: Path, attempt_id: str, message: str, profile: str):
    from easel import creation
    from easel.creation_delivery import active_delivery
    creation_id = active_delivery.get()
    if not creation_id:
        return None, None
    key = hashlib.sha256(f"{attempt_id}\0{message}".encode()).hexdigest()
    with creation.edit_creation(creation_id) as work:
        stages = work["delivery"].setdefault("authoring_stages", {})
        record = stages.get(key)
        if record is None:
            agent_id = f"easel-author-{attempt_id[-8:]}-{uuid.uuid4().hex[:12]}"
            stage_root = Path(tempfile.mkdtemp(prefix=f"{agent_id}-", dir=parent))
            instruction = stage_root / "instruction.txt"
            instruction.write_text(message, encoding="utf-8")
            instruction.chmod(0o600)
            record = {"attempt_id": attempt_id, "source": str(source), "profile": profile,
                      "stage_root": str(stage_root), "agent_id": agent_id, "inputs_ready": False}
            stages[key] = record
        root = Path(record["stage_root"])
        if (record["source"] != str(source) or record["profile"] != profile
                or root.is_symlink() or root.parent != parent or not root.is_dir()
                or not root.name.startswith(record["agent_id"] + "-")):
            raise OpenClawAuthoringBoundaryError("隔离编排恢复记录与当前作品不一致")
    return key, record


def retained_authoring_message(attempt_id: str, *, profile: str) -> str | None:
    """Resume the latest dispatched turn, even if error/status prompts changed."""
    from easel import creation
    from easel.creation_delivery import active_delivery
    creation_id = active_delivery.get()
    if not creation_id:
        return None
    stages = creation.get_creation(creation_id)["delivery"].get("authoring_stages", {})
    for key, record in reversed(list(stages.items())):
        if record["attempt_id"] != attempt_id:
            continue
        root = Path(record["stage_root"])
        instruction = root / "instruction.txt"
        if (record["profile"] != profile or root.is_symlink() or instruction.is_symlink()
                or not root.name.startswith(record["agent_id"] + "-") or not instruction.is_file()):
            raise OpenClawAuthoringBoundaryError("隔离编排恢复指令缺失或身份不一致")
        message = instruction.read_text(encoding="utf-8")
        if hashlib.sha256(f"{attempt_id}\0{message}".encode()).hexdigest() != key:
            raise OpenClawAuthoringBoundaryError("隔离编排恢复指令已变化，不能重新认领")
        return message
    return None


def _remove_stage_record(key: str) -> None:
    from easel import creation
    from easel.creation_delivery import active_delivery
    with creation.edit_creation(active_delivery.get()) as work:
        work["delivery"].get("authoring_stages", {}).pop(key, None)


def _cleanup_stage(stage_root: Path, agent_id: str, configured: bool, *, command_prefix,
                   profile, cwd, env, runner) -> None:
    if configured:
        try:
            _delete_temporary_agent(command_prefix, profile, agent_id, cwd=cwd, env=env, runner=runner)
        except Exception as exc:
            raise OpenClawAuthoringBoundaryError("OpenClaw 临时 Authoring policy 移除失败；受限 Agent 配置保持有效") from exc
    agent_state_root = stage_root.parent.parent / "agents"
    if agent_state_root.is_dir() and not agent_state_root.is_symlink():
        _remove_exact_tree(agent_state_root, agent_id)
    shutil.rmtree(stage_root)


def release_delivery_authoring(attempt_id: str, *, command_prefix, profile, cwd, env,
                               runner: CommandRunner = subprocess.run) -> None:
    """Release retained staging only after the outer Authoring checkpoint commits."""
    from easel import creation
    from easel.creation_delivery import active_delivery
    creation_id = active_delivery.get()
    if not creation_id:
        return
    work = creation.get_creation(creation_id)
    if any(call["status"] in {"pending", "submitting"}
           for call in work["delivery"].get("agent_calls", {}).values()):
        raise OpenClawAuthoringBoundaryError("编排仍有待核实执行，不能移除其隔离工作区")
    for key, record in work["delivery"].get("authoring_stages", {}).items():
        if record["attempt_id"] != attempt_id:
            continue
        if record["profile"] != profile:
            raise OpenClawAuthoringBoundaryError("编排配置变化，不能移除另一网关的 Agent")
        root = Path(record["stage_root"])
        if root.is_symlink() or not root.name.startswith(record["agent_id"] + "-"):
            raise OpenClawAuthoringBoundaryError("隔离编排清理路径无效")
        if root.exists():
            _cleanup_stage(root, record["agent_id"], True, command_prefix=command_prefix,
                           profile=profile, cwd=cwd, env=env, runner=runner)
        _remove_stage_record(key)


def authoring_agent_policy(workspace: Path, agent_dir: Path) -> dict[str, object]:
    """Return the exact per-turn OpenClaw config, restricted to workspace text files."""
    return {
        "workspace": str(workspace),
        "agentDir": str(agent_dir),
        "skills": [],
        "tools": {
            "profile": "minimal",
            # OpenClaw 2026.9.4 no longer expands the minimal profile from
            # tools.fs. Add only the three workspace file tools to its bounded
            # profile; this version rejects configuring allow and alsoAllow together.
            "alsoAllow": ["read", "write", "edit"],
            "deny": ["group:runtime", "group:web", "group:ui", "group:media",
                     "group:plugins", "group:sessions", "group:automation",
                     "group:messaging", "group:nodes", "group:agents"],
            "fs": {"workspaceOnly": True},
            "elevated": {"enabled": False},
        },
    }


def run_attempt_scoped_authoring(
    *,
    attempt_id: str,
    attempt_workspace: str | Path,
    message: str,
    command_prefix: Sequence[str],
    profile: str,
    staging_parent: str | Path,
    timeout: int,
    thinking: str,
    cwd: str | Path,
    env: dict[str, str],
    runner: CommandRunner = subprocess.run,
    validate_artifacts: Callable[[Path], None] | None = None,
    prepare_workspace: Callable[[Path], None] | None = None,
) -> str:
    """Run OpenClaw against a copy of one Attempt and promote only authoring outputs.

    The OpenClaw Agent receives no shell, network, media, plugin, session, or
    publication tools. Its file tools are rooted to the private staged Attempt
    workspace. Easel copies back only the reviewed Authoring artifacts.
    """
    if not _ATTEMPT_ID.fullmatch(attempt_id):
        raise OpenClawAuthoringBoundaryError("非法 Attempt ID")
    source = Path(attempt_workspace).expanduser().resolve(strict=True)
    if not source.is_dir():
        raise OpenClawAuthoringBoundaryError("Attempt workspace 不存在")

    parent = Path(staging_parent).expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(parent, 0o700)
    stage_key, retained = _delivery_stage(source, parent, attempt_id, message, profile)
    agent_id = retained["agent_id"] if retained else f"easel-author-{attempt_id[-8:]}-{uuid.uuid4().hex[:12]}"
    stage_root = Path(retained["stage_root"]) if retained else Path(tempfile.mkdtemp(prefix=f"{agent_id}-", dir=parent))
    os.chmod(stage_root, 0o700)
    staged_workspace = stage_root / "workspace"
    agent_dir = stage_root / "agent-state"
    configured = False
    preserve = False
    try:
        if not retained or not retained["inputs_ready"]:
            # No Agent is dispatched before inputs_ready is committed. An
            # interrupted copy can be replaced without touching live writes.
            if retained and staged_workspace.exists():
                shutil.rmtree(staged_workspace)
            _stage_authoring_inputs(source, staged_workspace)
            if prepare_workspace is not None:
                prepare_workspace(staged_workspace)
            if retained:
                from easel import creation
                from easel.creation_delivery import active_delivery
                with creation.edit_creation(active_delivery.get()) as work:
                    work["delivery"]["authoring_stages"][stage_key]["inputs_ready"] = True
        policy = authoring_agent_policy(staged_workspace, agent_dir)
        configured = True
        _patch_profile(command_prefix, profile, {
            "agents": {"entries": {agent_id: policy}},
        }, cwd=cwd, env=env, runner=runner)
        _assert_agent_ready(command_prefix, profile, agent_id, staged_workspace,
                            cwd=cwd, env=env, runner=runner)

        staged_message = message.replace(str(source), str(staged_workspace))
        staged_message += (
            "\n先读取所用组件的必要合同，再逐文件调用 write/edit 实际保存；"
            "不要在聊天中展开完整设计推演或输出整份源码。每完成一个文件即落盘，"
            "以免输出长度耗尽时所有产物仍为空。已保存文件仍须完整合同校验。"
        )
        agent_command = [
            *command_prefix, "--profile", profile, "agent", "--agent", agent_id,
            "--session-key", f"agent:{agent_id}:attempt-{attempt_id}",
            "--thinking", thinking, "--timeout", str(timeout), "--message", staged_message,
        ]
        result = _agent_result(
            runner, agent_command, phase="执行", capture_output=True, text=True, cwd=str(cwd),
            timeout=timeout + 30, env=env,
        )
        missing = _missing_authoring_artifacts(staged_workspace)
        if missing:
            repair_message = (
                "〔Easel Authoring 自动补齐：第 2 轮〕\n"
                f"上一轮漏写了这些必需文件：{json.dumps(missing, ensure_ascii=False)}。\n"
                f"唯一工作区根目录是：{staged_workspace}\n"
                "只补写上述缺失文件，必须逐字使用 productions/easel-authoring/ 下的完整相对路径；"
                "若主 SVML 需要尚不存在的 productions/easel-authoring/authors/recipes.svs，"
                "也允许补写此唯一的样式依赖；已有样式文件不得重写。"
                "不要写到 workspace/authors、workspace/runs 等根目录，不要重写已有文件，"
                "不要改动 SCRIPT、SCENES、TREATMENT 或素材选择。"
                "直接分文件调用 write 保存，不在聊天中输出设计推演或整份源码。写完后停止。"
            )
            result = _agent_result(
                runner, [*agent_command[:-1], repair_message], phase="补齐", capture_output=True, text=True,
                cwd=str(cwd), timeout=timeout + 30, env=env,
            )
            if _missing_authoring_artifacts(staged_workspace):
                raise OpenClawAuthoringBoundaryError(
                    "视频编排补齐后仍缺少必需的普通文件；已保留原内容和素材，未提交视频合成"
                )
        if validate_artifacts is not None:
            from easel.integrations.hypit.errors import HypitIntegrationError

            try:
                validate_artifacts(staged_workspace)
            except HypitIntegrationError as exc:
                repair_message = (
                    "〔Easel Authoring 静态契约修复〕\n"
                    f"当前隔离工作区：{staged_workspace}\n"
                    f"本机 Hypit 对隔离产物的校验失败：{str(exc)[:3000]}\n"
                    "重读 AUTHORING_TASK.md 与 hypit-contracts/ 中相关组件的 attributes/children/recipe/notes，"
                    "按正式安装版 Surface 修复当前 SVML、SVS 或 Easel Run JSON；不得从相邻组件猜属性。"
                    "保留冻结内容、已准入素材和身份，不调用 Provider、plan 或 build。"
                    "无效产物尚未提升；修好后停止，由 Easel 再次校验。"
                )
                repaired = _agent_result(
                    runner, [*agent_command[:-1], repair_message], phase="合同修复", capture_output=True, text=True,
                    cwd=str(cwd), timeout=timeout + 30, env=env,
                )
                validate_artifacts(staged_workspace)
        _promote_authoring_artifacts(staged_workspace, source)
        preserve = bool(retained)  # outer selection/checkpoint still has to commit
        return result.stdout or ""
    except Exception as exc:
        from easel.creation_delivery import DeliveryExecutionUncertain
        if isinstance(exc, DeliveryExecutionUncertain):
            preserve = bool(retained)
        raise
    finally:
        if not preserve:
            try:
                _cleanup_stage(stage_root, agent_id, configured, command_prefix=command_prefix,
                               profile=profile, cwd=cwd, env=env, runner=runner)
            except OpenClawAuthoringBoundaryError:
                raise
            except Exception as exc:
                raise OpenClawAuthoringBoundaryError("OpenClaw 临时 Authoring policy 或私有文件清理失败；保留恢复记录") from exc
            if stage_key:
                _remove_stage_record(stage_key)


def _delete_temporary_agent(
    command_prefix: Sequence[str], profile: str, agent_id: str, *,
    cwd: str | Path, env: dict[str, str], runner: CommandRunner,
) -> None:
    result = runner(
        [*command_prefix, "--profile", profile, "agents", "delete", agent_id,
         "--force", "--json"],
        capture_output=True, text=True, cwd=str(cwd), timeout=30, env=env,
    )
    if result.returncode != 0:
        raise OpenClawAuthoringBoundaryError("OpenClaw 临时 Authoring Agent 清理失败")


def _patch_profile(
    command_prefix: Sequence[str], profile: str, patch: dict[str, object], *,
    cwd: str | Path, env: dict[str, str], runner: CommandRunner,
) -> None:
    result = runner(
        [*command_prefix, "--profile", profile, "config", "patch", "--stdin"],
        input=json.dumps(patch, ensure_ascii=False), capture_output=True, text=True,
        cwd=str(cwd), timeout=30, env=env,
    )
    if result.returncode != 0:
        raise OpenClawAuthoringBoundaryError("OpenClaw Authoring policy 更新失败")


def _remove_exact_tree(parent: Path, child_name: str) -> None:
    if child_name in {"", ".", ".."} or "/" in child_name or "\\" in child_name:
        raise OpenClawAuthoringBoundaryError("OpenClaw Agent state path 无效")
    child = parent / child_name
    if child.is_symlink():
        raise OpenClawAuthoringBoundaryError("OpenClaw Agent state path 是符号链接")
    if child.exists():
        resolved_parent = parent.resolve(strict=True)
        resolved_child = child.resolve(strict=True)
        if resolved_child.parent != resolved_parent:
            raise OpenClawAuthoringBoundaryError("OpenClaw Agent state path 越界")
        shutil.rmtree(resolved_child)


def _assert_agent_ready(
    command_prefix: Sequence[str], profile: str, agent_id: str, workspace: Path, *,
    cwd: str | Path, env: dict[str, str], runner: CommandRunner,
) -> None:
    # Validate configuration and confirm the Gateway recognizes this unbound
    # transient Agent before any model call is dispatched.
    for args in (
        ["config", "validate"],
        ["agents", "list", "--json"],
    ):
        result = runner(
            [*command_prefix, "--profile", profile, *args], capture_output=True,
            text=True, cwd=str(cwd), timeout=30, env=env,
        )
        if result.returncode != 0:
            raise OpenClawAuthoringBoundaryError("OpenClaw Agent 配置未通过校验")
        if args[0] == "agents":
            try:
                agents = json.loads(result.stdout)
            except (TypeError, json.JSONDecodeError) as exc:
                raise OpenClawAuthoringBoundaryError("OpenClaw Agent 状态响应无效") from exc
            row = next((item for item in agents if item.get("id") == agent_id), None)
            if not row or Path(row.get("workspace", "")).resolve() != workspace.resolve():
                raise OpenClawAuthoringBoundaryError("OpenClaw 未加载 Attempt 隔离 workspace")


def _stage_authoring_inputs(source: Path, target: Path) -> None:
    target.mkdir(mode=0o700)
    for relative in _INPUT_FILES:
        _copy_regular_file(source, target, relative, required=relative == "AUTHORING_TASK.md")
    for relative in _INPUT_DIRS:
        candidate = source / relative
        if candidate.is_dir():
            _copy_regular_tree(source, target, relative)
    assets = source / "materials" / "assets"
    if assets.is_dir():
        _assert_source_components(source, Path("materials/assets"))
        for asset_dir in assets.iterdir():
            if asset_dir.is_symlink():
                raise OpenClawAuthoringBoundaryError("Material Asset 输入包含符号链接")
            if asset_dir.is_dir():
                _copy_regular_file(source, target,
                                   (Path("materials/assets") / asset_dir.name / "asset.json").as_posix())
    for relative in ("productions/easel-authoring/authors",
                     "productions/easel-authoring/runs"):
        (target / relative).mkdir(parents=True, exist_ok=True)


def _copy_regular_tree(source: Path, target: Path, relative: str) -> None:
    from_root = source / relative
    _assert_source_components(source, Path(relative))
    for path in from_root.rglob("*"):
        if path.is_symlink():
            raise OpenClawAuthoringBoundaryError("Attempt 输入包含符号链接，隔离复制已拒绝")
        if not path.is_file() and not path.is_dir():
            raise OpenClawAuthoringBoundaryError("Attempt 输入包含非普通文件")
    shutil.copytree(from_root, target / relative, dirs_exist_ok=True, symlinks=False)


def _copy_regular_file(source: Path, target: Path, relative: str, *, required: bool = False) -> None:
    relative_path = Path(relative)
    _assert_source_components(source, relative_path)
    src = source / relative_path
    if not src.exists():
        if required:
            raise OpenClawAuthoringBoundaryError("Attempt Authoring Task 不存在")
        return
    if src.is_symlink() or not src.is_file():
        raise OpenClawAuthoringBoundaryError("Attempt 输入必须是普通文件")
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, destination)


def _assert_source_components(root: Path, relative: Path) -> None:
    if relative.is_absolute() or ".." in relative.parts:
        raise OpenClawAuthoringBoundaryError("Attempt 输入路径越界")
    current = root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise OpenClawAuthoringBoundaryError("Attempt 输入包含符号链接，隔离复制已拒绝")


def _promote_authoring_artifacts(staged: Path, destination: Path) -> None:
    pending: list[tuple[Path, Path]] = []
    for relative in (*_PROMOTED_ARTIFACTS, *_OPTIONAL_PROMOTED_ARTIFACTS):
        source = staged / relative
        if relative in _OPTIONAL_PROMOTED_ARTIFACTS and not source.exists() and not source.is_symlink():
            continue
        if source.is_symlink() or not source.is_file():
            raise OpenClawAuthoringBoundaryError("Authoring 未生成全部允许的普通文件")
        if source.stat().st_size > 8 * 1024 * 1024:
            raise OpenClawAuthoringBoundaryError("Authoring 输出超过大小限制")
        data = source.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise OpenClawAuthoringBoundaryError("Authoring 输出必须是 UTF-8 文本") from exc
        if relative.endswith("material-selection.json"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError as exc:
                raise OpenClawAuthoringBoundaryError("Production selection JSON 无效") from exc
            if not isinstance(payload, dict):
                raise OpenClawAuthoringBoundaryError("Production selection 必须是 JSON 对象")
        final = _safe_destination(destination, relative)
        final.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".authoring-", dir=final.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        pending.append((Path(temp_name), final))
    try:
        for temporary, final in pending:
            os.replace(temporary, final)
    finally:
        for temporary, _ in pending:
            temporary.unlink(missing_ok=True)


def _missing_authoring_artifacts(staged: Path) -> list[str]:
    """Return only absent/non-regular allowlisted outputs for one bounded repair."""
    return [
        relative for relative in _PROMOTED_ARTIFACTS
        if (staged / relative).is_symlink() or not (staged / relative).is_file()
    ]


def _safe_destination(root: Path, relative: str) -> Path:
    resolved_root = root.resolve(strict=True)
    target = root / relative
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise OpenClawAuthoringBoundaryError("Authoring 输出路径越界") from exc
    current = resolved_root
    for component in Path(relative).parts:
        current = current / component
        if current.is_symlink():
            raise OpenClawAuthoringBoundaryError("Attempt Authoring 输出路径包含符号链接")
        if current.exists() and current.resolve(strict=True) != current:
            raise OpenClawAuthoringBoundaryError("Attempt Authoring 输出路径解析不一致")
    return current
