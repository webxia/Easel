"""Prepare one chat Creation for external Hypit authoring, without running a Build."""

from __future__ import annotations

import hashlib
import json
import contextlib
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from easel import creation, persona
from easel.creator_proposal import SPEC_LABELS
from easel.integrations.hypit import handoff, service
from easel.integrations.hypit.errors import HypitIntegrationError
from easel.integrations.hypit.secrets import SecretRedactor

_CORE_FIELDS = {
    "schema", "topic", "core_idea", "tension", "why_worth_telling",
    "audience", "intended_takeaway", "claim_types", "boundaries",
}
_PRODUCTION_BRIEF_FIELDS = {
    "schema", "language", "duration_seconds", "aspect_ratio", "audio_mode", "beats",
    "text_overlays", "visual_constraints", "material_sources", "ai_generation_allowed",
    "publication_allowed",
}
_CLAIM_TYPES = {"fact", "observation", "opinion", "hypothesis"}
_CLAIM_SOURCES = {"user_statement", "model_inference", "source_evidence", "unknown"}
_TERMINAL_PREPARATION = {"PRODUCTION_PREPARED", "READY_FOR_EXTERNAL_AUTHORING"}
_RESUMABLE_PREPARATION = {
    "CONTENT_READY", "HANDOFF_READY", "BLOCKED_RUNTIME_NOT_CONFIGURED",
    "BLOCKED_RUNTIME_INVALID", "FAILED", "MATERIAL_FAILED", "MATERIAL_NOT_READY",
    "SCRIPT_TRUTH_REVIEW_REQUIRED",
}


def _material_local_roots() -> tuple[str, ...]:
    """Return explicitly configured Local material roots for product orchestration."""
    from easel.runtime_config import EaselRuntimeConfig
    return EaselRuntimeConfig.load().material.local_roots


class PreparationError(ValueError):
    """Raised when a Creation cannot be prepared safely for Hypit authoring."""


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _operation_key(session_id: str, turn_id: str | None) -> str:
    if not session_id or len(session_id) > 256:
        raise PreparationError("作品准备需要有效的聊天会话")
    seed = turn_id if isinstance(turn_id, str) and turn_id else "turnless"
    return _hash(f"{_hash(session_id)}\0{seed}")


def _pid_alive(pid: Any) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def preparation_paths(creation_id: str, operation_key: str) -> dict[str, Path]:
    if len(operation_key) != 64 or any(c not in "0123456789abcdef" for c in operation_key):
        raise PreparationError("作品准备标识无效")
    root = creation._creation_dir(creation_id) / "preparations" / operation_key
    return {
        "root": root,
        "draft": root / "draft",
        "snapshot": root / "snapshot",
    }


def claim_chat_preparation(
    creation_id: str,
    session_id: str,
    turn_id: str | None,
    *,
    recover_interrupted: bool = False,
) -> dict[str, Any]:
    """Persist a preparation claim before Agent dispatch so turn retries cannot fork work."""
    requested_key = _operation_key(session_id, turn_id)
    result: dict[str, Any] = {}
    with creation.edit_creation(creation_id) as work:
        current = dict(work.get("preparation") or {"status": "CREATED"})
        status = current.get("status", "CREATED")
        if not work.get("creative_mode"):
            current.update({"status": "BLOCKED_CREATIVE_MODE_REQUIRED", "updated_at": creation._now()})
            work["preparation"] = current
            result = {"action": "blocked", **current}
        elif status in _TERMINAL_PREPARATION:
            result = {"action": "already_prepared", **current}
        elif status == "PREPARING" and _pid_alive(current.get("owner_pid")) and not recover_interrupted:
            result = {"action": "in_progress", **current}
        else:
            existing_key = current.get("operation_key")
            key = existing_key if status in _RESUMABLE_PREPARATION and isinstance(existing_key, str) else requested_key
            paths = preparation_paths(creation_id, key)
            has_snapshot = all((paths["snapshot"] / f"{name}.json").is_file()
                              for name in ("content-core", "truth-packet", "creator-context", "production-brief"))
            action = "resume" if has_snapshot or status in {"CONTENT_READY", "HANDOFF_READY"} else "generate"
            current.update({
                "status": "PREPARING" if action == "generate" else status,
                "operation_key": key,
                "owner_pid": os.getpid(),
                "updated_at": creation._now(),
            })
            work["preparation"] = current
            result = {"action": action, **current}
    if result.get("action") == "generate":
        preparation_paths(creation_id, result["operation_key"])["draft"].mkdir(parents=True, exist_ok=True)
    return result


