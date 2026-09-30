# Creator 自主性与音画质量 E2E（2026-09-30）

## 本轮范围

只创建一个作品，从普通 Conversation 开始，目标 36 秒、9:16、1080×1920、5 个 Scene、普通话真实旁白、真实无歌词 BGM，沿用清醒备忘录风格；最终审片并进入 Selected Output / Content Library。不发布。不手改生产产物、状态或数据库，不绕过 Gate。

上一轮 12 秒静音作品不作为本轮验收证据。

## 首个现场与根因

- 新对话提交《把注意力放回当下》的完整短视频请求后，页面没有作品画布或 Creation 绑定，标题错误地显示“不要发布”。助手回复把新委托说成“继续推进”，展示 `_chat_bindings.json` 和旧作品内部 ID，并开始盘点环境。已点击正常“停止生成”，当前回复显示“已停止”；尚未确认制作或提交 Build。
- 当前代码证据：ChatPage 新会话 capability 默认为空；`_prepare_chat_request` 对 capability 空值直接走通用助手，不识别明确整片制作请求。助手因此未收到 Proposal 专属边界，正式方案流程未建立。不能通过手动补产物补救。
- 最小修复：服务端把明确整片制作委托路由到既有 ai-film Proposal；脚本、剪辑、分析和咨询保持普通聊天；收到正式 Creation 事件后前端持久化 ai-film 标记。结构化确认门、制作主链和素材/费用门禁不变。
- 定向验证：`tests/test_chat_capability.py` 18 passed，覆盖自然语言路由、非整片请求、重复请求复用同一 Creation、无 Attempt 与无制作派发。前端检查另记完成结果。
- 本轮已经发生产品代码修复，AUTONOMOUS 不可判 PASS。旧回复保留现场，不修改聊天历史。

## 后续现场

- 路由修复后通过同一聊天“重试”建立唯一 Creation `cr_046bb34c26a7444f9fd335c991ec1cc4`，风格 `clear_memo_video`、无 Profile。前端 lint/build 通过，保留既有 Hook/包体积警告。
- Creator 选择“看窗外一片叶子”，通过对话改为非个人经历的五句完整旁白，保留 36 秒、5 场景、字幕分句、无单帧闪烁、无 Logo/人脸/主体裁切。普通画布“按这个方案制作”后，正式规格冻结 `duration_seconds=36 / aspect_ratio=9:16 / audio_mode=mixed / language=zh-CN`；Attempt `fa_ed1106b7ca2ca9d1e805a68dd599e6e4`。
- 14:12 页面正式显示“创作规划遇到问题”，有阶段级重试和保留结果说明，无 Build。实际错误：五个视频 Need 的 `modality_spec.video.duration_seconds:extra_forbidden`。未修改任何实际 Planning 文件。
- 根因：Planning prompt 只枚举部分模态字段，视频合同没有完整交付；已有单次修正同样缺漏。最小修复让初次与修正请求共用 `MaterialPlan.model_json_schema()` 的当前完整 Domain 合同，明确时长意图写 `duration_hint.target_seconds`，严格验证不变。扩展既有回归覆盖该非法视频字段，并核对初次/修正都收到完整合同。
- 本轮已发生两次产品代码修复及服务重载。自主性结论仍为 FAIL，不能以恢复后成功掩盖本轮工程介入。
- 规划修复 5 项定向回归通过。Script Truth 通过普通 UI 的“记录委托复核并继续”记录为 `DELEGATE_REVIEWED`（7 条），非本人审阅、非来源事实；然后自动进入素材准备。
- 逐场候选审阅发现桌面视频中实际有手/人物（候选 1、2、4、6、10），不能满足当前 Need 的无手/无人物条件；叶子候选也不能冒充有窗框的 Scene 3。尚未提交任何视觉匹配确认。预览不是最终成片。
- 普通作品区旁白任务缺失的根因是 UI 硬编码 `voice_narration_global`，本轮 Director 正式生成 `voice_narration`。修复根据正式 Need 的 audio/voice 类型和生成许可识别，保留原生成 API、计费确认、Rights 与 Readiness Gate。真实页面刷新后“任务：准备整片旁白”显示，含证据/未知/费用边界，且高级信息折叠；lint/build 与前端投影通过。
- BGM 原搜索词含整个混音/时间线说明，Openverse 返回 0 候选；只读诊断 `piano instrumental` 返回 20 个（不下载、不入库）。Compiler 根据正式 BGM instruments 构建简短音色查询，保留完整 Need 和原过滤约束；5 项 compiler 回归通过。索引候选仍需正式 acquisition、检查、Rights/Match，不能当成已准入素材。当前 Plan 的 BGM `required_source_kind=stock` 还与 Openverse `open_license_index` 及本地素材来源不同，未放宽或改写该条件。
- 用户在本线程明确授权当前五句旁白的一次 MiniMax TTS，预期费用限 1 美元。官方价格页 `https://platform.minimax.cn/docs/guides/pricing-paygo`：speech-2.8-hd 3.50 元/万字符，汉字 2 单位。本脚本 133 字符、估算 241 计费单位，估算 0.08435 元人民币；已核对现有预置音色，不涉及设计或克隆。尚不代表账号实际结算证据。
- 普通“生成旁白素材”已打开原生计费确认框，浏览器工具无法操作该原生框；Codex 原生窗口控制被工具拒绝。未尝试绕过或重复提交；只读 generation-runs 为空。已请求用户在该同一确认框点击确定，计费请求是否实际提交仍待核实。此为工具操作限制，不伪称 Easel 制作失败。

