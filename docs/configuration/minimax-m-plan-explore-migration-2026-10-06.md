# MiniMax M Plan Explore 接入改动清单

日期：2026-10-06。状态：待实施方案。适用范围：Easel 使用的 OpenClaw 文字与视觉理解，以及 Material Layer 的 MiniMax 图片、视频和预置音色旁白生成。

**优先改动文字模型配置、每轮 thinking 参数和会话回放保护；媒体生成可以复用现有 Adapter，但启用套餐扣额前要核实具体模型权益，并补齐计费口径与额度处理。** 单独更换 Key 或模型名不足以完成迁移。

本次交付为改动方案，不代表已经切换模型、加载配置或通过真实调用验收。当前产品状态仍以 [Current State](../02_CURRENT_STATE.md) 为准；本方案不改变现有 Workstream 的执行顺序。

## 套餐变化及影响

以下为本次读取的国内站官方规则，账号实际权益与剩余额度另行核实。

| 项目 | M Plan Explore 官方规则 | 对 Easel 的影响 |
|---|---|---|
| 文字模型 | 当前列出的模型为 `MiniMax-M3.1-Flash-Preview` | 以该 ID 作为迁移目标；文档未列出旧 M3，不等于已证明旧模型立即失效 |
| 思考 | 新模型强制开启；`thinking.type=disabled` 或 `reasoning_effort=none` 返回 400 | 移除关闭思考的设置，核实实际请求参数与回放 |
| 思考深度 | `low`、`medium`、`high`、`xhigh`、`max`；省略默认 `max` | 建议先用 `low` 做兼容验证，复杂任务再依据质量与耗时选择 |
| 多模态 | 包含图像、音频；Explore、Build 还包含 H3 视频 | 可以评估让现有素材调用使用订阅额度；H3-Max 等具体型号需单独核实 |
| 额度共享 | 同一订阅在各工具、各模态间共享 | Easel 的局部统计不能当作账号全局剩余额度 |
| 时间窗口 | 非视频同时受 5 小时和周窗口限制；视频仅受周窗口限制 | 区分限速、5 小时额度和周额度；视频不能靠等待 5 小时刷新恢复周额度 |
| 扣减顺序 | 套餐额度优先，其次已购积分；订阅 Key 不自动扣账户余额 | 不能显示为“套餐内永远免费”，也不能将失败自动转为按量扣费 |
| Key | 订阅 Key 与普通按量 API Key 独立 | 普通 Key 不会因账号购买 Explore 自动开始扣套餐额度 |
| 使用定位 | 个人交互式使用；官方建议生产环境使用按量付费 | 本机个人创作可评估使用，不能据此承诺后台长期无人值守的服务可用性 |

Explore 的“3 倍额度”是相对 Go，不是相对用户原 Token Plan。升级后旧 Token Plan 的特殊优惠或额外额度不自动保留。

## 当前接入基线

本次检查的主工作区 HEAD 为 `c9cb4b9c`，分支为 `easel-studio`，存在既有未提交修改。下表是磁盘配置与源码事实，不证明运行中的服务已经加载相同配置。