def preparation_agent_context(
    work: dict[str, Any],
    preparation: dict[str, Any],
) -> str:
    """Give the existing Director a bounded Core/Truth task, never film authoring."""
    action = preparation.get("action")
    if action == "generate":
        key = preparation["operation_key"]
        draft = preparation_paths(work["id"], key)["draft"]
        try:
            draft_location = draft.relative_to(creation.PROJECT_ROOT).as_posix()
        except ValueError:
            draft_location = str(draft)
        return (
            "\n\n〔Creation Preparation V1：本作品的唯一准备任务〕\n"
            "你仍是 Easel Director。本轮只整理 Content Core、Truth Packet、最小 Creator Context 和 Production Brief。\n"
            f"CURRENT_CREATION_ID={work['id']}\n"
            "THIS CREATION ALREADY EXISTS. 必须复用该 ID，不得再次 create Creation。\n"
            "以下是必须原样复制到 Content Core topic 的 Creation 初始主题 JSON 值；不要改写、摘要、添加引号或调整空格：\n"
            + json.dumps(work.get("idea", ""), ensure_ascii=False) + "\n"
            "只写以下四个 JSON 文件到目录 " + draft_location + "：\n"
            "- content-core.json\n- truth-packet.json\n- creator-context.json\n- production-brief.json\n\n"
            "Production Brief 严格使用结构：\n"
            '{"schema":"easel-production-brief@1","language":"zh-CN",'
            '"duration_seconds":15,"aspect_ratio":"9:16","audio_mode":"silent",'
            '"beats":[],'
            '"text_overlays":["明确确认的屏幕文字"],"visual_constraints":["明确确认的限制"],'
            '"material_sources":[],"ai_generation_allowed":false,'
            '"publication_allowed":false}\n'
            "上述仅为字段格式示例，15 秒等规格不是用户确认值。beats 未确认时必须为空数组，不得复制占位动作或自行编排。"
            "已确认 beats 的时长合计必须等于总时长（误差最多 0.5 秒）。\n"
            "audio_mode 只能是 silent、voice、music、mixed；旁白与背景音乐同时存在时使用 mixed，"
            "不要写 narration_bgm、voice_bgm 等描述性值。\n"
            "这些值只整理当前用户明确确认的方案；未指定则用空列表/安全默认值，不自行添加偏好。"
            "忠实映射聊天中最后确认的时长、节拍、画幅、音轨、屏幕文字、人物/隐私限制、素材来源、"
            "生成和发布要求；后续用户确认优先于早期建议。\n"
            "ai_generation_allowed 的 false 只是格式示例，不是本作品禁令。核对最后确认的用户许可："
            "明确允许真实缺口使用生图补位时设 true；真实禁令或未授权时设 false。"
            "素材预算仅授权费用，不能据此推导内容许可，也不能因优先图库就丢失补位许可。\n"
            "Content Core 必须严格使用字段：\n"
            '{"schema":"easel-content-core@1","topic":"与 Creation 初始主题逐字一致",'
            '"core_idea":"一个核心判断","tension":"核心矛盾",'
            '"why_worth_telling":"值得讲的原因","audience":"相关受众",'
            '"intended_takeaway":"观众看完应理解什么","claim_types":["fact|observation|opinion|hypothesis"],'
            '"boundaries":["不要扩写的方向"]}\n'
            "Content Core 中不要出现 treatment、script、storyboard、scene、shot、camera、duration、visual_prompt、timeline。\n"
            "Truth Packet 必须严格使用以下唯一合法结构；字段类型也必须一致，不要增加 id、statement、notes 等字段：\n"
            '{"schema":"easel-truth-packet@2","claims":[{"claim":"具体主张",'
            '"kind":"hypothesis","source":"model_inference","confidence":"low"}],'
            '"personal_facts":[{"fact":"画像中可公开的事实","source":"profile","public_allowed":true}],'
            '"first_person_allowed":["仅允许的第一人称用途"],"public_allowed":["允许公开的内容"],'
            '"forbidden_inventions":["禁止补造的内容"],"uncertainty_policy":'
            '{"plan_is_not_experience":true,"learning_is_not_proven_capability":true,'
            '"unknown_claims":"label_uncertain"}}\n'
            "claims 只记录准备写进视频、且关于现实世界的具体内容主张；时长、画幅、beat、静音、素材来源、禁用生成/发布等制作约束不是 Truth claim，必须只写入 Production Brief，不得复制到 claims。若作品是无旁白、无事实字幕的纯观察/镜头表达，claims、personal_facts、first_person_allowed 均使用空数组；不要为了填充结构而把制作规格改写成用户事实。\n"
            "claims 每项只允许 claim/kind/source/confidence/source_quote/source_ref。source 只能是 "
            "user_statement、model_inference、source_evidence、unknown。模型归纳或推理绝不能标 user_statement。"
            "每条 claim 必须同时提供非空 claim、kind、source、confidence；kind 只能是 fact/observation/opinion/hypothesis，"
            "confidence 只能是 high/medium/low。user_statement 的 claim 必须与 source_quote 完全相同，且 source_quote 必须是"
            " Creation 初始主题中的逐字连续片段；不能做到时改为 model_inference 并删除 source_quote。"
            "model_inference/unknown 不得添加 source_quote 或 source_ref；只有 source_evidence 可带真实 source_ref。"
            "Profile 不是 claims.source 的合法值；画像中的已确认个人事实只放入 personal_facts 并标 source=profile，"
            "从画像推导出的判断仍属于 model_inference。"
            "user_statement 必须同时提供 source_quote，且 claim 与 source_quote 完全相同、逐字出现在 Creation 初始主题中；"
            "不符合就改标 model_inference 或 unknown。source_evidence 必须提供真实 source_ref；不能确认则标 unknown。"
            "personal_facts 每项只允许 fact/source/public_allowed/source_quote；source 只能是 user_statement 或 profile。"
            "personal_facts 若为 user_statement，同样必须用逐字 source_quote，且 fact 与 quote 完全一致并出现在初始主题中。"
            "first_person_allowed、public_allowed、forbidden_inventions 都必须是字符串数组；不能写成对象或布尔值。"
            "unknown_claims 只能是 omit 或 label_uncertain。plan 不是经历，学习不等于已证明能力。\n"
            "Creator Context 必须严格使用以下结构，不要改字段名，也不要增加顶层字段：\n"
            '{"schema":"easel-creator-context@1","identity":{"public_description":"公开身份概述"},'
            '"audience":"相关受众","voice":{"tone":"表达语气","avoid":["避免的表达"]},'
            '"relevant_context":["与本主题有关的公开上下文"],'
            '"privacy_policy":{"do_not_infer_private_facts":true}}\n'
            "不要复制完整 Profile/Memory 或无关家庭、财务、求职隐私。\n"
            "只使用用户明确提供、当前观察、画像中可公开且相关的信息；不补造公司事件、对话、日期、金额、结果或经历。"
            "如事实来源不足，明确标 unknown/低置信，不得伪造来源。\n"
            "上次后端校验错误：" + SecretRedactor.redact_text(str(preparation.get("last_error") or "无"))[:1000] + "\n"
            "有上次错误时修正对应草稿，不得原样交付。交付前在项目根目录执行只读合同校验：\n"
            f".venv/bin/python -m easel.creation_preparation --validate-draft {work['id']} {key}\n"
            "失败时修正草稿再校验；只有命令成功才可报告合同校验通过。该命令不冻结、不启动制作。\n"
            "本轮不要写 Treatment、视频脚本、分镜、镜头清单、时间线或 SVRun；不要调用 Hypit check/plan/pricing/build，"
            "不要调用任何媒体 Provider。Hypit 外部 Authoring Agent 将负责全部 Film Authoring。"
        )
    if action == "resume":
        return (
            "\n\n〔Creation Preparation V1：恢复已冻结的准备任务〕\n"
            "复用当前 Creation 和已冻结的 Content Core/Truth/Creator Context/Production Brief；不得重写这些快照，"
            "不得另建 Creation、Handoff 或 Attempt。后端将幂等恢复 Handoff/Attempt 准备。"
            "本轮不要进入 Treatment、Script、Storyboard、Scene、Timeline 或 SVRun，也不要运行 Hypit Build。"
        )
    if action == "already_prepared":
        return (
            "\n\n〔Creation Preparation V1：作品已准备〕\n"
            "当前 Creation 已有准备结果。不要创建或重写 Core、Truth Packet、Handoff、Hypit workspace 或 Attempt；"
            "不要把后续修订自动变成新的 Attempt。正常回应本輪对话即可。"
        )
    if action == "in_progress":
        return (
            "\n\n〔Creation Preparation V1：已有同一作品准备任务正在运行〕\n"
            "不要生成或写入任何准备产物，也不要启动另一条 Hypit 流程。"
        )
    return "\n\n〔Creation Preparation V1：当前作品风格未选择，请引导用户先选择作品风格并新建对话。〕"


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
            raise PreparationError(f"{label} 缺失、越界或超过大小限制")
        value = json.loads(path.read_text(encoding="utf-8"))
    except PreparationError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise PreparationError(f"{label} 不是有效 JSON") from exc
    if not isinstance(value, dict):
        raise PreparationError(f"{label} 顶层必须是 JSON 对象")
    if SecretRedactor.contains_secret(value):
        raise PreparationError(f"{label} 检测到疑似凭证内容")
    return value


