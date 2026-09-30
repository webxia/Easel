# Creator 工作区真实 E2E（2026-09-30）

状态：PARTIAL（制作链完成，但依赖工程修复）。仅一次新 Creation；全部制作推进从 Web 普通入口执行。

Creation：`cr_4f91858572d2458596b9218e55bfd982`；Attempt：`fa_ea632c2c1db2ab329b04c377c3b1df4e`。

创作输入：忙碌中给自己留一口气；12 秒、9:16、简体中文、彻底静音。流动水面 → 风中树叶 → 开阔天空，三句字幕为“先停一下。”“慢慢呼吸。”“再往前走。”，柔和淡化过渡。仅许可公开视频素材、不生成 AI 素材、不发布。

## 第一处失败与恢复证据

- 启动前旧 Web 进程未加载今天接口；重启服务。浏览器保留的历史作品 `cr_d4354d31817142beb3a062435904f811` 已不存在，未手工修复关联或继续它。
- 普通文字“中文短片”未自动进入正式作品入口；通过“看看能做什么 → 整片视频创作”启用后，Proposal 正式出现。首轮通用回复有内部流程文案和不准确的许可概括，未用其执行制作。
- Proposal 字面规格与输入一致，普通对话收敛方向后点击“按这个方案制作”，Preparation 自动完成冻结并进入 Planning。
- 10:47 左右 Planning 严格校验失败：`Creative Planning MaterialPlan Domain validation failed: schema:extra_forbidden`。失败 MATERIAL_PLAN.json SHA256：`df8241c33dcaff2627c67f36629d8cea51aa894d9b472bee06d3edf4a6da4cbd`。根因是 Agent 增加了 Domain 不允许的顶层 `schema`；自动单次修正仍保留该字段。
- 页面误标“素材准备失败”，内容准备仍显示进行中；根因是 Planning 与 Material 共享异常状态且没有失败阶段。
- 最小代码修复：初次与修正提示明确顶层允许字段、要求移除 schema；Preparation 记录 active_stage/failure_stage；画布区分 Planning 失败并正确显示已完成的内容准备、使用可理解错误文案。没有放宽 Domain 合同、没有改写真实产物或状态。
- 定向验证：3 个已有 Preparation / Planning 回归通过；扩展已有回归覆盖额外 schema 的修正提示和持久化失败阶段。前端状态投影通过；lint / build 通过（既有 AccountsPage Hook warning 与包体积提示保留）。

待验证：页面阶段 Retry 后的真实 Planning / Material / Authoring / Build / Review / Selected Output / Content Library。

## 内容复核与通用模式修复

- 页面“重试创作规划”成功；冻结输入、Creation 与 Attempt 均复用，进入 SCRIPT_TRUTH_REVIEW_REQUIRED。
- 主卡只支持本人审阅，委托复核只能通过高级区。将既有正式委托复核 API 动作加入普通内容任务卡；未变更审核语义。
- 实测每 5 秒刷新清空审阅勾选。修复为按 Attempt / Script SHA / Truth Packet SHA 重置；成片确认同样改为按输出名称与 SHA 重置。真实页面跨轮询勾选保持，随后普通任务卡提交委托复核。
- 素材阶段 500：`Product Library scope requires the Creation's frozen Profile`。通用画像不含 Profile，却被产品允许进入 Creation。最小修复为每个无画像 Creation 使用独立的持久化 LibraryScope，避免读取其他画像或其他通用作品的图库。原画像范围规则保持；素材、Rights、Match 与 Gate 不放宽。
- 范围隔离回归 1 passed（已有 integration 文件中覆盖相同作品稳定、不同通用作品隔离、与画像作品隔离）。lint / build 通过。

这些实际产品代码修复属于工程干预；本次不能据此宣称无救场的 AUTONOMOUS PASS。

## 检索条件失败与前序规划修复

- 通用范围修复后素材供给返回 NOT_READY，无候选。只读 product-supply.json 证明三个 Need 的 local/pexels/pixabay 路径均因 `allowed_source_kinds` 数组不可编译失败，没有发起有效 Provider 检索。普通卡错误地将系统检索失败说成用户缺素材。
- MATERIAL_PLAN.constraints 同时包含 `allowed_source_kinds: [external_stock]` 和 `must_not_contain: [...]`。最小修复为 Planning 完成前调用现有 NeedCompiler 校验；提示保留排除边界到 intent.description，使用既有 `required_source_kind=stock` 与 `allow_generation=false`。
- 已记录但不可检索的 Planning 在未 Authoring/未提交 Build 时，从同一 Preparation Retry 交回原 Director 修正，再走正式 persist/supply；不手改真实计划。明确重新进入规划核验，原冻结内容和规格不变。
- 同 Script/Truth SHA 且审阅账本通过现有完整校验时复用审阅；变更脚本重新审阅。已有 integration 回归扩展验证这两个条件。
- 普通缺口任务在没有候选时提供已有 Preparation Retry，不要求另发“继续”。
- 定向组合 5 passed；扩展的 Domain/retrieval 修正与 Script Truth 组合 5 passed。真实页面 11:13 已显示系统重写后保留完整画面边界；供给请求待观察。