| 位置 | 已确认行为 |
|---|---|
| 本机 OpenClaw easel profile | OpenClaw `2026.9.4`；默认 `minimax/MiniMax-M3`；`openai-completions`；地址 `https://api.minimax.cn/v1` |
| 同一模型配置 | `reasoning=false`；`thinkingDefault=off`；`extra_body.thinking.type=disabled`；上下文 1,000,000，输出上限 8192 |
| [Web 调用入口](../../web/app.py) | `THINKING_LEVEL` 从 `EASEL_THINKING_LEVEL` 读取，默认 `off`；普通对话、同步 Agent 调用和隔离 Authoring 都使用该值 |
| [旧 M3 配置脚本](../../scripts/configure_minimax_m3_thinking.py) | 只接受旧 M3，并写入 `thinking.type=disabled`；已明确拒绝 M3.1，不能作为新模型迁移脚本 |
| [会话修复脚本](../../scripts/session_heal.py) | `sanitize_rows` 删除所有 `thinking` / `redacted_thinking` 块，没有按 Provider 或签名区分；Web 在对话前调用它 |
| [素材配置](../../easel/runtime_config.py) | Key 优先 `EASEL_MINIMAX_API_KEY`，其次 `MINIMAX_API_KEY`；默认 `image-01`、`speech-2.8-hd`、`MiniMax-H3-Max`；媒体 host 为 `https://api.minimax.cn` |
| [生成核价](../../easel/materials/providers/minimax_pricing.py) | 从公开按量价格读取人民币估算，没有订阅权益、窗口或积分查询 |
| [作品生成授权](../../easel/integrations/material_generation.py) | scope 绑定媒体模型、音色、API origin 和 Key 摘要；按目录价估算占用作品预算 |
| [依赖预检](../../easel/runtime_dependencies.py) | 仅检查配置存在及支持的模型，`CONFIG_READY` 不证明 Key 认证、套餐权益或剩余额度 |

尚未核实现有 Key 的计费类型、升级后是否沿用、当前窗口余额及积分余额。公开规则不能替代这些账号事实。

## 第一批改动 文字模型可用性

这一批是采用 M Plan 当前文字模型的最小迁移范围。

| 编号 | 必要改动 | 涉及位置 | 完成标准 |
|---|---|---|---|
| A1 | 将默认模型及模型目录中的 ID 对齐到 `MiniMax-M3.1-Flash-Preview`，更新显示名，标记支持 reasoning | 本机 OpenClaw easel profile；配置说明 | 默认模型解析到新 ID，旧 M3 参数不会被误套用 |
| A2 | 删除新模型上的 `thinking.type=disabled`，使用 `adaptive` 或不传该开关；将思考档位设为受支持的值 | 同一 profile；模型参数映射 | 实际请求不含 disabled/none；显式传递预期深度，避免意外使用默认 max |
| A3 | 对齐 Web 每轮调用的 `EASEL_THINKING_LEVEL`；修正“MiniMax 只支持 off”的旧注释；为新模型的不兼容设置提供明确提示 | `web/app.py`；`.env.example`；运行配置文档 | 普通对话、Preparation/Planning、素材观察和 Authoring 的实际参数一致，环境覆盖也不能悄悄产生禁用参数 |
| A4 | 限定旧会话修复逻辑的适用范围，保留 MiniMax 工具调用所需的完整思考内容 | `web/app.py::_heal_openclaw_session`；`scripts/session_heal.py` | M3.1 的 assistant、thinking、tool call 和 tool result 可完整往返；旧网关的具名签名修复场景仍有效 |
| A5 | 核实 8192 输出上限与思考占用；处理 `finish_reason=length`、有思考但正文为空等结果 | OpenClaw 模型配置；现有调用结果处理 | 截断不会被认领为有效 JSON 或任务成功；输出上限按任务证据调整，不直接照抄 1M 上下文大小 |
| A6 | 限定旧 M3 脚本用途并补充迁移说明，复用现有配置安全写入能力 | `scripts/configure_minimax_m3_thinking.py`；`tests/test_minimax_thinking_contract.py` | 旧脚本继续拒绝新模型；迁移可预览、幂等、可回退，且保留其他模型和认证配置 |

A4 是本次整理新增确认的风险：官方要求多轮工具调用保留完整 assistant 返回及 `reasoning_content`，而现有修复函数会无差别删除思考块。实际新模型失败尚未复现，但不能将该旧行为直接带入迁移验收。

OpenClaw 当前安装代码已有 `reasoning_content` 的接收与回放处理；是否正确保留还受 `reasoning` 和每轮思考参数影响。先用确定性请求/回放验证定位缺口，不因版本号较旧就直接升级整个 OpenClaw。