def _text(value: Any, field: str, maximum: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise PreparationError(f"Content Core 字段 {field} 无效")
    return value.strip()


def _validate_core(value: dict[str, Any], topic: str) -> dict[str, Any]:
    if set(value) != _CORE_FIELDS or value.get("schema") != "easel-content-core@1":
        raise PreparationError("Content Core schema 或字段不符合 V1 合同")
    if value.get("topic") != topic:
        raise PreparationError("Content Core topic 必须与 Creation 初始主题一致")
    for field in ("topic", "core_idea", "tension", "why_worth_telling", "audience", "intended_takeaway"):
        _text(value.get(field), field, 4000 if field == "topic" else 2000)
    claim_types = value.get("claim_types")
    boundaries = value.get("boundaries")
    if (not isinstance(claim_types, list) or any(item not in _CLAIM_TYPES for item in claim_types)
            or not isinstance(boundaries, list) or len(boundaries) > 30
            or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in boundaries)):
        raise PreparationError("Content Core claim_types 或 boundaries 无效")
    return value


def _validate_production_brief(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != _PRODUCTION_BRIEF_FIELDS or value.get("schema") != "easel-production-brief@1":
        raise PreparationError("Production Brief schema 或字段不符合 V1 合同")
    if value.get("language") not in {"zh-CN", "zh-TW", "en"}:
        raise PreparationError("Production Brief language 无效")
    duration = value.get("duration_seconds")
    if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 900:
        raise PreparationError("Production Brief duration_seconds 必须为 1–900 秒整数")
    if value.get("aspect_ratio") not in {"9:16", "16:9", "1:1", "4:5", "4:3", "3:4"}:
        raise PreparationError("Production Brief aspect_ratio 无效")
    if value.get("audio_mode") not in {"silent", "voice", "music", "mixed"}:
        raise PreparationError("Production Brief audio_mode 无效")
    beats = value.get("beats")
    if not isinstance(beats, list) or len(beats) > 30:
        raise PreparationError("Production Brief beats 必须是最多 30 项的数组")
    beat_total = 0.0
    for beat in beats:
        if not isinstance(beat, dict) or set(beat) != {"label", "duration_seconds", "description"}:
            raise PreparationError("Production Brief beat 字段无效")
        if any(not isinstance(beat.get(key), str) or not beat[key].strip() or len(beat[key]) > 500
               for key in ("label", "description")):
            raise PreparationError("Production Brief beat 文本无效")
        beat_duration = beat.get("duration_seconds")
        if isinstance(beat_duration, bool) or not isinstance(beat_duration, (int, float)) or not 0 < beat_duration <= 900:
            raise PreparationError("Production Brief beat duration 无效")
        beat_total += beat_duration
    if beats and abs(beat_total - duration) > 0.5:
        raise PreparationError(f"制作节拍合计 {beat_total:g} 秒，与总时长 {duration} 秒不一致；未确认节拍时请使用空 beats 数组")
    for key in ("text_overlays", "visual_constraints", "material_sources"):
        items = value.get(key)
        limit = 30 if key != "material_sources" else 12
        if (not isinstance(items, list) or len(items) > limit
                or any(not isinstance(item, str) or not item.strip() or len(item) > 500 for item in items)):
            raise PreparationError(f"Production Brief {key} 无效")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", item) for item in value["material_sources"]):
        raise PreparationError("Production Brief material_sources 只能使用 provider-neutral 标识")
    if not isinstance(value.get("ai_generation_allowed"), bool):
        raise PreparationError("Production Brief ai_generation_allowed 必须是布尔值")
    if value.get("publication_allowed") is not False:
        raise PreparationError("Creation E2E Production Brief 不允许自动发布")
    if SecretRedactor.contains_secret(value):
        raise PreparationError("Production Brief 检测到疑似凭证内容")
    return value


def _validate_truth(value: dict[str, Any], user_input: str) -> dict[str, Any]:
    required = {
        "schema", "claims", "personal_facts", "first_person_allowed", "public_allowed",
        "forbidden_inventions", "uncertainty_policy",
    }
    if set(value) != required or value.get("schema") != "easel-truth-packet@2":
        raise PreparationError("Truth Packet schema 或字段不符合 V1 合同")
    for field in ("claims", "personal_facts", "first_person_allowed", "public_allowed", "forbidden_inventions"):
        if not isinstance(value[field], list) or len(value[field]) > 100:
            raise PreparationError(f"Truth Packet 字段 {field} 必须是有限数组")
    for item in value["claims"]:
        if not isinstance(item, dict) or set(item) - {
                "claim", "kind", "source", "confidence", "source_ref", "source_quote"}:
            raise PreparationError("Truth Packet claim 格式无效")
        if not isinstance(item.get("claim"), str) or not item["claim"].strip():
            raise PreparationError("Truth Packet claim 文本无效")
        if item.get("source") not in _CLAIM_SOURCES:
            raise PreparationError("Truth Packet claim source 非法；画像事实只能进入 personal_facts")
        if (item.get("kind") not in _CLAIM_TYPES
                or item.get("confidence") not in {"high", "medium", "low"}):
            raise PreparationError("Truth Packet claim 缺少有效类型、来源或置信度")
        if "source_ref" in item and (not isinstance(item["source_ref"], str)
                                      or not item["source_ref"].strip() or len(item["source_ref"]) > 2000):
            raise PreparationError("Truth Packet source_ref 无效")
        if "source_quote" in item and (not isinstance(item["source_quote"], str)
                                       or not item["source_quote"].strip()
                                       or len(item["source_quote"]) > 2000):
            raise PreparationError("Truth Packet source_quote 无效")
        source = item["source"]
        if source == "user_statement":
            quote = item.get("source_quote")
            if quote != item["claim"] or quote not in user_input or "source_ref" in item:
                raise PreparationError(
                    "user_statement 的 claim 与 source_quote 必须完全相同，且逐字出现在用户初始输入中")
        elif source == "source_evidence":
            if not item.get("source_ref") or "source_quote" in item:
                raise PreparationError("source_evidence claim 必须带真实 source_ref")
        elif "source_ref" in item or "source_quote" in item:
            raise PreparationError("非 user_statement/source_evidence 不得伪造来源引用")
    for item in value["personal_facts"]:
        if not isinstance(item, dict) or set(item) - {
                "fact", "source", "public_allowed", "source_quote"} or not {
                "fact", "source", "public_allowed"}.issubset(item):
            raise PreparationError("Truth Packet personal_facts 格式无效")
        if (not isinstance(item["fact"], str) or not item["fact"].strip()
                or item["source"] not in {"user_statement", "profile"}
                or not isinstance(item["public_allowed"], bool)):
            raise PreparationError("Truth Packet personal fact 无效")
        if item["source"] == "user_statement":
            quote = item.get("source_quote")
            if quote != item["fact"] or quote not in user_input:
                raise PreparationError("user_statement personal fact 必须逐字出现在用户初始输入中")
        elif "source_quote" in item:
            raise PreparationError("profile personal fact 不应附带用户原话引用")
    for field in ("first_person_allowed", "public_allowed", "forbidden_inventions"):
        if any(not isinstance(item, str) or not item.strip() or len(item) > 1000 for item in value[field]):
            raise PreparationError(f"Truth Packet 字段 {field} 包含无效条目")
    policy = value["uncertainty_policy"]
    if (not isinstance(policy, dict) or policy.get("plan_is_not_experience") is not True
            or policy.get("learning_is_not_proven_capability") is not True
            or policy.get("unknown_claims") not in {"omit", "label_uncertain"}):
        raise PreparationError("Truth Packet uncertainty_policy 未锁定事实边界")
    return value


def _validate_creator_context(value: dict[str, Any]) -> dict[str, Any]:
    handoff._validate_creator_context(value)
    if len(value["identity"]["public_description"]) > 1000 or len(value["audience"]) > 1000:
        raise PreparationError("Creator Context 超过精简快照长度限制")
    if len(value.get("relevant_context", [])) > 8:
        raise PreparationError("Creator Context relevant_context 最多保留 8 条")
    if any(not isinstance(item, str) or len(item) > 500 for item in value.get("relevant_context", [])):
        raise PreparationError("Creator Context relevant_context 必须是短文本数组")
    voice = value.get("voice", {})
    if any(not isinstance(item, str) or len(item) > 300 for item in voice.get("avoid", [])):
        raise PreparationError("Creator Context voice.avoid 格式无效")
    return value


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    try:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PreparationError("准备产物不能序列化为规范 JSON") from exc


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _profile_source_hash(profile_id: str | None) -> str | None:
    if not profile_id:
        return None
    root = persona.PROFILES_DIR.resolve()
    directory = (root / profile_id).resolve()
    if root not in directory.parents or not directory.is_dir():
        raise PreparationError("绑定的 Creator Profile 不存在")
    digest = hashlib.sha256()
    for path in sorted(directory.glob("*.md")):
        if path.is_symlink():
            raise PreparationError("Creator Profile 不允许包含 symlink")
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


@contextlib.contextmanager
def _operation_lock(creation_id: str, operation_key: str):
    lock_path = preparation_paths(creation_id, operation_key)["root"].parent / f"{operation_key}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        if os.name == "nt":
            lock.seek(0, os.SEEK_END)
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                lock.seek(0)
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def validate_preparation_draft(creation_id: str, operation_key: str) -> dict[str, Any]:
    """Read-only validation shared with snapshot promotion."""
    work = creation.get_creation(creation_id)
    if (work.get("preparation") or {}).get("operation_key") != operation_key:
        raise PreparationError("作品准备标识与当前任务不一致")
    draft = preparation_paths(creation_id, operation_key)["draft"]
    raw = {
        "content_core": _read_json(draft / "content-core.json", "Content Core"),
        "truth_packet": _read_json(draft / "truth-packet.json", "Truth Packet"),
        "creator_context": _read_json(draft / "creator-context.json", "Creator Context"),
        "production_brief": _read_json(draft / "production-brief.json", "Production Brief"),
    }
    expected_specs = work.get("chat_workflow", {}).get("production_specs")
    if expected_specs is not None:
        for field, expected in expected_specs.items():
            if expected is None or raw["production_brief"].get(field) != expected:
                raise PreparationError(f"制作规格{SPEC_LABELS.get(field, field)}与 Creator 确认的方案卡不一致；禁止冻结漂移输入")
    return {
        "content_core": _validate_core(raw["content_core"], work["idea"]),
        "truth_packet": _validate_truth(raw["truth_packet"], work["idea"]),
        "creator_context": _validate_creator_context(raw["creator_context"]),
        "production_brief": _validate_production_brief(raw["production_brief"]),
    }


def _persist_snapshot(work: dict[str, Any], preparation: dict[str, Any]) -> dict[str, Any]:
    paths = preparation_paths(work["id"], preparation["operation_key"])
    bundle = validate_preparation_draft(work["id"], preparation["operation_key"])
    snapshot = paths["snapshot"]
    if snapshot.exists():
        raise PreparationError("检测到不完整或已存在的 Content Snapshot；为避免覆盖已冻结内容已停止")
    temp = paths["root"] / f".snapshot-{uuid.uuid4().hex}"
    temp.mkdir(parents=True, exist_ok=False)
    try:
        hashes = {}
        names = {
            "content_core": "content-core.json",
            "truth_packet": "truth-packet.json",
            "creator_context": "creator-context.json",
            "production_brief": "production-brief.json",
        }
        for key, name in names.items():
            payload = _canonical_bytes(bundle[key])
            path = temp / name
            with path.open("xb") as handle:
                handle.write(payload)
            hashes[key] = _sha256(payload)
        temp.chmod(0o555)
        for path in temp.iterdir():
            path.chmod(0o444)
        os.replace(temp, snapshot)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return {"bundle": bundle, "hashes": hashes, "paths": paths}


def _load_snapshot(work: dict[str, Any], preparation: dict[str, Any]) -> dict[str, Any]:
    paths = preparation_paths(work["id"], preparation["operation_key"])
    if not paths["snapshot"].is_dir():
        return _persist_snapshot(work, preparation)
    files = {
        "content_core": paths["snapshot"] / "content-core.json",
        "truth_packet": paths["snapshot"] / "truth-packet.json",
        "creator_context": paths["snapshot"] / "creator-context.json",
        "production_brief": paths["snapshot"] / "production-brief.json",
    }
    payloads = {}
    for key, path in files.items():
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
            raise PreparationError("冻结的 Content Snapshot 缺失、越界或超过大小限制")
        payloads[key] = path.read_bytes()
    hashes = {key: _sha256(payload) for key, payload in payloads.items()}
    expected = preparation.get("snapshot_hashes")
    if not isinstance(expected, dict) or expected != hashes:
        raise PreparationError("冻结的 Content Snapshot hash 不匹配")
    core = _read_json(files["content_core"], "Content Core Snapshot")
    truth = _read_json(files["truth_packet"], "Truth Packet Snapshot")
    context = _read_json(files["creator_context"], "Creator Context Snapshot")
    production_brief = _read_json(files["production_brief"], "Production Brief Snapshot")
    bundle = {"content_core": _validate_core(core, work["idea"]),
              "truth_packet": _validate_truth(truth, work["idea"]),
              "creator_context": _validate_creator_context(context),
              "production_brief": _validate_production_brief(production_brief)}
    return {"bundle": bundle, "hashes": hashes, "paths": paths}


def _update_preparation(creation_id: str, **fields: Any) -> dict[str, Any]:
    with creation.edit_creation(creation_id) as work:
        value = dict(work.get("preparation") or {})
        value.update(fields)
        value["updated_at"] = creation._now()
        value.pop("owner_pid", None)
        work["preparation"] = value
    return creation.get_creation(creation_id)["preparation"]


def mark_preparation_failed(creation_id: str, message: str) -> None:
    safe = SecretRedactor.redact_text(message)[:1000]
    try:
        work = creation.get_creation(creation_id)
        current = work.get("preparation", {})
        if current.get("status") in _TERMINAL_PREPARATION or current.get("attempt_id"):
            return
        _update_preparation(creation_id, status="FAILED", last_error=safe, owner_pid=None)
    except Exception:
        return


def _snapshot_artifacts(work: dict[str, Any], snapshot: dict[str, Any]) -> list[str]:
    relative_root = snapshot["paths"]["snapshot"].relative_to(creation.OUTPUTS_DIR.resolve())
    return [
        (relative_root / "content-core.json").as_posix(),
        (relative_root / "truth-packet.json").as_posix(),
        (relative_root / "creator-context.json").as_posix(),
        (relative_root / "production-brief.json").as_posix(),
    ]


def prepare_creation_for_hypit(
    creation_id: str,
    *,
    runtime_profile: str | None,
    planning_executor: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Freeze Easel-owned inputs, create/reuse Handoff and Attempt #1, then stop."""
    work = creation.get_creation(creation_id)
    try:
        creation.require_chat_proposal_confirmed(work)
    except creation.CreationError as exc:
        raise PreparationError(str(exc)) from exc
    preparation = work.get("preparation") or {}
    operation_key = preparation.get("operation_key")
    if not isinstance(operation_key, str):
        raise PreparationError("Creation 缺少有效的 Preparation operation key")
    with _operation_lock(creation_id, operation_key):
        return _prepare_creation_for_hypit_locked(
            creation_id, runtime_profile=runtime_profile, planning_executor=planning_executor)


def _prepare_creation_for_hypit_locked(
    creation_id: str,
    *,
    runtime_profile: str | None,
    planning_executor: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None,
) -> dict[str, Any]:
    work = creation.get_creation(creation_id)
    try:
        creation.require_chat_proposal_confirmed(work)
    except creation.CreationError as exc:
        raise PreparationError(str(exc)) from exc
    preparation = dict(work.get("preparation") or {})
    operation_key = preparation.get("operation_key")
    if not isinstance(operation_key, str) or len(operation_key) != 64:
        raise PreparationError("Creation 缺少有效的 Preparation operation key")
    if not work.get("creative_mode"):
        raise PreparationError("视频创作尚未选择作品风格；需新建对话后重试")

    snapshot = _load_snapshot(work, preparation)
    if preparation.get("status") not in {"CONTENT_READY", "HANDOFF_READY", "PRODUCTION_PREPARED",
                                         "BLOCKED_RUNTIME_NOT_CONFIGURED", "BLOCKED_RUNTIME_INVALID"}:
        artifacts = _snapshot_artifacts(work, snapshot)
        if work["stages"]["content_core"].get("status") != "completed":
            creation.record_stage(
                creation_id, "content_core", "completed", artifacts=artifacts,
                summary="Content Core、Truth Packet 与精简 Creator Context 已冻结",
            )
        preparation = _update_preparation(
            creation_id, status="CONTENT_READY", snapshot_hashes=snapshot["hashes"],
            snapshot_artifacts=artifacts,
        )
        work = creation.get_creation(creation_id)

    handoff_id = preparation.get("handoff_id")
    if handoff_id:
        record = next((item for item in work.get("hypit_handoffs", [])
                       if item.get("handoff_id") == handoff_id), None)
        if record:
            handoff.resolve_handoff(creation_id, handoff_id)
            handoff_record = record
        else:
            raise PreparationError("Creation preparation 引用了未登记的 Handoff")
    else:
        profile_hash = _profile_source_hash(work.get("profile"))
        handoff_record = service.create_creation_handoff(
            creation_id,
            content_core=snapshot["bundle"]["content_core"],
            truth_packet=snapshot["bundle"]["truth_packet"],
            creator_context=snapshot["bundle"]["creator_context"],
            references=[],
            production_request={
                "media_type": "video",
                "orientation": snapshot["bundle"]["production_brief"]["aspect_ratio"],
                "language": snapshot["bundle"]["production_brief"]["language"],
                "production_brief": snapshot["bundle"]["production_brief"],
                "production_brief_sha256": snapshot["hashes"]["production_brief"],
                **({"video_plan": work["delivery"]["video_plan"]}
                   if (work.get("delivery") or {}).get("video_plan") else {}),
                **({"confirmed_proposal_sha256": (work.get("chat_workflow") or {}).get("proposal_sha256")}
                   if (work.get("chat_workflow") or {}).get("proposal_sha256") else {}),
            },
            preparation_key=operation_key,
            profile_source_sha256=profile_hash,
        )
        preparation = _update_preparation(
            creation_id, status="HANDOFF_READY", handoff_id=handoff_record["handoff_id"],
            handoff_hash=handoff_record["hash"],
        )
        work = creation.get_creation(creation_id)

    runtime_state = "CONFIGURED"
    runtime_error = None
    if runtime_profile:
        try:
            service._runtime_identity(runtime_profile)
        except HypitIntegrationError as exc:
            runtime_state = "INVALID"
            runtime_error = SecretRedactor.redact_text(str(exc))[:1000]
    else:
        runtime_state = "NOT_CONFIGURED"
    attempt = service.create_film_attempt(
        creation_id, handoff_record["handoff_id"],
        runtime_profile=runtime_profile if runtime_state == "CONFIGURED" else None,
        preparation_key=operation_key,
        runtime_status=runtime_state,
    )

    # Product Creation always traverses the Material lifecycle. Local roots
    # configure one supply source; an empty registry produces an auditable
    # NOT_READY gate instead of skipping Planning and Supply.
    material_roots = _material_local_roots()
    from easel.integrations.material_layer import (
        MaterialIntegrationError,
        MaterialProductOrchestrator,
        PlanningIntegration,
    )

    active_stage = "planning"
    _update_preparation(creation_id, active_stage=active_stage, failure_stage=None)
    try:
        planning = None
        if attempt.get("material_planning", {}).get("status") == "PLANNING_READY":
            planning = PlanningIntegration().load(attempt)
            if not attempt.get("production_authoring") and attempt.get("execution_status") == "NOT_SUBMITTED":
                from easel.materials.application.compiler import NeedCompiler, NeedCompilationError
                try:
                    for need in planning["plan"].needs:
                        NeedCompiler().compile(need)
                except NeedCompilationError:
                    # A structurally valid but non-retrievable plan is not a
                    # trusted supply checkpoint. Repair it via the same Director.
                    planning = None
        if planning is None:
            if planning_executor is None:
                raise MaterialIntegrationError("Production Planning executor is required; Material Gate cannot be bypassed")
            _, handoff_manifest, _ = handoff.resolve_handoff(creation_id, handoff_record["handoff_id"])
            production_request = handoff_manifest.get("production_request", {})
            if (production_request.get("production_brief_sha256") != snapshot["hashes"]["production_brief"]
                    or production_request.get("production_brief") != snapshot["bundle"]["production_brief"]):
                raise MaterialIntegrationError("Handoff Production Brief does not match its frozen snapshot")
            mode = handoff_manifest.get("creative_mode", {})
            planning_context = {
                "content_core": snapshot["bundle"]["content_core"],
                "truth_packet": snapshot["bundle"]["truth_packet"],
                "creator_context": snapshot["bundle"]["creator_context"],
                "context_refs": {
                "content_core_sha256": snapshot["hashes"]["content_core"],
                "truth_packet_sha256": snapshot["hashes"]["truth_packet"],
                "creator_context_sha256": snapshot["hashes"]["creator_context"],
                "production_brief_sha256": snapshot["hashes"]["production_brief"],
                "creative_mode_sha256": mode.get("hash", ""),
                },
            }
            planning = planning_executor(attempt, planning_context)
        active_stage = "material"
        _update_preparation(creation_id, active_stage=active_stage)
        material_result = MaterialProductOrchestrator().run_with_planning(
            attempt, material_roots, planning,
        )
    except (MaterialIntegrationError, OSError, ValueError) as exc:
        safe_error = SecretRedactor.redact_text(str(exc))[:1000]
        _update_preparation(
            creation_id,
            status="MATERIAL_FAILED",
            failure_stage=active_stage,
            runtime_status=attempt.get("runtime_status"),
            handoff_id=handoff_record["handoff_id"],
            handoff_hash=handoff_record["hash"],
            attempt_id=attempt["attempt_id"],
            attempt_number=attempt["attempt_number"],
            last_error=safe_error,
        )
        raise PreparationError(safe_error) from exc
    material_status = material_result["status"]
    if material_status == "SCRIPT_TRUTH_REVIEW_REQUIRED":
        _update_preparation(
            creation_id,
            status="SCRIPT_TRUTH_REVIEW_REQUIRED",
            runtime_status=attempt.get("runtime_status"),
            handoff_id=handoff_record["handoff_id"],
            handoff_hash=handoff_record["hash"],
            attempt_id=attempt["attempt_id"],
            attempt_number=attempt["attempt_number"],
            last_error="Script claims require explicit local-operator review before Material Supply",
        )
        return {
            "status": "SCRIPT_TRUTH_REVIEW_REQUIRED",
            "runtime_status": attempt.get("runtime_status"),
            "creation_id": creation_id,
            "handoff_id": handoff_record["handoff_id"],
            "attempt_id": attempt["attempt_id"],
            "attempt_number": attempt["attempt_number"],
            "workspace": attempt["workspace"]["path"],
        }
    if material_status != "MATERIAL_READY":
        _update_preparation(
            creation_id,
            status="MATERIAL_NOT_READY",
            runtime_status=attempt.get("runtime_status"),
            handoff_id=handoff_record["handoff_id"],
            handoff_hash=handoff_record["hash"],
            attempt_id=attempt["attempt_id"],
            attempt_number=attempt["attempt_number"],
            last_error="required MaterialNeed 未覆盖；Production Authoring 已阻止",
        )
        return {
            "status": "MATERIAL_NOT_READY",
            "runtime_status": attempt.get("runtime_status"),
            "execution_status": attempt.get("execution_status"),
            "creation_id": creation_id,
            "handoff_id": handoff_record["handoff_id"],
            "attempt_id": attempt["attempt_id"],
            "attempt_number": attempt["attempt_number"],
            "workspace": attempt["workspace"]["path"],
            "task_path": attempt["authoring"]["task_path"],
        }
    attempt = material_result["attempt"]

    status = attempt.get("authoring_status", "READY_FOR_EXTERNAL_AUTHORING")
    _update_preparation(
        creation_id, status="PRODUCTION_PREPARED", runtime_status=attempt.get("runtime_status"),
        handoff_id=handoff_record["handoff_id"], handoff_hash=handoff_record["hash"],
        attempt_id=attempt["attempt_id"], attempt_number=attempt["attempt_number"],
        last_error=runtime_error,
    )
    return {
        "status": status,
        "runtime_status": attempt.get("runtime_status"),
        "execution_status": attempt.get("execution_status"),
        "creation_id": creation_id,
        "handoff_id": handoff_record["handoff_id"],
        "attempt_id": attempt["attempt_id"],
        "attempt_number": attempt["attempt_number"],
        "workspace": attempt["workspace"]["path"],
        "task_path": attempt["authoring"]["task_path"],
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="只读校验 Preparation 草稿；不冻结、不运行生产")
    parser.add_argument("--validate-draft", nargs=2, required=True, metavar=("CREATION_ID", "OPERATION_KEY"))
    args = parser.parse_args()
    try:
        validate_preparation_draft(*args.validate_draft)
    except (ValueError, HypitIntegrationError) as exc:
        parser.exit(1, SecretRedactor.redact_text(str(exc))[:1000] + "\n")
    print("Preparation 四个草稿已通过后端合同校验（尚未冻结）")