工程干预记录：重启加载当前 Web 代码、修复产品代码。未手写正式产物，未调用内部接口强制推进，未绕过门禁。

## 实际素材核对与 Authoring 契约失败

- 真实供给得到 9 个 Pexels 视频候选。通过普通任务卡逐场景预览并分别提交证据：树叶候选 1、浅溪候选 3、天空候选 5；其余候选未用作覆盖。三个 Need 保留独立观察依据；未确认原声，成片冻结规格仍要求彻底静音。
- 待处理数量 3 → 2 → 1 → 0；Gate READY 后自动进入 Authoring，无需发送“继续”。
- 11:38 Authoring 静态校验失败，错误 `time:Timeline does not accept duration.`。无 Build 提交，失败隔离产物未提升。页面保留方案、脚本和素材 checkpoint，并提供“重试视频编排”。
- 根因：隔离助手无法访问安装包，任务书的“使用冻结时长”未明确 Timeline 字段；自动修正只有原错误和同一缺失契约。安装版 Hypit 0.2.7 的 timeline-author/src/surface.ts 明确只允许 id/clock/end。相邻视频路径同样缺少 Normalize/Media Item/Sequence Handoff 指导，原任务主要展示静态图片。
- 产品任务书补齐安装版 Timeline.end、视频 Normalize → Media Item、静音 stream policy、Sequence/Handoff 与 crossfade Recipe 合同。没有人工编写 SVML/SVRun，未更改冻结语义。普通 Retry 自动刷新生成任务书，再由隔离助手编排并接受完整静态校验。
- Preparation 交付原始 Agent 内部自述被直接流到聊天。修复交付通道：制作阶段只展示后端阶段结论，原始 token/thinking/question 不进入 Creator SSE 交付或断线结果；非流式同样使用阶段结论。历史聊天未人为改写。已有 API 回归使用内部路径哨兵验证不泄漏。
- 素材卡视频文案改为“素材预览/这段素材”；运行中恢复入口改为“检查并恢复视频编排”，避免声称当前请求已中断。
- 75 项 Preparation/Material integration 回归已通过；当前 Authoring/隔离边界/提案确认定向组合 26 passed；任务书刷新与 Preparation 诊断回归 4 passed。前端投影、lint、build、compileall、diff check 通过（既有 warning 保留）。
- 11:49 从普通作品卡点击“重试视频编排”，仅恢复同一 Creation/Attempt 的失败阶段。后续结果仍待验证。

### 第二次 Authoring 失败：类型链契约不完整

- 11:54 同阶段再失败：`pipeline:Normalize.source must resolve to BlobArtifact.`，Build 仍未提交。第一次补齐的视频示例错误地使用 raw media:Video 的 `.video` 引用，这是本次工程修复引入的指导错误，不记为已解决。
- 安装版 media/src/surface.ts 证明原始 Video 的 id 自身就是 BlobArtifact；Normalize 输出 `.media` 才是 SynchronizedMedia。临时静态夹具中 `source={shot.video}` 稳定复现错误，`source={shot}` 通过。
- 继续核对完整类型链：Video → Normalize → Sequence/Handoff → 中文 Typography → Film → Render。本机 `hypit check` 检查暴露 Film 同样必须含 timeline；补齐后完整组合 `ok=true`、sourceKind=author、units=2、modules=20、outputCount=9。
- 静态夹具仅用于类型合同，不是可播放视频，不写入真实作品 workspace，不执行 plan/pricing/build 或 Provider 生成。所有临时文件自动删除。
- 产品生成任务书同步修正直接 Blob 引用、Film 四个必需属性和 Typography Font/Style/Area 类型链；3 项既有 workspace/刷新回归通过，compileall/diff check 通过。后续普通 Retry 是否成功仍待真实核验。

### 第三次 Authoring 失败与契约获取根因

