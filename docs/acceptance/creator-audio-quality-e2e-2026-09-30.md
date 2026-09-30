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

## 旁白试听与素材缺口显式化

- 发现普通旁白任务只要求使用权复核，没有试听入口；预览 API 也限定为图片/视频。最小修复将同一受保护的、Bundle/SHA 绑定的预览扩展到 audio，在旁白任务中加入播放器。确定性 HTTP 回归以 WAV fixture 核验当前素材可读取、错误 SHA 为 404、字节变化为 409、禁缓存；没有新增生成或改变任何门禁。
- 正常刷新后返回同一会话和“作品”，当前旁白播放器 `duration=31.932 / readyState=4 / error=null`。Creator 在本线程实际试听后明确回答“五句完整清晰，语速合适”。该结论仅覆盖当前独立旁白，不覆盖尚不存在的最终 Timeline、BGM 混音或全片节奏。
- 通过 MiniMax 官方统一条款的开放平台链接核对 `https://platform.minimax.cn/protocol/user-agreement`：9.5 允许在遵守协议条件下自主决定输出用途，1.7 对公开传播提出生成内容标识要求。具体账号是否有另行合同及是否适用于本片，已请求 Creator 确认，尚未取得回复；Rights 保持 UNKNOWN，不把付费批准当作许可证明。未登录账号、接受新协议或操作验证码。
- BGM 任务隐藏根因：UI 只用相同 media_type 的候选判断缺口，旁白及本地 MP3 因此被算作配乐“已有候选”，未考虑当前 Plan 的来源硬条件。缺口卡现在按正式来源条件展示候选存在性，实际页面显示配乐要求、图库来源与本地/开放索引不相容，以及冻结规划当前不能直接修订。Matching / Rights / Readiness 的准入仍由原后端决定；该提示不宣称素材已语义匹配，也不承诺对话可自动改写冻结输入。
- 本轮当前四条视频候选只读抽帧证据：候选 1 有操作键盘的手、候选 3 有人物及手、候选 4 有握杯的手；候选 2 为占主体的办公图表。当前集合没有窗框/户外叶子/单叶特写，未提交任何虚假的 Match 确认。抽帧保存在 `/tmp`，没有改原素材或补正式产物。
- 该补丁后 Material integration 32 passed，前端 lint/build 通过；保留既有 Hook / 包体积提示。后端仅在确认生成 COMPLETE、Build NOT_SUBMITTED、Authoring 未开始后重载，恢复页面未增加生成记录。


## 本次授权后的根因修复与素材恢复

- Creator 指示：“你先解决根因，然后本次旁白无需授权直接使用即可，要做到减负，不要太多的确认”。使用普通旁白 Rights 卡记录该声明（仅本次未发布作品），并通过正常音频匹配复核记录 Creator 已给出的“五句完整清晰，语速合适”。不接受新协议，不推定第三方账号合同，不再次调用 MiniMax。
- 新根因：TTS Asset 没有语义证据，原 Match 复核仅接受视觉 Need；Rights 通过后旁白依然被 Gate 阻断，页面却显示缺少音频并引导再次付费生成。正式复核现在接受脚本/SHA/生成记录绑定的旁白，来源修订后仅对未改变的 Voice Need 复用原记录；旁白身份错配拒绝。配乐试听另保留独立匹配审核，不能替代 Rights 或署名事实。
- 来源根因：Planning 文案把有授权素材误收窄为 stock；Preparation 来源示例又包含具体 Provider。示例来源改为空；只有用户明确限定图库时才写 stock。当前已冻结文件不手改，通过受保护普通补料动作明确选择 BGM 扩展来源，旧/新 Plan revision 留痕，脚本/场景/Handoff 不变。
- 补料根因：旧全量 Supply 丢弃集合，中间单来源 Bundle 可覆盖可信 checkpoint。当前只补未覆盖 Need，验证旧 Asset/字节/证据，保留原集合；子来源不写 canonical Bundle。独立 SupplyRun 有父记录，检索期间证据变化拒绝覆盖；请求身份持久化，完整 Supply 已落盘但 Gate 更新中断时先对账，禁止重复请求 Provider。没有调用付费生成或 Build。
- 实际普通 UI 操作：同一 Creation/Attempt，补料请求 `14a8f458-846b-4fe3-82ee-a4146ef7f97d` COMPLETE。Plan revision 从 `7bf3bf6585f9f89a61cfc15d92a7f7d92876d73632bef285f3e213b8742d0fe0` 到 `27ef6da18cf83659a32eaa76c2e00bcfd9e7e2db81758054aec3928a1c5d828a`；当前 Bundle revision `896c8f3d38c02312c02d7f346272c894ff8cd2ccb434d30a4b4925e309186f1d`。原 7 个 Asset 全部保留，38 个当前 Asset；旁白 SHA 保持 `351894790a4a181e43b58ae63c0f068c913fb4ace23728dde78bcb33b4ea8833`，脚本 SHA 保持原值，生成记录 1 次。该实际补料在最后 SupplyRun 子记录命名/父链追踪小修复前执行；父链最终行为由确定性回归证明，未为补该证据重复真实检索。
- 正常刷新、返回同一会话和“作品”后，旁白不再要求复核或生成，待处理数量从 7 降为 6。页面具备配乐播放器、试听匹配、场景素材核对、缺失署名来源事实处理入口。剩余 5 个视觉与 1 个配乐 Need，尚未提交不实 Match。配乐本地候选的署名文本存在，但来源创作者/页面与逐字 credit 的可核验条件尚不完整；仍阻断，不清除 CC BY 义务。
- 验证：此前组合 127 passed（Preparation/Material/MiniMax Image-Speech-Video/Hypit 边界）；最后音频/恢复增量 52 passed，28 deselected。包括脚本错配、未知 Rights、署名缺口可见、音频审核独立性、素材保留、父链、相同请求幂等与 Gate 中断对账。前端 lint/build、compileall、115 个技能与发布执行合同验证及 diff check 通过。保留既有 AccountsPage Hook、包大小和依赖 deprecation 提示。
- 当前结论：本次根因修复与素材阶段恢复完成；没有最终视频、Selected Output 或新增内容库。完整 Creator E2E、音画混合与全片质量保持未完成，工程介入已发生，AUTONOMOUS 仍不可判 PASS。后续真实制作需从当前任务卡继续，并保留费用和最终审片门禁。