`web/app.py::_material_compact_result` 的执行身份包含 `native-thinking-off-json@2`。迁移时应同步核对该策略标识：必要时仅为新执行或已确认失败的执行使用新标识，继续复用有效领域缓存；不能通过修改标识重发正在运行或结果未知的任务。

## 第二批改动 素材使用订阅额度

仅在决定让图片、视频和旁白实际使用 Explore 额度时执行。文字模型迁移可以先完成。

| 编号 | 改动或核实项 | 涉及位置 | 完成标准 |
|---|---|---|---|
| B1 | 核实订阅 Key 的归属、区域及具体模型权益 | 本机认证所有者；MiniMax 官方控制台或只读接口 | 分别确认 `image-01`、`speech-2.8-hd`、`MiniMax-H3-Max`；不根据“H3”统称推定 H3-Max 已可用 |
| B2 | 为素材调用显式配置订阅 Key；建议使用已有 `EASEL_MINIMAX_API_KEY` 避免通用变量影响其他工具 | 本机受保护配置；`easel/runtime_config.py`；`.env.example` | 文字和素材各自的认证来源清晰；无静默按量 Key 回退 |
| B3 | 区分作品成本估算、套餐消耗和实际现金支出 | `minimax_pricing.py`；`material_generation.py`；前端费用文案 | 可保留目录价估算作为作品成本上限，但不得声称该数值就是账号实扣；不把套餐调用记为零成本 |
| B4 | 增加按需只读用量检查与脱敏投影 | Provider/运行依赖层；必要的后台 API 与状态页面 | 能显示套餐、5 小时/周窗口及积分的已核实信息；查询失败显示未知，不假定额度充足 |
| B5 | 区分认证、模型权益、短期限速和套餐额度耗尽 | MiniMax 三种 Adapter；现有交付错误映射 | 认证/权益错误不盲重试；限速采用有界等待；额度不足保留检查点并说明恢复条件 |
| B6 | 核对订阅使用条款对现有生成素材用途政策的影响 | `material_generation.py::commission_generated_rights`；公开协议证据 | 不因套餐包含生成能力就推定用途权利；仅在现有证据仍适用时复用自动准入 |

现有图片、视频、TTS 的官方 API 路径及 Provider 隔离方式可以保留；没有证据要求改用 MiniMax CLI 或新建媒体生产链。视频当前为 `/v2/video_generation`，图片为 `/v1/image_generation`，旁白为 `/v1/t2a_v2`。

B3 的最小方案是保留现有目录价占额，修正文案并补充独立套餐状态。若以后要增加计费来源字段或修改作品授权合同，应先做跨模块合同复核，再实施；不将此次文档交付视为合同变更授权。

B4 可依据官方 `GET https://www.minimax.cn/v1/token_plan/remains` 或认证所有者提供的 `mmx quota`。接入前核实真实响应结构，只保留白名单字段。余额查询具有时效性，其他工具也会消耗额度，因此预检不能保证后续提交一定成功，也不替代原有执行授权。

B5 必须保留现有不确定提交保护：请求可能已被接收时，继续查询原任务或对账，不能以“换 Key”“换模型”“额度已刷新”为理由重新购买。

## 旧作品和加载顺序

1. 先核对活动作品、运行中的 Agent、未完成 Provider 任务和未知提交，确定可以加载配置的时点。
2. 在本机受保护位置备份配置；在隔离 fixture 中完成模型参数、工具回放和错误分类验证。
3. 加载文字模型配置，核对 Web 的每轮参数以及网关实际模型，不只检查磁盘文件。
4. 媒体切换前完成具体型号权益核实，记录计费来源和适用用途条款。
5. 更换媒体 Key、模型、音色或 API origin 会改变现有授权 scope。旧作品需要重新核对授权；保留原占额、真实费用、未知提交、已生成素材和验收历史，不清零或自动转授。
6. 用获授权的最小真实调用确认新配置。文字兼容通过后再按模态验证媒体，不直接启动完整视频 E2E。