## 一次 TTS 的结果与后续根因修复

- 后续普通页面与正式记录确认这一次生成已完成：`gen-3a8b8b47-46e4-472e-8236-5c3bebcb9aa9`，仅一个生成记录，当前脚本哈希与输入一致。未重发请求。音频技术检查通过；独立 ffprobe 核对 MP3 / 32 kHz / 单声道 / 31.932 秒。计费记录仍为 UNKNOWN，不能把官方单价估算当成实际账单，也不能把技术检查当作完整试听通过。
- 生成后的画面候选从 10 个降至 4 个，页面短暂报 `Material Rights candidates require the current Plan and Gate Bundle`。根因：`generate_minimax_asset` 在生成成功后调用整轮 `ProductMaterialSupply.run`，重新搜索/获取所有 Need，并替换 Bundle；逐来源 Supply 的中间 Bundle 还会使刷新读到暂时不一致的 Gate。原资产文件仍在，原 Bundle 的集合和证据没有按 checkpoint 保留。
- 最小修复：生成前校验当前 Plan revision / Bundle / Gate；生成完成后保留原集合与素材记录，只加入这一次新 Asset，本地重新执行原 Matching / Readiness / Gate，并保存 parent SupplyRun。生成期间若 checkpoint 或资产记录变化，保留生成结果并停止，不覆盖新状态、不重新付费。没有改变 Rights/Match/Readiness 冻结语义，没有加入第二条供应链。
- 扩展既有 Material integration 场景，断言生成与 Rights 复核都不查 Provider、原 Asset 完整保留、新 Asset 使用原 Bundle identity、SupplyRun 绑定父记录、未知 Rights 仍 NOT_READY、核验正式证据后才进入生产准备。Material integration 与 MiniMax Image/Speech/Video 合同共 42 passed；自然对话/Compiler/Preparation 共 68 passed。均为确定性 fixture，不请求真实 AI。compileall 与 diff check 通过；前端 lint/build 在此前界面修复后通过。
- 普通页面“重新检查进度”后状态读取错误消失，旁白使用权任务仍待核验，作品仍有 7 项素材缺口。没有再生成音频，没有确认不合格候选，没有提交 Authoring/Build。

## 当前验收边界

本轮尚无最终视频、Selected Output 或内容库记录。不能验证音画混合、剪辑节奏、转场、最终裁切或整体风格。AUTONOMOUS / CREATOR_VISIBLE 已因本轮工程修复及首次内部回复泄漏失败；其他尚未完成的端到端指标保持未验收。BGM 来源约束与现有供应渠道不一致、场景候选不完整，以及当前冻结规划缺少普通路径的脚本/素材需求修订，仍需解决；不能通过手改 Plan、重复付费或放宽 Gate 强行完成。
