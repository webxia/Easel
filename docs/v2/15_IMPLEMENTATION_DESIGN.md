# S5 · 代码复核后的可执行设计

状态：**Coding 合同；实施与运行结果见[当前状态](04_CURRENT_STATE.md)。** 本文把已确认需求/职责落实为实施要求；技术依据见[选型建议](14_TECHNOLOGY_SELECTION.md)，执行入口见[实施任务包](tasks/S6_IMPLEMENTATION_PLAN.md)。文件、端点、表和命令描述合同目标，是否实现及覆盖范围以对应源码、任务卡和运行证据为准。

## 1. 复核结论与实施约束

业务基线 `easel-v2-rebuild@8eeafb6b9bf62b26e2077057cbebe45721f5d464`；本次复核起点 `codex/s5-architecture@d25b8f8395c907180738a5795042c3fe86e6de0b`，两者 easel/web/skills/tests 无业务差异。V1 只读 `57c8e2ade21af9fb6abccdab3f7ba8e50132314f`。

- 现有 `web/app.py` 已有本机写入保护、画像/附件/outputs/聊天 SSE，应保留这些边界；V2 用独立 router 接入，不继续把全部新业务堆入大文件。
- 作品记录是业务权威；框架检查点、素材库内部记录不拥有第二套确认/额度。网络和数据库不能一笔事务提交，未知结果必须独立处理。
- 执行者所有权、工作发现、外部操作幂等、版本和事务事件属于 Easel；不能宣称引入图框架即可获得生产可靠性。
- 模型主链推荐程序控制的任务 API 和工具分发，无任意 shell、文件浏览或直接媒体凭证。既有通用 Harness 保留给已有聊天；只有证明满足同样限制的接入才可参与 V2 收费制作，不默认用完整聊天会话当创作执行状态。
- 编辑器已在 S6-09 落实为本地 FFmpeg 受限时间线，版本、许可、真实能力与未覆盖项见 [ADR-S6-009](decisions/ADR-S6-009-local-editor.md)及[选型依据 §5](14_TECHNOLOGY_SELECTION.md#5-编辑渲染本地-ffmpeg-与可编辑工程)。不整体迁入 V1 native_source/service，不把 Hypit 后续接入作为当前主线前置。缺失效果明确返回能力缺口，不得擅自改为效果降级的幻灯片交付。

## 2. 建议代码组织与唯一责任

所有路径相对受测 checkout；新目录/文件由对应实施任务创建。

| 目标模块 | 写入权与主要入口 | 不能负责 |
|---|---|---|
| `easel/production/contracts.py`、`errors.py` | Pydantic 业务输入/结果、版本常量、类型化错误 | 调模型/读真实凭证/隐式写库 |
| `easel/production/store.py`、`migrations/` | 作品/修订/授权/任务/操作/事件事务，文件索引 | 跨网络长事务、模型审美判断 |
| `easel/production/service.py` | 所有用户命令、版本核验、授权追加、接受/删除保护 | 把聊天 finish 当作品成功 |
| `easel/production/worker.py`、`graph.py` | 领取持久任务、阶段路由、恢复、取消、局部任务重建 | 自己维护另一套用户额度或原始用户要求 |
| `easel/production/context.py`、`model_tasks.py` | 必要上下文、能力检查、严格结果接收、受控工具循环 | 自动加载根 AGENTS/其他画像、任意 shell、直接付费网络 |
| `easel/production/operations.py`、`providers/` | 唯一提交/观察/接收与额度准入；Provider 错误分类 | 在重试装饰器里重新生成 |
| `easel/materials/`、`easel/production/materials.py` | 迁入 V1 库内能力与新作品适配；输出素材句柄 | 回写作品接受/方案、搬旧 Creation/Delivery |
| `easel/production/media.py`、`editors/`、`quality.py` | 音轨/字幕/工程/渲染/检测适配、局部保护 | 任意素材采购、改人设/事实、隐式更换音色 |
| `web/production_api.py`、`web/frontend/src/lib/productionApi.ts` | HTTP 合同、错误映射、快照/事件游标 | 复制执行状态或授权逻辑 |
| `web/frontend/src/components/ProductionPage.tsx` 等 | 输入/方案、制作进度、预览、审阅、版本比较 | 用前端内存或模型文本推测完成 |

工具尽量复用函数/API；独立脚本用参数数组与有限环境调用，禁用 shell 拼接。新作品文件开放前，S6-02必须同时改造旧 `/api/output`、`/api/media` 的读取、下载/打包及枚举入口，拒绝生产私有根和其符号链接别名；旧output与画像DELETE也要检查引用。不能靠隐藏目录名保护数据库，也不能留下rmtree/unlink旁路。删除聊天不得经stopChat隐式取消独立作品运行。

新模块只导入配置/存储接口，不从 `web/app.py` 反向导入，避免循环依赖与启动副作用。旧聊天和 V2 不互相创建第二个生产运行。

## 3. 数据与文件合同

### 3.1 存储布局

建议生产私有根 `outputs/_production/`，其中作品数据库、WAL、框架检查点、运行工作区和内部证据不直接映射静态下载。现有_safe_output_path只保证路径位于outputs，尚不能提供该保护；S6-02必须先封闭旧读取/打包/删除入口。用户可预览/导出的成片存 `outputs/works/<work_id>/...`，由受控媒体API仅放行已登记、允许展示且作用域正确的产物。上传入口产生经校验的input_id，绝不接受前端任意本机路径。

SQLite 开启 foreign_keys、明确 schema_version 和前向迁移；短写事务、有限 busy timeout，不在事务内等待模型/网络/渲染。备份必须覆盖有效数据库与 WAL 状态，先用 SQLite 在线备份而非随意复制单文件。应用初始化不能迁入 V1 用户库或扫描历史盘。

媒体写临时文件→核验内容/大小→原子落到稳定位置→登记引用。中断留下未登记文件时对账接收或保留待清理，不再次收费生成。数据库迁移失败停止 V2 写入并报告，不能破坏已有 Easel 聊天/文件入口。

### 3.2 最小记录与不变量

ID 使用程序生成的不透明标识；时间 UTC；数据库行有 revision 用于并发核验。JSON 内容必须有 schema_version，经合同校验；既有用户路径不作数据库主键。

| 记录 | 最少信息 | 关键约束 |
|---|---|---|
| channels | id、既有 profile_ref、name、定位/偏好、default_director_revision、音色/字幕默认、archived | 引用真实既有画像；不创建另一个主人设。删除/重命名画像不得静默切换他人画像；已有作品保留快照 |
| directors / director_revisions / channel_directors | 身份、名称、风格草稿/不可变版本、参考证据、style_confirmed、trial_pending、试片、接受记录、可用频道关系 | 多对多；默认必须属于有效搭配。接受作品与接受导演为独立命令，可在同一用户交互明确提交 |
| works / work_inputs | profile_ref 可空、channel_id 可空、当前方案/运行/接受版本引用、原始输入清单、必用/参考用途 | 无画像不得读其他画像。频道与画像一致；文件引用有作用域和来源，原片不可覆盖 |
| plan_revisions | work_id、revision、完整脚本/场景/设置/事实与禁止项/适配许可、画像和导演版本依据、hash、confirmed_at | 确认后不可原地改写。摘要是同一内容派生；scene_id 不使用 Markdown 行号 |
| authorization_grants | work_id、用途范围、所绑定input/preview/plan_revision、provider及model/mode允许清单、AI补料许可、IMAGE/VIDEO累计上限、明确收费/追加记录、撤销记录 | 生产授权绑定已确认方案；规划/试听只允许具名用途。追加不重置消耗；确认方案与生产授权同事务；新作品不继承旧授权 |
| runs / tasks | run_id、work_id、kind=planning/production/revision、目标输入/方案/编辑修订、graph_version、任务种类、依赖、input_fingerprint、结果引用、状态、owner_epoch | 同作品至多一个有效执行负责方；确认前规划也持久调度，确认后从冻结方案制作，不重复规划；局部修订新run并复用有效产物 |
| operations | operation_id、work/run/task、类型、input_hash、grant、provider/model/mode与配置版本、提交身份、Provider任务ID、状态、计数分类、回执摘要 | 同一个业务提交重放返回同一操作；用户明确新生成另建ID，不能仅按相同prompt去重。旁白/模型也留操作痕迹但不占IMAGE/VIDEO额度 |
| artifacts / artifact_edges | artifact_id、类型、hash、存储引用、来源/权益、方案/工程/模型/音色等依赖、检查结果引用 | 复用必须依赖相容且文件可用；单靠路径存在不算合格。保留版本仍引用的产物不可删除 |
| reviews / acceptances | 指定output_revision、用户意见、影响范围、修改授权、明确接受的时间/来源 | 修改不会抹掉旧接受记录；accepted_output_id 与当前run状态分开保存 |
| events / command_receipts | work_id、递增seq、run/revision、kind、实际payload、actor；idempotency_key及请求指纹 | 事件和领域状态同事务；同key不同内容409；重复请求返原回执，不触发新执行 |

以上是逻辑表族，不强制每个斜杠分成独立物理表。Coding 可以合并低复杂度表，但不能移除身份/版本/权限不变量；所有物理 schema 由 S6-01 在迁移文件中一次明确，后续不得各自另建同义表。

规划模型与试听发生在方案确认前：操作引用本次创作请求已明确的服务授权或具名试听授权，不要求先存在生产方案，也不因此获得IMAGE/VIDEO生成许可。已有授权范围内正常调用不逐次询问；新收费试听或未授权服务/模式按需求说明并确认。此为权限记录，不新增用户金额预算或配音次数额度。

### 3.3 状态机

- 作品展示：discussing / awaiting_confirmation / producing / needs_decision / preview_needs_fix / reviewable / cancelled。已接受是独立记录和UI标识，后续修改不能丢失历史接受。
- 任务：pending→running→succeeded；running 可进入 waiting_external / retryable_failed / needs_decision / failed / cancelled。恢复需核对当前版本、依赖及所有权，不能直接重放所有 running 项。
- 生成操作：reserved→sending→submitted→succeeded 或 failed_after_submit；sending 断线→unknown；可证明未提交→failed_before_submit 并释放预留。submitted 后失败仍计一次；unknown 保持待核实占用，不能作为已知提交或自动退款。
- 额度显示：已用=确认实际提交数，待核实=发送结果未知，临时预留单独记账；可用=上限−已用−未知占用−未发送预留，且不小于0。查询/下载/复用不增加提交次数。并发准入在一个短事务内完成。
- waiting_external 是在途服务任务；needs_decision 是授权/实质变更；retryable_failed 是可自动恢复的具体故障。展示断连不更改这些业务状态。

重复确认、防旧版本、取消和发送争用均由条件更新/唯一约束与command receipt保证。reserved→sending的同一条件更新必须核验当前run/task修订、owner_epoch、取消、服务模式权限与额度；过期执行者不能新建操作或发送。取消确认阻止新的sending；已跨发送边界的调用如实视为在途，接管者不得重发。过期worker不能登记当前版本产物，但可按既有operation_id递交不改变原请求的回执；程序核实后收存有效结果，保留收费成果。

## 4. 模块间接口与错误

函数名是实现合同，具体异步类型由实施卡落实；任务输入仅含必要字段和稳定引用。

| 接口 | 输入 → 输出 | 关键语义 |
|---|---|---|
| WorkService.command | command_id、work/revision、用户动作 → receipt、snapshot_cursor | 创建/确认/修改/取消/接受均走此入口；已有实体必须带expected_revision，创建时为空；版本不匹配409 |
| ModelTaskRunner.run | TaskContext、task_kind、能力要求、有限工具 → TypedResult/NeedDecision/TaskFailure | 不自写状态；有效结果校验后由调用方登记；格式纠正有界，保留原结果诊断 |
| MaterialSupply.supply | scope、SceneNeed、允许来源/用途 → candidates 或具体缺口 | 只有候选；导演检查实际媒体后选择，不由搜索顺序自动选片 |
| OperationService.submit/observe/receive | 已授权需求/operation_id → 操作事实、可用产物或unknown | 只有submit能发送新生成；observe/receive不扣新次数；所有恢复先读原记录 |
| EditorAdapter.check/build/observe/cancel | versioned EditProject、媒体句柄、允许能力 → 诊断、render_job、产物 | 不携带媒体生成凭证；输入禁止未经批准的外部URI/脚本资源。未就绪返回capability_unavailable |
| QualityService.inspect | 输出产物、目标规格/约束、视听证据 → findings | finding有位置、证据、严重性、影响范围；代码检查与模型判断分开 |
| RevisionPlanner.propose | 原输出、反馈、依赖 → ChangeSet | 明确受影响场景/声音/文字/额度及需确认项；程序依赖+模型语义影响共同决定，不只按文件diff |
| ProgressQuery.snapshot/events | work_id、after_seq → 状态/成果/关键事件 | snapshot附cursor；客户端用cursor续订，事件去重并忽略旧run更新 |

统一错误 envelope：code、user_message、retryable、affected_ids、operation_id 可空、requires_decision、诊断引用。code 至少区分 invalid_input / stale_revision / permission_missing / quota_exhausted / result_unknown / material_unavailable / provider_unavailable / invalid_model_output / invalid_edit_project / quality_blocked / internal_error。禁止原始异常/响应正文泄露凭证；retryable 不直接授权重复提交。

HTTP 约定：400格式，404不可见/不存在，409版本/命令key冲突，422业务约束/能力缺口，202已接收后台命令；401/403沿用实际本机权限规则，不能另造不生效的多用户认证。所有写路由仍经过 existing local_write_guard；读媒体仍有输出路径和作用域校验。

### 4.1 HTTP API 合同

统一新增前缀 `/api/production`，交互继续由现有 Web 入口调用。

| 路由族 | 作用 |
|---|---|
| GET/POST `/channels`，PATCH `/channels/{id}` | 列表/创建/编辑/归档及默认；关联既有画像，不绑定平台账号 |
| GET/POST `/directors`，PATCH `/directors/{id}`，POST `.../revisions`，POST `.../accept` | 名称/归档与风格版本分开；参考→草稿→试片→明确接受；频道PATCH可清除失效默认 |
| GET/POST `/works`，GET `/works/{id}`，POST `.../inputs` | 作品列表含未出片/无画像作品，按状态/画像/频道筛选并以稳定游标分页；建作品、输入和快照不依赖聊天存在 |
| POST `.../plans`，POST `.../plans/{revision}/confirm` | generate建立planning run；用户明确编辑直接产生新方案修订；确认含plan_hash/授权/command_id并只创建一个production run |
| POST `.../authorization-grants`，POST `.../cancel`，POST `.../resume` | 追加/取消/解决needs_decision；resume指定解决的decision及版本，不是无条件重跑 |
| POST `.../revisions`，POST `.../outputs/{id}/accept` | 自然语言意见生成局部ChangeSet，按影响处理；接受明确输出 |
| GET `.../events?after=seq`，GET `.../artifacts`，GET `/artifacts/{id}/content` | SSE事件、成果列表和受控媒体预览；缺失cursor历史可回快照 |
| POST `.../fork`，POST `.../assignment` | 基于旧作建新作品但不复制授权；只改归属不触发重做或扩大素材权限 |
| POST `.../voice-previews`，POST `.../subtitle-previews` | 同文音色试听与真实画面字幕预览；显式保存到本片/频道/画像，试听收费遵守授权 |
| POST `.../deletion-preview`，POST `.../delete`（目标作品/输出版本），DELETE `/artifacts/{id}` | 先给精确影响和版本指纹，用户明确删除后只解除授权范围的保留引用；直接删被引用artifact仍409 |

各任务只实现其负责路由；不要先把整个API注册为空壳返回成功。当前聊天发送接口不自动变付费视频创建：用户明确视频创作意图后建立/关联 work_id，后续消息可路由到该作品；自由聊天继续原行为。

## 5. worker、模型、素材与编辑主线

### 5.1 worker 与持久编排

CLI 目标增加 `easel production worker` 和 `easel production status`；启动 V2 Web 时启用受管理worker，关闭浏览器不停止它。Web服务退出可停止本机worker并持久保存，重启后恢复；不承诺电脑/服务关机期间继续运行。显式作品取消与服务退出是不同操作。

初期一个本机worker，可在已授权任务范围内有界并发；不用 Redis/Celery。worker用数据库owner_epoch/lease领取；heartbeat只是存活线索，过期回收必须递增epoch，旧写入拒绝。进程环境不继承全部用户密钥，按适配器必要字段注入。

LangGraph节点按产物边界组织。planning run：prepare_context→plan，写不可变候选方案后结束，作品awaiting_confirmation；用户确认后另建production run：读取冻结方案→supply/select→edit→render→inspect→review，不再调用plan改写已确认内容。revision run只包含ChangeSet影响的任务。首次规划、改方案和制作中修改均有输入版本及持久任务；planning不允许生成媒体，输入改变时旧结果保留但不得覆盖当前方案。

失败返回明确子范围，生成submit不是可无条件重试的整个节点。持久run记录graph_version，重启先对账operations，恢复有效检查点；旧图版本无法安全解释时停为可诊断状态，不静默跳节点。领域记录已提交而checkpoint未提交时幂等返回已有结果；反向窗口也重新核对，不能信任checkpoint覆盖已取消授权。

### 5.2 模型与工具

V1全局Voice生成只绑定完整脚本，不能直接承担句级修改；音轨按可定位段保存文本摘要/voice身份和边界，复用未改段并复查拼接听感。

首期不要强制多Agent；相同导演规则可覆盖多个任务角色。context不从普通长会话回忆授权，也不自动拼接根AGENTS/全量history。schema/prompt有版本；输出只需创意内容、引用ID和理由，既有身份、hash及权限由程序绑定。

能力配置分别说明文本/图像/音频/视频/工具/结构化结果是否真的可用。缺必要模态返回capability_unavailable，不用抽帧冒充完整视听检查。模型调用和TTS的实际费用仍需用户授权；虽然不计IMAGE/VIDEO额度，也不能无限重试。无效输出有限格式修正；无新证据循环停止，具体上限配置可调且记录本run值，不作为新增用户额度。

可用工具白名单：查询可访问素材、查看媒体证据、读取当前工程、提出生成需求、提交受控编辑、获取操作/渲染结果。工具执行都经程序校验作用域与授权；模型本身没有通用shell或媒体Provider凭证。任何下载外部文本/参考视频的内容作为数据，不作为权限或系统指令。

### 5.3 素材与渲染

M01/02把LibraryVisibility（本机拥有者/画像可见范围）与UseContext（当前work_id和用途）分开，不能用work_id把所有库资产锁为单作品。明确可复用的同画像资产可跨作品复用，current_creation_only仍绑定源作品；无画像输入默认仅本作品，后续归类不自动扩大权限。M03/04检索/获取，M05通过OperationService准入观察。不迁V1用户库，不把旧rights结果无条件用于新用途；署名/版权证据进入最终依赖。V1测试适配路径/fixtures并保留负例意图，不复制PASS数字。

S6-07分别实现IMAGE和VIDEO的适配与能力声明，S6-10实现VOICE。未配置真实服务可先做离线协议测试，但缺失模态保持capability_unavailable/NOT_TESTED；一个生图adapter通过不表示生视频已接通。S6-09已完成本地 FFmpeg 首个编辑器决定及真实合成媒体证据，范围见 [ADR-S6-009](decisions/ADR-S6-009-local-editor.md)；S6-14继续验收完整生产能力，不暗含用样片代替未实现功能。

EditProject 保存编辑器类型/版本、可编辑工程、稳定scene_id、实际媒体依赖、音色与字幕生效值。当前 `ffmpeg-timeline-v1` 是该后端自己的受限时间线，支持实际视频剪辑/溶解、图片显式运动、独立原声/配音/音乐、固定字幕；不是要求其他引擎服从的通用视觉DSL。项目/manifest/结果hash与无字幕合成底片保留供修订和真实预览。未来更换引擎须按实际能力适配，不能跨引擎偷偷丢风格特征。

原声必用区间与生成旁白分开轨道/依赖。固定voice provider/model/voice_id及相关可用参数，缺失不静默换。字幕对实际音轨对齐并结合实际画面预览；字号是对应输出分辨率的可调整参数。当前 assemble.py 会保留显式镜头时长、缺省时借旁白推导；其默认静音/补帧及缺字幕回退需在适配时显式处理，不能照搬为产品限制。

## 6. 质量、局部修订与用户可观察性

技术检查输出可解码、音视频轨、时长/画幅、素材引用、字幕时间/范围及声音线索；语义检查基于真实视听证据核对事实、观点、风格、节奏。自动检测黑场/静音仅是线索，允许有意留白，不能为PASS删除创作。

质量记录绑定精确artifact hash与检查规则/模型版本。待修候选不能成为reviewable；新输出不能沿用旧输出PASS。机器合格和用户接受分开。审美改进建议不自动变无限阻断；缺必用内容、错误事实、不可播放等属于阻断。

RevisionPlanner输出ChangeSet：base_output、affected_scene_ids、changed_audio/text/settings、expected_new_image/video_calls、scope_expansion、new_permissions、reusable_artifacts。用户清楚授权的局部低影响修改无需二次审批；扩大范围/新增生成说明随修改确认，额度不够再追加。active run期间的新修改先形成请求，不改写正在消费的P1；确需重定向则停止新派发并保留在途结果，创建新修订/run后重算依赖。

进度概览持续显示阶段/具体动作、并行任务、成果预览、消耗/待核实、阻塞及下一步；展开输入/输出和面向用户的选择摘要，不暴露模型内部思维或凭证。事件至少包括 command_accepted、task_started、artifact_registered、operation_waiting、decision_required、revision_created、quality_result、run_completed/cancelled。模型token流不是业务事件真相；长期无更新显示最后时间/状态待核实，不模拟百分比。

## 7. UI、默认与长期资产

沿用 ProfilePage/ChatPage/OutputsPage；新增频道/导演配置与作品页由现有App路由连接。必须可无画像无频道创建。频道表示系列，默认导演是已接受的版本；跨频道同风格不复制经历。

音色/字幕按本片→频道→画像解析并在方案确认时固定，后续修改默认只影响新方案。保存到长期默认须用户明确指定作用域，不能因为本片改字号就修改频道。正式首版兼试片时同时展示两个独立接受选项，不从“接受视频”推导“保存导演”。

根据画像/频道/本次风格推荐少量可用声音，支持同文试听及服务支持的语速/情绪参数。固定音色不可用时保留原设置，说明原因并列出替代试听及收费条件；用户明确选择后建立新本片设置，不静默更换或修改长期默认。导演归档后不再用于新作默认推荐；失效默认提示选择或明确取消，已确认作品仍固定原版本。

内容库展示作品选定输出并可比较历史版，保留已有文件浏览；不将旧ready/published标签当接受状态。新作品基于旧作品时引用允许素材，但新建方案与授权。画像或频道归档保留历史引用，不让同名新画像静默占用旧身份；具体重命名/删除通过引用检查或提示解除关联，已确认快照不回写修改。

用户主动删除作品/指定历史版时，先展示精确影响和待删除版本；提交时核对预览版本，事务解除本次明确删除范围的保留引用并保存最小删除回执，再异步清理无其他引用的文件。不得删除用户inbox原件、其他作品共享资产或在途操作结果；有在途操作时延期物理清理，结果接收后对账。删除已接受版本必须明确指出接受选择也会移除；不擅自选择另一版替代。S6-02实现合同/保护，S6-12实现完整删除命令与UI。

## 8. 待落实的能力边界

依赖兼容与持久执行归 S6-04；外部 IMAGE/VIDEO 服务归 S6-07，任务化模型与实际多模态能力归 S6-08；编辑器版本/许可与纯制作边界归 S6-09；固定音色与字幕归 S6-10。未就绪能力必须明确不可用，不能用替身标记真实首版。

长片、四声音、跨题材及完整体验由[任务包](tasks/S6_IMPLEMENTATION_PLAN.md)分批实施验收；首个可播放样片不缩减 34 项需求。执行与授权遵守任务包共同约定，实际进展和证据见[当前状态](04_CURRENT_STATE.md)。

## 9. S6-14A 对话接入增量（提案，待评审，未实现）

2026-10-18 增补，关联 [S6-14A](tasks/S6-14A_conversation-integration.md) 和[交互设计](20_CONVERSATIONAL_INTERACTION.md)。以下是候选实施合同，不宣称现有 HTTP/schema 已支持；§3～6 的已确认版本、权限、引用、恢复和生产链约束持续生效。当前源码基线 `406e523c`。

### 9.1 会话、依据与命令身份

复用现有 chat session/turn/job，不建立另一套生产队列。最小增加以下逻辑记录，物理表/迁移在实施前确定并测试：

| 记录 | 最少字段 | 权威边界 |
|---|---|---|
| conversation_work_links | session_id、work_id、关联时间/解除时间 | 一段对话可关联多作品；每轮固定 work_id，切换焦点不改变已提交轮次；source_session_id 仅记录来源，不能代替多对话续接关系 |
| work_conversation_turns | turn_id、session_id、work_id、role、用户可见正文或可恢复引用、context_revision、提交状态、结构化卡片/命令引用、created_at | 只持久化本片必要交流，不搬入其他聊天/画像或隐藏思考；现有聊天转录可引用时不重复复制；解除绑定不丢已冻结方案依据 |
| creative_brief_revisions | work_id、revision、用户事实/核心观点/限制、设置建议、input_ids、每项来源引用、未决项、hash | 可由模型提出摘要，程序验证来源/作用域并保存；不是授权表或另一份 Profile。已冻结引用不可原地改写 |

Planning payload 增补可选 `brief_revision` / `brief_hash`；存在时由服务端核验并组装 TaskContext。Plan 保存其依据引用，摘要变化或新增输入使旧候选方案失效，旧确认请求拒绝。已有作品和第五轮 Plan 没有这些字段仍按原合同读取。用户显式规格继续优先；未指定项是导演建议，不能用表单初始值冒充用户要求。

每轮用户消息先持久接收，再调用聊天运行时；同 turn_id、同内容仅处理一次，同 ID 不同内容409。现有聊天 job 回放承担断线续接，刷新不重发模型请求；若模型请求已发出但结果无法核实，记录当轮待核实并停止自动重推。该聊天调用记录不等同于生产 Operation；制作 MODEL/VOICE/IMAGE/VIDEO 继续只走原 OperationService。对话授权不自动成为制作授权。

工具派生 command_id 由服务端绑定 turn_id、动作序号和请求指纹并持久保存，避免同一轮恢复再建 Work。显式确认按钮使用前端首次产生并持久保留的 command_id；超时后原样重放取回执，不能换 ID。跨存储的“聊天回执已写/业务命令未写”窗口由同命令重放收敛，不以浏览器消息落盘作为执行成功。

### 9.2 请求、工具与事件

| 接口/能力 | 现有能力 | 拟增加语义 |
|---|---|---|
| POST `/api/chat/stream` | message、persona、sessionId、turnId、attachments；后端已有 workId/workRevision/outputId 简单命令分支 | 前端连通这些字段；替换“带 workId 就 plan/revise”为作品对话适配。显式视频入口可带 `interaction_mode=video`；普通聊天的制作意图经语义提案建立草稿，不靠正则强转 |
| GET `/api/chat/jobs/{turn_id}/stream?after=...` | 既有当轮事件回放 | 回放新增作品引用/卡片事件，禁止重放时再次派发工具；不存在的 job 不触发生产 |
| GET `/api/production/works/{id}/conversation`（拟新增） | 无 | 返回该作品必要讨论及卡片引用、绑定信息、分页游标。无原聊天时仍能续接；不返回其他会话全文或内部模型回执 |
| POST `/api/production/works/{id}/conversation-links`（拟新增） | 无 | 用既有 Command envelope 关联当前会话，沿用本机写保护、可见性和版本核验；只建立关联，不启动生产 |
| POST `/works/{id}/briefs`（同 production 前缀，拟新增） | 无 | 受控保存带来源的摘要修订；更新作品修订、失效旧未确认提案；活动制作期间只保留修改建议，不能改冻结依据 |
| POST `/works`、`.../inputs`、`.../plans`、`.../revisions` | 已有业务命令 | 工具桥适配到这些入口/同一 service，使用现有 envelope；不再增加同义生产端点 |
| 确认、追加授权、取消、接受、删除 | 已有明确命令 | 首期直接由版本卡提交，不作为模型可自由调用的写工具；绑定具体版本/动作及用户可见范围 |
| GET Work snapshot + events | 已有 cursor 与 SSE | 作为卡片业务状态的唯一事实源；聊天 token/done 不能覆盖它 |

上述短路由均相对 `/api/production`，仅 `/api/chat/...` 为完整旧聊天路由。请求写入继续使用 `{command_id, expected_revision, payload}`。新 API 保持本机 Origin/Host/write guard；session_id 不是新的账户授权，不能因知道字符串而跨作用域读取附件。

作品会话工具白名单：查询本片/目录、读取已校验媒体证据、建立明确请求的草稿、登记本片附件、提出/保存创作摘要、请求完整方案、请求具体版本修订。讨论/解释只返回正文或提案。原始附件必须经现有 upload 和 ownership 校验后登记；未知使用权不能由模型填写为 KNOWN。后台每次媒体操作继续验证已持久授权，不从工具参数中的“用户同意”推导。

聊天 SSE 增加 `work_linked`、`work_card` 两种候选事件，均由程序生成；保留既有 token/question/activity/done。卡片 envelope：`schema_version, card_id, kind, work_id, entity_ref, source_cursor`；entity_ref 指向具体 Plan/Run/Task/Output/Review，不承载第二套可写状态。卡片 action 显式携带目标版本及 hash，UI 提交前读取当前快照；有冲突时失效而非自动升级用户确认。

`card_id` 由业务实体和卡片种类确定，重复事件更新原卡而不追加大量重复消息。普通聊天回放序号与作品 seq 分开存储，不比较两种游标大小。后端只有落库确认的实体才能生成可操作卡；模型 Markdown 中伪造的卡片/命令永远只是文字。

借鉴现有 video-production 的结构化问答协议，决定卡还需持有 `decision_ref`（具体 task/review）、版本、用户可见问题、选项及对应允许动作；选项 value 是程序定义的有限值，不能作为 shell/URL/任意工具参数执行。回答经 action adapter 转成现有 grant/resume/revisions/confirm 等命令；必要时连续命令分别幂等，授权成功而恢复失败时只恢复，不重复授权。沿用 QuestionCards 的呈现方式，但卡片生命期绑定业务决定，不依赖聊天流仍在运行，也不复用旧 SDK 的文件状态或 gateway question.resolve 作为作品授权。

### 9.3 当前 OpenClaw 与生产边界

当前运行设置只读核实为 OpenClaw；现有 `_production_chat_command` 绕过它直接执行任务。新适配须让其参与创作对话，并实际限制作品会话的工具与执行权限。程序在工具注册/分发处拒绝任意 shell、旧独立视频 Skill 执行及 Provider 直接调用；作品会话的执行环境不能拿到可绕过这些限制的媒体凭证。既有 worker 保有必要 Provider 配置。

受控工具桥复用 WorkService，不接受模型指定 command_id、授权、owner_epoch 或 accepted_output_id。会话与作品/画像作用域由服务端绑定。当前 OpenClaw 的按会话工具限制、上下文加载和可执行环境隔离尚未验证，列为 S6-14A 第一实施项；不能仅靠提示词宣称达标。普通非视频聊天维持原 Harness；不静默切换会话所属底座，不为接入全局关闭其他技能。若当前底座做不到，报告限制并评审替代适配后再实现。

技能复用以经审查的创作知识和受控函数/adapter 为单位；旧技能内的任意命令、独立媒体生成、发布与全局 Profile 写入不自动获得本作品授权。配置/提示词来自产品指令源，禁止加载研发 AGENTS 和 Task；六维画像的 V2 语义以正式需求为准，不能继承旧“制作忽略平台维度”而丢失用户约束。

### 9.4 恢复与验证要求

新绑定/摘要/回放信息走前向兼容迁移，历史 Work、Plan、Operation 与成功回执保持原语义；迁移只在后续实施获得相应运行授权时进行。新前端以快照 cursor 起订，重复/乱序/旧 Run 事件不覆盖当前状态；断线仅改变连接提示。

必须覆盖：多轮讨论不意外调用 Planning、明确方案请求、一次确认仅一个 Run、响应丢失重放、旧卡/双窗口冲突、暂停聊天不取消制作、删除聊天后找回作品、指定旧输出局部修改、UNKNOWN 不重发、禁止旧 Skill 旁路、跨画像/附件作用域负例。具体验收表由 S6-14A 维护，不把上述提案写成已通过。