- 12:05 再失败 `media-track:Member does not accept for.`；Member 只有激活时点，Item 才有独立窗口。此前有限示例没有真正解决隔离助手无法获取完整正式契约的问题，不将这些重试记为恢复通过。
- 根因修复从提示片段提升为产品的契约获取边界：每次隔离 Authoring 启动前，宿主通过官方只读 `hypit vocabulary` 获取实际安装的 11 个生产组件包，按包导出 attributes/children/recipe/notes/引用类型为 `hypit-contracts/*.json`。无 Runtime、Provider 请求、Build、状态修改或额外 Agent 权限。
- 合同仅存在于私有 staging，不提升为作品产物；Actor 仍只能 read/write/edit workspace。初次、恢复和静态修复均显式读取正式合同，合同缺失时在配置/启动 Agent 前阻断。
- 本机官方 vocabulary 导出验证 11 包均有正式 Surface。20 项 Authoring 组合通过；6 项隔离边界回归通过，既有场景扩展覆盖合同先于 Agent 可读、合同不提升、合同获取失败无 Agent 调用并保留原可信产物/清理 staging。
- 没有因此启动新 Creation，也没有重做素材供给；后续同阶段普通 Retry 结果仍待观察。

## 最终制作、审阅和入库证据

- 正式安装版 vocabulary 桥接后，同一 Attempt 自动完成 Authoring 静态校验、Plan 与 Pricing；12:22 普通任务卡显示“本次制作无第三方计费请求”。通过普通费用卡批准后，仅提交一个真实 Build：`bld_20260930T042303468Z_10968E3121`。
- 12:23 导出 `final.video`，自动文件完整性、流与解码检查 PASS。播放器实际播放三段水流、风中树叶、天空与三句字幕，包含柔和转场；未出现人物/地标/工作生活情境或新增第一人称事实。
- ffprobe 只读证据：1080×1920、24 fps、12.000000 秒、6,690,890 字节。AAC 音轨是静音载体，1,153,024 个解码浮点样本的 max_abs_sample=0.0；不将“有音轨”误说成有可听声音。
- 浏览器原生控件遮罩压暗底部字幕；只读抽取编码帧确认白字清晰，原视频未修改。普通修改卡实际保存一般反馈，time_seconds=5，绑定当前 output_name 与 SHA；退回审片，没有执行新的 Authoring/Build。构图与转场的真实重做分支本次未执行，不宣称已实测。
- 12:59 普通“确认成片”记录最终审阅 APPROVED，并选择 `final.video`。内容库普通入口出现一个项目、一个成品 final.mp4，三句画面文案完整。
- 最终 SHA-256：`0f24a9123a57e46a8d14075eeed4a53ee6ec294cc610e10df790e64d1e6047a1`。内容库副本字节 SHA 与选中输出完全相同；`.easel.json.source` 绑定原 Creation/Attempt/Build/Output 与同一 SHA。
- 内容库预览原本默认显示内部路径，修复为“高级信息”折叠项。刷新后普通预览不显示路径；返回同一会话的作品画布仍显示“最终成片已确认 / 已保存到内容库”，没有重新制作。
- 桌面 1440×900 双栏、默认窄屏切换均检查；输入框保持在对话底部。临时视口已恢复。没有发布、创建第二个 Creation、手改作品产物或状态、绕过门禁。

## 最终结论与验证边界

```makefile
CREATOR_E2E = PARTIAL
FUNCTIONAL = PASS
CORRECT = PASS
CREATOR_VISIBLE = FAIL
RECOVERABLE = PASS
AUTONOMOUS = FAIL
BUGS_FOUND = Planning schema/检索合同、失败阶段误标、轮询清空确认、通用画像图库范围、缺候选无阶段 Retry、生产回复泄漏、隔离 Authoring 无正式契约、内容库预览泄漏内部路径
BUGS_FIXED = 上述功能与契约问题已修复并验证；制作回复交付隔离由确定性回归验证
MANUAL_ENGINEERING_INTERVENTION = 产品代码修复、加载代码的服务重启、本机只读诊断与静态合同检查；未人工补正式产物
FINAL_OUTPUT = final.video / final.mp4（12 秒、1080×1920、彻底静音）
CONTENT_LIBRARY = PASS
```

CREATOR_VISIBLE=FAIL 是本次整段经历的结论：曾出现内部自述/文件表、阶段误标和内部路径；修复后的展示检查不抹除已发生的问题，历史消息也没有被手工重写。初始自然文字路由、自动命名和素材要求的中文呈现仍有体验改进空间。需用户另行授权的新作品才能证明完全无工程救场；本次按约束停止，不自动开始第二个作品。

验证汇总：Preparation/Material integration 组合 75 passed；Preparation/Hypit/隔离边界组合曾为 80 passed + 1 个旧聊天诊断文案断言失败，该断言按“聊天简短结论、画布保留诊断”更新后定向 4 passed；相关 Authoring/提案与隔离定向 26 passed、正式契约接入后 Authoring 20 passed，最终变更的隔离/修复路径 7 passed，任务书刷新 3 passed。组合有重叠，不相加为唯一测试总数。前端投影、lint、build、compileall、115 项技能契约校验与 diff check 通过；既有 Hook、包体积、Starlette/httpx/anyio warning 保留。没有运行完整 pytest 套件或第二次真实 E2E。