回退以配置和本次代码改动为单位。新模型会话不直接混入旧模型会话；回退不删除作品、生成记录、媒体或费用账本。

## 验收清单

确定性验证优先扩展已有高价值场景，不按条目数量新增测试文件。

| 验收边界 | 需要证明的行为 | 优先复用 |
|---|---|---|
| 模型与参数 | 新模型实际请求的 ID、思考档位、输出上限正确；拒绝 disabled/none；旧模型不受影响 | `tests/test_minimax_thinking_contract.py`、现有 Web/Agent 调用 fixture |
| 工具回放 | thinking、正文、tool call、tool result 经接收、保存、修复和下一轮请求后完整；截断不得成功 | `tests/test_openclaw_authoring_boundary.py`、`tests/test_core.py`、会话修复场景 |
| 素材与额度 | 假 HTTP 覆盖 401、权益拒绝、429、窗口耗尽、未知结果；不重复提交、不静默按量回退 | `tests/test_minimax_image_speech_generation.py`、`tests/test_minimax_video_generation.py` |
| 预算与旧作品 | 目录价估算不冒充实扣；配置改变拒绝沿用旧授权；累计占额和已有结果保留 | 现有 Material integration 与 Creation delivery 测试 |
| 状态投影 | CONFIG_READY、认证通过、权益可用、用量可读与真实生成成功分开表达 | runtime readiness 与 Creator/Operator 状态场景 |
| 真实最小验收 | 单轮文字、至少一次工具调用及续接、当前需要的视觉输入；媒体按模态记录实际结果及扣额依据 | 独立具名运行记录，调用需在已授权范围内 |

纯文档交付只检查引用、内容与 diff；本方案实施时再运行对应回归。测试使用假凭证和确定性响应，不调用付费 AI、不依赖本机真实账号。真实最小验收通过也不等于 MATERIAL_READY 或完整视频交付通过。

## 建议执行顺序

**A1–A6 文字兼容 → 确定性验证 → 最小文字真实验收 → B1–B6 媒体套餐接入 → 分模态真实验收。**

最小可交付结果是新文字模型能够完成普通对话、结构化返回和工具续接。套餐用量展示属于后续素材接入的配套能力。暂不扩展新 BGM 生成、声音克隆、新素材模型或第二条制作链。

本次没有足够的真实调用证据支持承诺迁移后的速度、额度节省比例或全链可靠性；这些以相同任务的实际耗时、token/套餐用量、结果质量和干预次数比较。

## 官方依据

- [M Plan 概览](https://platform.minimaxi.com/docs/m-plan/intro.md)：Explore 覆盖范围、档位和共享能力。
- [M Plan 常见问题](https://platform.minimaxi.com/docs/m-plan/faq.md)：Key、扣减顺序、积分、限流与生产使用定位。
- [用量说明](https://platform.minimaxi.com/docs/m-plan/usage-rules.md)：5 小时和周窗口，以及共享额度。
- [Token Plan 老用户说明](https://platform.minimaxi.com/docs/m-plan/token-plan-notice.md)：升级后权益和历史优惠变化。
- [OpenClaw 接入](https://platform.minimaxi.com/docs/m-plan/openclaw.md)：新模型配置及禁止关闭 thinking。
- [OpenAI 兼容接口](https://platform.minimaxi.com/docs/api-reference/text-openai-api.md)：模型 ID、思考参数、输出上限和工具回放要求。
- [视频 V2 接口](https://platform.minimaxi.com/docs/api-reference/video-generation-v2-create.md)：H3 与 H3-Max 的 API 规格，不构成账号套餐权益证明。
- [按量价格](https://platform.minimaxi.com/docs/guides/pricing-paygo.md)：现有素材目录价估算依据。