## 配乐试听、逐场核对与自动编排

- Creator 实际试听配乐前 36 秒后回答“符合，作为当前作品配乐”。普通任务卡记录该听感：无歌词、轻柔钢琴/音垫、舒缓，适合旁白下方；没有重复费用确认或音频生成。独立素材试听不等于最终混音审片。
- 当前配乐为 Kevin MacLeod 的 At Rest，原片 206.568 秒。普通 Rights 卡根据既有 source.json / LICENSE.md 补全创作者与官方单曲来源，保留 CC BY 4.0、署名文本与许可证据；普通配乐 Match 卡记录上述 Creator 判断。未解除署名义务，署名传播到最终输出仍待验证。
- 使用只读抽帧核对现有候选，拒绝有人物/手/Logo/复杂文字的桌面素材及明显插画风窗景。通过普通 UI 分别记录五个 Scene 的独立 Match 证据：散放空白笔记本与文具；窗边空白电脑屏幕及笔记本；真实窗框、纱帘与窗外受光绿叶；深绿单叶纹理；再次回到空白笔记本与文具。同素材复用的 Scene 1 / 5 保留独立观察，不把标题或技术检查当成视觉依据。
- 限制如实记录：Scene 1 原片清晰，不具有现成前景虚化；Scene 3 室内偏暗、原片 360×640，需在最终输出检查放大清晰度；Scene 4 整体偏暗而非金黄色；Scene 2 / 4 横屏需要检查竖屏裁切。最后质量结论仍以实际成片为准。
- 第二次普通补料请求 `f4ef510a-6c7f-4ffe-8bbd-d4bd37efda9f` COMPLETE，只为未覆盖的 Scene 3 提交 `window sunlight trees` 检索提示，新增 6 个候选，保留其他已合格素材/审核与同一旁白。选用真实竖屏窗景 `asset-5f5a189ddb83442e9d0397192ea5987a`，观察 0.2～20 秒多点确认窗外叶片与纱帘轻微移动、机位基本稳定、无人物/文字。
- 17:03 普通画面核对完成后 Material Gate READY，页面自动进入“正在编排视频”，无需另发“继续”。同一 Creation / Attempt，脚本与旁白 SHA 不变，TTS 记录仍仅一次；未手改正式 Plan、Bundle、SVML、SVRun 或状态，未手工派发内部接口。当前 Authoring 运行中、Build NOT_SUBMITTED；最终视频与内容库尚未产生。

## 首次完整音画输出与局部修改

- 17:09 Authoring 经产品本机静态合同校验通过；普通费用卡显示“本次制作无第三方计费请求”。17:10 使用该正式费用卡启动本地 Build `bld_20260930T091035634Z_18426BFAB6`，17:11 自动导出 `final.video`：36 秒、1080×1920、有音轨，SHA `f42fc0195361b6f1aade63466207d0aadab9e9baedf08715a5b3cd6744d1c22d`，技术 QC pass。
- 正式输出保留 At Rest 的创作者、官方来源、CC BY 4.0 credit 与 `export_credits` 记录。这证明本次署名承载链可到导出记录，不证明片内可见署名，也不授权自动发布。
- 只读抽帧核对 0.2～35.8 秒：五个场景和完整五句字幕出现；没有人物、手或 Logo。第四场景 21～25 秒接近黑场，叶片太晚进入；根因是从该已准入原片的开头取片，而开头主体尚未完整出现。Scene 1/5 白底白字对比偏低，Scene 1 未实现前景虚化；这些质量限制不被技术 pass 掩盖。
- 音轨只读回归分析：8 kHz 单声道样本拟合已确认 Voice 与 BGM，系数约 0.996 / 0.390、残差 RMS 0.00271、整体 RMS 0.05684、峰值 0.519。支持两条既有声音实际混入且没有明显数字削波；不替代人耳判断、逐句同步或节奏审片。
- 17:15 普通“提出修改”保存绑定当前输出/SHA、21.2 秒的 composition 反馈：同一叶片素材取约 5 秒后叶纹已可见的连续区间，调整竖屏构图；保持其他场景、总时长、文字与声音，不重新请求 Provider。普通“按反馈调整构图与转场”建立同一 Creation 的修订 Attempt `fa_0d6c1185c757c7c49334ca5bda73e2d2`，复用可信内容/素材并自动开始 Authoring；新核价、费用门与最终审片仍保留。没有代码修改、手工产物或状态写入。首次输出尚未批准或入库。

