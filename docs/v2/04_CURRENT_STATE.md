# Easel V2 · 当前状态

> 状态：**S0 — 骨架已推送；CI 文档引用故障已修复并由远端验证通过**；核查日期：2026-10-16。CI 通过记录属于下文列明的提交；新提交仍须独立验证。
> 本文是当前快照，不是历史运行流水账。阶段结果需指出证据范围，后续更新本段而非在文件顶端追加“最新”。

## 项目基线与保护范围

- 开发仓库：`/Users/xgx/Projects/Easel`；分支 `easel-v2-rebuild`；官方起点 `4ffdc980`（`upstream/main`），S0 骨架已推送提交 `939b1184`。
- `easel-studio` 已在自有 GitHub Fork 单独封存；旧协议与 Planning 调试不自动迁入 V2。
- S0 仅修改研发骨架文档、模板及有限 CI/贡献说明；不修改视频业务源码或用户的运行素材/凭证。
- 已存在的未跟踪文件（二维码图片、临时技能草稿目录和两个中文创作目录）属于原现场，本轮不删除、不纳入提交。**未将仅存在于本地的目录写成可解析的仓库路径链接。**
- 官方新代码曾在本机通过 Web HTTP、浏览器页面、Gateway 及 Skills 列表可用性检查；这**不**构成真实 AI 视频创作成功的证明。
- 上一轮独立配置/安全测试中曾有 183 PASS / 1 FAIL（占位模型 Key 测试在已加载自定义配置环境中未隔离）；属于旧范围证据，不能写成完整仓库全绿。

## 当前里程碑与单一下一事项

| 阶段 | 事实状态 |
|---|---|
| S0 | 骨架 `939b1184` 与文档路径修复 `5ddac359` 均已推送；本地定向测试通过；修复提交的 GitHub Actions 全部必跑任务 PASS，S0 收口 |
| S1–S5 | 尚未进入，未获得具体生产执行验收结果 |

## 本轮 S0 本地验收证据

- `python scripts/validate_document_paths.py`：**本地 PASS**（1045 条路径）；修复提交的 GitHub Actions 纯净检出验证亦已 PASS。
- `python scripts/validate_skills.py`：**PASS**，114 项 Skills/发布契约；`python scripts/validate_skill_commands.py`：**PASS**，306 条文档命令。
- `python -m pytest -q tests/test_document_paths.py tests/test_agent_harnesses.py`：**100 PASS**，2 条非阻断依赖弃用警告。
- `git diff --check` 和 11 个必要文件存在性检查：**PASS**；CI YAML 本地解析 **PASS**，V2 push 范围和 PR 触发配置存在。
- WebCodex 的 `project.instructions` 已读取到根 `AGENTS.md`，完整加载且未截断；**产品内创作 Agent 实际运行时的指令发现/隔离未做模型调用验证**。
- 首次 GitHub Actions（[CI #38860788907](https://github.com/webxia/Easel/actions/runs/38860788907)）因文档引用了未提交的临时目录而失败；修复后 [CI #38861847307](https://github.com/webxia/Easel/actions/runs/38861847307) 对 `5ddac359` 结论为 **SUCCESS**：全部必跑任务通过，真实安装任务按既有触发条件跳过。未运行真实创作或媒体制作；未修改业务源码、User Profile、素材及原有未跟踪文件。

**NEXT_SINGLE_ACTION**：进入 S1，审计官方源码能力与创作 Agent 指令加载边界，产出各项需求“复用 / 改造 / 缺失”的证据映射。真实付费调用需另行明确授权。

## 更新这个文件时

只记录当前活动事项、确认的证据、仍存在的风险及下一动作。具体失败日志由测试记录、Task、Git 或 PR 承担，不在本文件复制历史。
