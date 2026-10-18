# Easel V2 · 当前状态

> 最后核实：2026-10-18。本文仅汇总当前事实与唯一研发下一动作；完整运行及失败证据见 [S6-14](tasks/S6-14_integration-release.md)。

## 当前结论

**S6-14 · PARTIAL：第五轮已达到 REAL_API_PRODUCTION_PASS / ZERO_MANUAL_RECOVERY_PASS / CREATOR_REVIEW_PENDING。** 在固定生产源码 `406e523c` 上，正式 API 从新建作品、Planning到真实素材/TTS、剪辑、FFmpeg、技术QC自动完成，无人工 `/resume`。自动音视频语义QC仍 **NOT_TESTED / manual_review_only**，Creator尚未接受；不能据此宣称完整Web对话或S7矩阵通过。

S6-01～13 的软件主链已接通；[S6-15](tasks/S6-15_material-layer-hardening.md) **CLOSED / COMPLETE**，不重开历史G4。前三部成片的研发协助记录、第四轮FAIL均保留，第五轮是独立成功样本。

用户已明确要求回到 **Easel 对话式创作**，并已授权完成A2～A4及本轮A5离线验收。[S6-14A](tasks/S6-14A_conversation-integration.md)现为 **A1 ISOLATED_FAKE_PASS；A2～A4 IMPLEMENTED / SOFTWARE_PASS；A5 ISOLATED_INTERACTION_PASS（28/28离线判据）；A6 COMPLETE / SOFTWARE_PASS（对话管线入口统一，6项隔离入口判据）**。已实现持久OpenClaw桥、带来源创作依据、统一对话/卡片/频道导演入口及审片/版本/明确长期保存闭环；已跑通频道创建→参考形成导演→方案→本地出片→独立接受→局部修订→长期保存→内容库续作。实际实现映射见[实施合同§9.10](15_IMPLEMENTATION_DESIGN.md#910-a2a4实际落地与部署边界)，隔离原生与浏览器证据见任务卡。正式配置和第五轮生产数据未改，不能将本轮软件结果当成正式部署或真实Web生产通过。

## 唯一执行入口

- 工作区 `/Users/xgx/Projects/Easel`；分支 `easel-v2-main-workspace`。第五轮成功生产基线 `406e523c035fe8da0f1435f4d813defa63653692`，A2～A4实施基线44b3f08c，A5起点6efb91e9，当前HEAD以Git为准。
- 服务 [本机7860](http://127.0.0.1:7860/)，唯一 `com.easel.web`。此前A1收口时只读能力检查HTTP200，`backend.reload_required=false`；未重启服务。生产源码后续有改动须先核实服务版本，禁止旧worker处理新命令。
- 当前聊天运行设置实测 **OpenClaw**，V2生产走 **MiniMax任务调用**；本轮已在源码挂载协议2持久工具桥并完成隔离Web/原生插件接线验证；正式Gateway未安装配置，正式服务未重载，不能混为已部署。
- [PR #8](https://github.com/webxia/Easel/pull/8) 仍是历史 `codex/s6-production` Draft，不包含主工作区最新修复；本轮不合并或汇合PR。
- 真实服务保持具名授权；不使用qwen3.8或DeepSeek替代，不重发成功/UNKNOWN请求。本轮不创建第六轮、不迁移业务数据、不自动接受或发布。

## 已核实的真实作品

| Work ID | 结果 | 人工审阅 |
|---|---|---|
| `1bc5f5fa797047dabd6e00654ee3675a` | 第一次成片，经历研发协助 | reviewable，未接受 |
| `f8040a6d153c419aaf1045eadc61bc63` | 第二次成片，首次配音时长阻断后修订完成 | reviewable，未接受 |
| `59a27d8fb2f54be0a43507e2f78b9a02` | 第三次成片，Edit阻断后重载/恢复完成 | reviewable，未接受 |
| `18a20ed1fe9241168fd13c16648c1742` | 第四轮Planning口播字段治理前失败，零人工直通FAIL保留 | 未出片 |
| `9b9ed8da98e4437e89618ceee1cb7731` | **第五轮正式API自主完成，零人工恢复PASS** | reviewable，Creator审阅待反馈 |

第五轮输出 `f06e9604f6134039b5c22ae1303df323`：[播放视频](http://127.0.0.1:7860/api/production/artifacts/f06e9604f6134039b5c22ae1303df323/content)。45.000秒、1080×1920、H.264/AAC、51,940,170 bytes；SHA与登记一致。4次MODEL（Planning含一次自动格式修复）+7次VOICE全部成功，无UNKNOWN；技术QC pass，语义QC未测，quality_state仍needs_fix，接受记录为空。详细素材/命令/回执证据见父任务。

第五轮生产基线最近软件回归为 **465 passed / 3 skipped / 0 failed**。此前 A1 新增边界用例后生产模块回归 **479 passed / 4 skipped / 0 failed**，原生安装集成用例已单独显式执行 **1 passed**，插件 Node 用例 **5 passed**；[A1记录](tasks/S6-14A_conversation-integration.md)区分其隔离范围与正式验收。

## 唯一研发下一动作

**A6已完成；当前等待用户体验反馈与正式Gateway配置合成、受控部署的另行授权。** 对话笔入口的管线区域已并列视频创作、创建导演、创建频道；同聊天继续、保留主题/附件，不自动发送或生产。A6浏览器与单测组合完成6项补充判据，Node97 passed，build/lint通过；菜单选择产生0 Work/Run/Operation，隔离服务已回收。证据见[S6-14A A6](tasks/S6-14A_conversation-integration.md#2026-10-18--a6对话管线入口统一用户澄清software_pass)。

A5的UI01～UI28仍保留其原离线范围：Python557 passed / 4 skipped、原协议1原生兼容1 passed、完整本地媒体探针42项PASS、含memory-core的原生权限探针16项PASS、Node91 passed。A6没有重新执行这些Python/媒体探针，也不将6项入口验证并入原28项分母。正式安装/重载/库迁移、真实付费Web生产和第五轮Creator接受均未执行；当前源码有变更，不能沿用A1历史reload_required=false。


Creator可同时通过上方视频入口审片，反馈故事/风格、画面匹配、旁白/字幕、音乐/音效与节奏；未明确接受不标CREATOR_ACCEPTED。跨题材风格、质量、耗时/成本及完整规格矩阵归后续S7，不以此次交互设计自动启动。

## 权威参考

- [S6-14 真实证据与本轮验收](tasks/S6-14_integration-release.md)
- [S6-14A 新增交互任务](tasks/S6-14A_conversation-integration.md) · [交互设计与图](20_CONVERSATIONAL_INTERACTION.md)
- [任务包](tasks/S6_IMPLEMENTATION_PLAN.md) · [需求](01_REQUIREMENTS.md) · [架构](02_ARCHITECTURE.md) · [运行配置](16_RUNTIME_SETUP.md)