## 修订失败、根因与阶段重放

- 修订 Attempt 首次 Authoring 在 17:26 返回“OpenClaw 隔离 Authoring 调用失败”，新 Build NOT_SUBMITTED，原片/素材仍保留。只读网关日志核实同一 run `9795bb5e-4399-4ef9-8262-a3b743f11d39`：17:25:22 MiniMax-M3 返回 502 HTML、一次暂态重试后 17:26:05 返回 400 HTML；不是素材或音频损坏。不能宣称已修复外部网关。
- 同期隔离草稿未提升：重新编写了其他场景、声音和字幕，BGM gain 从 0.4 到 0.28、淡入淡出改变，违反局部反馈承诺。正式流程没有针对 composition 的声音/字幕不变校验，仅提示保持不变。隔离助手还反复将目录交给 read、猜测含 @1 或不存在的合同文件，因为无目录工具且合同缺少文件索引。
- 停止该阶段后最小修复：安全失败类别/退出码，不泄漏模型输出/凭证；只读合同 index.json 与正确文件名；局部编辑提示保留组件 ID 与原音轨；提升前、Authoring 完成及 Plan 前校验原 checkpoint fingerprint 和声音/字幕依赖图，拒绝改变来源、增益、淡入淡出、时序或文字。没有手工改实际媒体/生产产物/状态。
- 验证 79 passed（Authoring 隔离、Hypit、Material integration）；实际修订继承的可信源图与原片一致，校验通过。compileall/diff check 通过。17:36 在确认无运行中编排/合成后重载服务，首次页面动作因连接失效未派发，显示最后可信失败；刷新返回同一会话和作品，17:38 正常“重试视频编排”恢复同一修订 Attempt。

## 截取范围根因与失败 Build 恢复

- 前一补丁 `c3e2b0a0` 已推送。修订重放只改 Scene 4，声音与字幕依赖图保持原值；原 static check 自动修正了把 trim 写在 Item 属性的问题，17:48 通过，正式核价仍无第三方媒体计费请求。17:49 正常费用卡提交 Build `bld_20260930T094944019Z_2541159AB6`；引擎确定失败：`Media layer content.trim is outside its source`，没有新导出。
- 真实根因：原片约 27.605 秒，Normalize Clock 24 fps，但 appearance recipe 写 `trim-start:300 / trim-end:780`，相当于 12.5～32.5 秒，超出原片标准化范围（663 帧），且不是请求的 5～13 秒。语法和 Plan 没有执行此媒体范围检查，错误直到 Build 才发现。已核对安装版 0.2.7 `media-track/src/author.ts`、`sampling.ts` 和 `media-execution/src/execute.ts`：trim 是 appearance recipe 的成对整数帧，按 Normalize 时钟计算；视频 span 使用正向取整总帧数。
- 最小修复：对当前准入视频的实际时长、Normalize Clock、局部 recipe 的整数帧范围作合成前检查，提升前/Authoring/Plan 均核验；指令明确秒转帧和 recipe 位置，不猜 60 fps。实际无效源只读检查即被拒绝，未改原 SVML。Creator 页面将该引擎错误译成可理解的截取范围说明，隐藏内部 producer 路径。
- 已失败 Build 的恢复保留 Truth/Material，复制来的编排若不合格则停为 `AUTHORING_REPAIR_REQUIRED`，不宣称完整 checkpoint READY，不开放 Plan/费用/Build；原源码 fingerprint 未变且 Authoring 全部检查通过后才提升 READY。同恢复请求不覆盖修复中的文件；原 composition 反馈保留。扩展已有恢复 integration 证明此路径不重新 Supply、不再 Build、费用未批准、复制/修复中不能核价提交。
- 83 项 Authoring/Hypit/Material 定向回归通过；lint/build/compileall/diff check 通过，保留既有 Hook、包体积和测试依赖弃用提示。确认无活动编排/合成后重载。18:15 普通“从视频制作阶段恢复”建立同一 Creation 的 `fa_4839c063b5849993dcd0720b965bc41e`，当前 MATERIAL_READY、AUTHORING_FAILED、AUTHORING_REPAIR_REQUIRED、NOT_SUBMITTED，范围拦截按预期生效；18:16 普通“重试视频编排”从此检查点开始修复。新成片与内容库尚未完成，本轮工程介入继续记 FAIL。
