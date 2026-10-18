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

<a id="9-s6-14a-对话接入增量提案待评审未实现"></a>

## 9. S6-14A 对话接入合同（A1隔离验证，A2～A5待实施）

2026-10-18 研究修订，关联 [S6-14A](tasks/S6-14A_conversation-integration.md) 与[交互设计 §4.4～4.6](20_CONVERSATIONAL_INTERACTION.md#44-openclaw-研究结论与方案选择)。研究基线 `bac81d99`；成功生产源码仍为 `406e523c`。A1 已实现并隔离验证原生插件、3个工具与未挂载的内存绑定适配；[任务卡](tasks/S6-14A_conversation-integration.md)记录证据。下述正式持久绑定、全量工具/字段与产品入口仍待 A2～A5；不得直接启用内存探针为正式服务。§3～6 的生产身份、版本、授权、引用、恢复约束持续生效。

### 9.1 最少持久化与命令身份

不再把早稿中的三类逻辑记录直接当成三张必建表。优先扩展/引用现有 chat session/turn/job、服务端转录、Work 快照、task payload 和 command_receipts；确需独立持久化的绑定与映射由 A2 设计迁移。

| 必须可恢复的信息 | 最少候选字段/存放原则 | 权威边界 |
|---|---|---|
| 运行与作品关联 | UI session、runtime agent/session key/session UUID、运行段、当前 Work、历史 Work 关联、撤销时间；服务端持久绑定 | 同一 UI 对话可以有普通/视频运行段；每轮只绑定一个 Work/Output。session 字符串不是账户授权 |
| turn 接收与工具映射 | turn_id、规范请求 hash、固定目标/版本、接受/派发/完成/待核实状态、toolCallId 别名、动作/参数指纹、command_id、结果引用；扩展现有 job 信息 | 防止重复聊天调用/建作品；不是第二套 Run/Operation 存储 |
| 创作依据与卡片索引 | brief revision/hash、用户事实/要求/导演建议及来源消息引用、input handles、未决项、实体/卡片引用；正文优先引用现有转录 | 不复制全量历史或隐藏推理；被 Plan 引用的依据须独立保留，删聊天不破坏方案证据 |

turn 在调用 OpenClaw 前持久接收：同 ID/同请求返回已有 job/回执，同 ID/不同请求409。当前 supervisor 的事件文件可回放，但新 POST 会重建事件文件，**不能据此宣称入口已幂等**。若聊天请求已发出而完成状态未知，标记待核实，不自动重发到 HTTP 或 CLI。

每轮固定运行绑定、作品/输出、Profile/Director 及观察到的版本。沿用会话锁，增加跨进程可恢复的活动 turn 校验；晚到工具不借用下一轮目标。插件从可信 toolContext 取 agentId/sessionKey/sessionId，execute 取 toolCallId；Web 以持久绑定解析 turn 和范围，不接收模型指定 turn_id、command_id、授权或 owner_epoch。

**必须区分同一会话的不同运行**：tool factory 的 session 上下文没有 Web turn_id，不能每次按“该会话当前 turn”猜归属。A1 使用 before_agent_run / before_tool_call / agent_end 的混合插件入口；sessionKey由宿主预留，原生session UUID首次从可信钩子绑定并在后续核对，本版本HTTP请求头 x-openclaw-session-id 未被采用，不能以客户端计算值替代。正式持久合同：Web 在派发前预留 invocation；原生 run-start hook 以可信 agent/session/原生 runId 原子认领该预留，取得只绑定此 invocation 的内部引用；before_tool_call 以 runId + toolCallId 建立执行关联，execute 只使用该关联。引用不经过模型参数，结束/撤销后晚到调用拒绝。前一派发未知或取消后尚未确认原生结束时，不允许新运行认领其预留。全局 raw stream 的首事件闩锁只能用于展示，不能作为授权证据。原生运行指 OpenClaw runId，与生产 Run ID 分开。若 A1 无法证明该生命周期关联，接入不通过，不能仅靠 sessionKey 或提示词补齐。

同一 turn 内串行成功的自身命令可用已持久回执更新观察版本；外部冲突仍须停止并刷新，不能自动改版本重发。

工具映射以已接收 turn + 具名动作 + 规范参数指纹定位持久意图，记录 toolCallId 别名并产生稳定 command_id；重复同意图返回原回执，不因 toolCallId 改变再建 Work/Run。同一轮确有不同输入通过不同指纹区分。已有 WorkService command_receipts 保持最终业务幂等；映射已写/业务未写的窗口，用同一命令收敛。响应丢失不自动换 ID，409也不自动更新版本后重发。

前端确认/授权/取消/接受命令首次创建 ID 后持久保留。grant 成功而 resume 响应丢失时，只查询/重放对应 resume，不重复授权。聊天 token/done 和浏览器消息落盘都不等于制作完成。

### 9.2 具名工具、内部转发与现有 API 映射

推荐插件 ID `easel-work`，工具名如下；A1仅实现 context/create_draft/request_plan 三个，其余待A2。插件未安装到正式运行环境，每个工具的业务字段合同持续有效。每个工具只接受其业务字段，不暴露任意 HTTP URL/path、SQL、shell、Provider 参数或自由 action 字符串。

| 工具 | 模型可给的业务参数 | 程序补齐/核验 | 复用的现有能力 |
|---|---|---|---|
| easel_work_context | 所需上下文类别 | 绑定作品/所选画像/导演、允许知识与最新可见快照 | Work snapshot、目录和既有画像读取；输出经过字段裁剪 |
| easel_work_input_evidence | 当前允许的 input/attachment handle、必要媒体区间 | 归属、范围、来源与证据状态；不接受任意文件路径/远端 URL | 既有输入/媒体元数据与可用分析；没有证据时明确未分析，不宣称自动转写已支持 |
| easel_work_create_draft | 标题、主题、用户提出的设置建议及来源 | 本轮明确视频意图、当前绑定、合法字段、幂等 ID | POST /works；创建后服务端原子/可恢复地保存关联 |
| easel_work_register_inputs | 已上传句柄、必用/参考建议、用户明确的原声设置/使用权依据 | 上传会话、路径/hash/symlink、权益；有活动 Run 时拒绝 | POST /works/{id}/inputs |
| easel_work_update_brief | 有来源的创作依据变更与未决项 | 来源属于本片；用户要求与模型建议分开；实质变更使旧提案不可确认 | 必要新增：受控 brief 保存；不启动模型/制作 |
| easel_work_request_plan | brief 引用、明确规划请求、用户反馈 | 当前版本、冻结 brief/input 引用、真实规划授权；禁止工具自造 services grant | POST /works/{id}/plans；原 MiniMax Planning |
| easel_work_request_revision | 当前允许的 output handle、反馈/保护项/明确区间 | 原输出属于当前 Work、允许影响与既有授权、稳定命令身份 | POST /works/{id}/revisions；沿用影响分析与复用 |

上述路径相对 `/api/production`，继续使用 `{command_id, expected_revision, payload}`。只读查询可取新快照；写入必须针对固定/明确更新的版本，不能在冲突后悄悄接受新版本。create 不允许模型重新指定另一画像；改变当前画像/导演通过 UI 或明确的版本化设置动作。

**进程间转发**：A1已提供未挂载 router 的 claim/prepare/dispatch/end 四个固定入口，位于 `/api/chat/work-tools/`；正式 Web 未接入。插件以固定具名动作、可信运行身份、已绑定 invocation/原生 runId、toolCallId 和 schema 参数转发；服务端调用同一 WorkService/只读目录，不复制路由或生产逻辑。插件工厂可按 agentId/绑定状态返回工具或不注册。转发只返回结构化回执、业务引用或已验证缺口；作品卡由 Web/业务投影生成，不信任模型自写卡片。

该内部入口须使用独立、最小权限的插件服务凭证及本地传输限制，凭证留在插件/服务端，绝不成为模型参数或工具结果。只允许本入口的有限动作，不允许该凭证调用 confirm/grant/accept/delete 或任意 Web 路由。现有浏览器 Origin/Host/local-write guard 保留；需要独立入口鉴权时做精确路径策略，不能全局放行无 Origin 请求或伪造浏览器 Origin。插件是可信安装代码，不抵御恶意本机运维者；sessionKey 由可信运行时提供而非浏览器或模型声明。

### 9.3 前端请求、依据与事件增量

| 入口 | 复用/拟增加的具体语义 |
|---|---|
| POST /api/chat/stream | 保留消息/附件/turnId；workId 不再短路为 plan/revise。服务端校验运行与作品绑定，先记录 turn 再派发；interaction_mode=video 为入口提示，不是权限证明 |
| GET /api/chat/jobs/{turn_id}/stream | 复用已有回放；重连不执行模型或工具；增加引用事件 |
| POST /api/production/works/{id}/conversation-links（拟新增） | 用现有命令 envelope 关联当前会话并保存运行绑定/关联来源；已有本机可见性、版本和会话访问校验继续有效。绑定不启动生产，不能靠知道 session 字符串跨范围取附件 |
| POST /api/production/works/{id}/briefs（拟新增，工具内部调用同一 service） | update_brief 保存带来源修订；解释不变更，实质变更失效旧提案。活动制作期间仅暂存建议，不能改变冻结依据 |
| GET /api/production/works/{id}/conversation-context（拟新增） | 返回恢复所需的绑定、brief、必要可见消息/来源索引和业务卡引用；不新建全量聊天查询系统，不返回隐藏推理/其他会话全文。先用现有 snapshot/转录可得数据，缺失时再补此投影 |
| 现有 confirm/grant/resume/cancel/accept/delete | 只由明确业务卡操作提交；不注册为模型自由写工具 |
| 现有 Work snapshot + SSE | 卡片状态唯一来源；与聊天流独立；复用 cursor、实体引用及既有媒体接口 |

brief 需要时增加 `brief_revision/brief_hash` 引用，由服务端验证消息来源、输入句柄和版本。Planning TaskContext 只得到必要结构化依据及来源，不得到完整聊天。Run/Plan 保留所用依据快照，不原地改写旧冻结引用；旧第五轮记录没有这些字段仍按旧合同可读。当前 request 文本可承载整理后的依据，但不足以单独实现来源验证、冻结和失效，因此不能把本增量说成完全零后端改动。

跨会话附件检查从“必须等于 Work.source_session_id”细化为“上传来源属于已校验的当前关联会话，且句柄/路径/hash满足该来源作用域”；保留来源 provenance，不覆盖原 source_session_id，不扩大到其他关联会话的任意文件。主动切换当前 Work 不转移已提交 turn 的归属。活动 Run 期间的新附件只留在会话待登记区，不能自动 cancel。

聊天 SSE 候选新增 work_linked、work_card，保留 token/question/activity/done。作品卡片 envelope：`schema_version, card_id, kind, work_id, entity_ref, source_cursor`；entity_ref 指向 Plan/Run/Task/Output/Review，kind 只允许程序定义枚举。未有Work的目录创建提案及其持久卡合同见§9.9，不能强造Work或伪造Work cursor。card_id 按实体和种类稳定生成；重复更新原卡。操作带具体版本/hash，过期卡409并提示刷新，不自动接受新版。

聊天事件序号与 Work cursor 分开。QuestionCards 可复用呈现；制作决定卡包含具体 decision_ref、有限合法动作和目标版本，生命周期绑定业务记录，聊天 done 后继续显示。gateway question.resolve 只回答创作澄清，不写制作授权。卡片恢复由快照投影完成，不要求后台主动再次调用 OpenClaw。

规划无授权时复用现有 needs_decision 与 grant/resume：不发送外部请求；卡片显示实际所需服务/用途，由用户操作提交。已有有效规划授权不重复询问。确认完整 Plan 时一次授予本次制作所需的既有服务与次数，之后只在实质缺口/扩大影响时出决定卡。

### 9.4 OpenClaw 运行配置与上下文合同

首期推荐同一现有 Gateway 中新增内部 `easel-video` 配置（待实施、待验证）；不是新产品人格、模型替换或 Agent 委派。HTTP 目标 `openclaw/easel-video`，session key 固定 `agent:easel-video:<runtime_session_key>`。A1 已验证 HTTP/CLI 共用同一原生会话和绑定；正式问题桥、历史解析、会话重置仍须接入同一持久绑定；不能一条路径回 main。外部派发结果不明时禁止切换 CLI 重发。

新视频对话从首轮使用受限配置。普通 main 对话进入视频创作时，在 UI 明确进入作品模式并开启受限运行段，保留原 UI 会话及本片必要可见内容；不复制 main 原生内部转录、秘密、工具执行上下文。两段历史按运行绑定分别读取。同一运行段内不因卡片选择切换到另一 Agent。切换到新Work或另一Profile时沿用同一受限Agent配置，但必须新建原生session/运行段；不把上一个Work的原生转录继续用于新作。返回原Work可恢复其匹配运行段，失效时只带允许的可见依据另开段。目录设置阶段向它首次创建的同画像Work绑定可以保留该段，绑定转移须持久、幂等且无旧调用在途；不能将已有Work的段重新绑定给另一Work。普通 Easel main 功能继续使用其原配置，内部配置不可用时只拒绝作品动作。

配置使用严格工具 allowlist，仅加入上述作品工具和已验证安全的创作澄清能力。不得继承 coding profile 中的 exec/read/write、浏览器、任意网络、直接媒体生成、会话委派、发布或长期 Profile 写入。工具策略按本机实际版本核实合成后的结果，不套用旧模板。受限工作区不运行现有全量 sync，而只装配产品指令与审查后的知识；画像/目录/素材经服务端 scope 投影提供。启动文件、自动记忆、slash/管理命令与媒体自动处理也需验证，不能只检查模型可见工具名。

不宣称另一个 Agent 配置天然提供 OS/凭证隔离：Gateway/插件代码仍属于可信宿主，聊天模型需要其自身凭证，可能存在默认授权读取。模型没有访问原始凭证的工具或上下文，制作授权仍由 Worker/Operation 程序检查；不能用 prompt 安全声明替代执行证据。首期因运行/turn 关联需要生命周期与 before_tool_call hook，使用 definePluginEntry 等支持工具+hooks 的混合插件入口；tool-only defineToolPlugin 仅作为工具接口参考，不能宣称它支持任意 hooks。缺插件/缺绑定/身份不符/权限核验失败时阻断，不回退宽权限 main。

### 9.5 候选实施落点与最小纵向切片

A1 已创建插件、easel/work_bridge.py 和隔离探针，均未在正式入口安装或挂载。下表其余正式落点仍为候选：

| 落点 | 改动范围 | 复用边界 |
|---|---|---|
| agents/plugins/easel-work/（A1已有） | 原生工具 schema/factory、run生命周期/tool-call关联、固定本地转发、回执转换 | 使用已安装 OpenClaw SDK，不引入生产/重试状态机 |
| agents/ 下受限产品工作区装配（拟新增） | 从权威产品人格/知识源选择并固定版本，配置原生工具白名单；不运行全量 sync | 不复制一套主人设；正常 main 同步不受影响 |
| web/app.py 与独立薄接入模块（拟提取） | 替换 workId 短路；运行绑定/turn 接收/固定转发鉴权；统一 HTTP/CLI/问题桥/历史路由 | 沿用聊天 supervisor、流式和会话锁，不另起服务 |
| easel/production/service.py、store 与 planning.py | 绑定与依据保存/引用、跨会话附件检查、生成 Plan 时携带依据；必要 schema 迁移 | 原命令准入、Operation、Worker 和成功生产步骤保持职责 |
| web/frontend 的 ChatPage、ProductionPage、store、api/productionApi | 共用业务组件、作品绑定、持久卡/详情、旧卡冲突、独立作品 SSE、稳定 action ID | 同一 Work 快照与既有 artifact/版本/接受接口 |

第一条纵向切片只证明：进入视频模式 → 连续讨论两轮 → 明确整理方案 → 插件收到可信上下文 → 薄适配调用假 WorkService → 返回稳定回执 → 卡片从快照更新。随后加缺授权、插件停用、重复/未知请求、旧卡和越权负例；通过后再扩大到完整 A2～A5。真实生产不参与这条可行性验证。

### 9.6 验证、兼容与回退

A1 已在临时配置/工作区和假聊天模型/临时 WorkService 下验证下列核心项，证据见任务卡；正式产品入口仍须执行同等检查：指定 Agent/session 真实一致、原生 run 与 Web invocation 可可靠关联、晚到调用拒绝、实际可用工具只有白名单、可信身份可取、插件鉴权拒绝伪造/越权、禁用插件或绑定失效不回退 main；负例含 shell/别名/直接 Provider/文件凭证/研发指令/其他画像/自动记忆/内建命令。源码可行性不等于这些测试通过。

A2 验证同 turn 同内容/不同内容、同工具意图不同 callId、提交后响应丢失、晚到工具、双窗口/旧卡冲突、跨会话附件合法续作与越权拒绝、brief 来源/更正/失效以及旧 Work 兼容。A3/A4 验证聊天 done 后决定卡可用、关页后继续制作、删聊天后业务依据和版本仍可恢复、指定旧输出修改、UNKNOWN 不重发。

迁移只在后续实施范围授权内运行，当前成功作品、Operation 回执和 Creator 接受状态不改变。回退时停用新入口/插件，保留主聊天、旧作品读取和所有证据；未知已派发请求先核实，不通过降级入口重跑。A5 先做离线完整交互；真实模型/媒体与服务安装重启需对应授权，软件/Web/真实生产/Creator 接受分列记录。

A1 新增运行就绪合同：Gateway /health=200 不证明插件已就绪。宿主派发前通过受 Gateway 认证保护的 GET `/plugins/easel-work/status` 核对协议、Agent 与工具清单，缺插件/不兼容返回不可用，不发起模型调用或回退main；该检查是插件存活证据，实际合成权限仍由运行时用例验证。内存 invocation/ticket 及测试驱动的意图 allowlist 只用于 A1，A2 必须持久化并接入真实用户意图/来源，不把内存丢失当可安全重发。

### 9.7 交付闭环与长期回写（补充提案，未实现）

2026-10-18 用户补充要求核对 Easel 原生完成/回写设计。行为与来源分析见[交互设计 §10](20_CONVERSATIONAL_INTERACTION.md#10-创作结束后的闭环与回写2026-10-18补充设计)。本节是后续增量合同，不更改 A1 的3工具/内存探针，不宣称已接通长期写入、发布或归因。

**现有权威与投影**：Artifact/QC/Run事实、reviews、acceptances/accepted_output_id、频道/导演版本继续由现有生产库维护；旧内容项目由 `.easel.json` 展示头/steps维护。内容库在现有 OutputsPage 中分别读取目录树与production/library。V2卡片/跨层交接按“实际产物引用+必要结论”生成，不将Run成功写成accepted/published，不把metadata/聊天或OpenClaw全局MEMORY作为新的授权/接受权威。

| 触发 | 复用写入 | 补充合同 |
|---|---|---|
| 真正产物/QC/运行终态 | 原 Artifact/quality_checks/Task/Run/event | 完成摘要和卡片只做投影；索引/封面失败独立补建，不重跑生产或再付费调用模型 |
| 明确修改某成片 | 原 reviews + revise | 引用具体output_id/基准digest/反馈；未要求修改的闲聊不自动开启revision |
| 明确接受某版本 | 原 acceptances + accepted_output_id | 已接受库读取选择，而非最新文件；Creator人工确认不篡改semantic not_tested记录 |
| 建议长期保存 | A2持久对话/卡片中的必要提议引用 | 程序保存模型提出的候选，不修改长期目标；只有有用的1～3条；没有就不提议 |
| 明确保存长期项 | 现有Profile文件编辑、频道设置或Director版本机制的受控适配 | 必须绑定目标版本/差异与来源，一次明确操作对应一个确定写入，模型不直接执行全局文件写 |
| 明确另行发布/查询复盘 | 原publisher、calendar/publish-log、data-tracker/归因脚本 | 另行任务/授权；保持具体成片、平台账号、真实回执与分析来源关联；本轮仅定义衔接 |

**长期提议的最少逻辑信息**：`proposal_id, work_id, output_id?, source_refs[], target_kind, target_ref, target_version_or_hash, entries[], proposed_patch, patch_hash, status, applied_receipt_ref?`。source_refs指向本片可见用户消息、Review、明确接受、实际发布/指标/报告；entries区分用户明确要求、观察、建议和待验证推测。不保存隐藏思考或全量转录。提议由会话适配接收结构化候选并验证来源/目标，模型正文中的“记住/已保存”不构成写命令；如需模型工具也仅能创建提议，不能应用长期变更。复用A2持久卡/依据记录；是否独立物理表在实施时确定，不先新增学习Agent、后台模型任务或通用记忆数据库。

- `target_kind=profile`：绑定明确的Profile ref，只允许本次提议显示的style/preferences/memory目标；利用现有路径校验和原子替换原语，补输入摘要/前置文件hash/幂等检查。默认不写identity/经历、不写其他画像、共享context或全局MEMORY。无画像不自动建一个。用户主动编辑其他六维字段仍走原有画像编辑语义。
- `target_kind=channel_defaults`：复用频道版本命令，仅保存明确选择的默认项；不将本片规格自动变全频道默认，不增加付费许可。提议产生后切换UI画像/频道不改变其目标；目标或内容过期时409并展示变化。
- `target_kind=director_revision`：沿用既有参考/证据、风格确认、试片及accept流程；只保存新版本，不改旧revision和历史Plan。单个成片的接受不替代Director接受，也不能用未按新Director版本制作的旧输出充当该版本试片。新试片/外部分析所需调用按原授权，不能因学习提议触发。

**确认与幂等**：首次保存操作固定 command_id、proposal/patch hash、目标前置版本；程序验证来源/作用域后对指定目标应用。用户改提议内容则生成新hash，旧卡不可继续保存。Profile文件与SQLite不是一个事务：持有目标文件锁后比较 before/after hash，原子替换并落应用回执；重放若命中同一已写after hash只补回执、不重复追加。若目标既非已知before也非after，返回冲突，不覆盖用户并发编辑。不得用普通append后再盲目重试。跨多个目标分别留回执、明确部分结果，不假称整组原子成功。该恢复协议尚未实现，现有PUT本身不提供它。

未确认、拒绝或忽略的提议不改变长期数据，也不影响成片接受/下载/复用。已确认条目成为后续新Work的输入依据；已有Profile/Director快照与进行中已确认Plan保持不变。新作查询可沿用已有Profile/频道目录读取，不需要再次读全历史聊天。撤销/删除已保存内容按当前目标版本作显式增量修改，保留必要来源/回执，不能整文件回滚覆盖后续合法编辑；来源作品删除按现有影响检查处理，不能把不可用证据仍展示为可播放。

**发布接入的后续边界**：现有PublishPage只选旧目录媒体，旧安全路径检查拒绝V2受管目录。必须经业务适配将已选具体Output解析为通过权限/Rights/署名/hash检查的发布输入，再交原publisher，不能放宽旧media路径或让模型自由提供内部文件路径。平台改版/转码若改变视频字节，登记为派生发布版本并保留来源；发布时选择快照不随之后的accepted_output_id变化。

后续发布关联最少包含 `work_id, output_id, digest, acceptance_ref_at_request, profile_ref?, platform_account_ref, platform, request_ref, remote_post_or_draft_ref?, url?, receipt_state, published_or_saved_at`。只有真实平台回执才是success；公开发布、平台草稿、失败、未知分别记录。一个跨平台动作按平台账号分别留结果；成功一端不重发，未知不盲目重推。现有日历/publish-log作既有兼容底座，关联/去重信息可由适配维护；不另建指标副本。

记录重放以发布请求/远端帖子身份和实际输出为依据，不能只按标题/日期猜作品。Web和脚本只能有一个主记录入口；日志补写失败单独显示待补，不重做真实发布。旧log.record是追加、calendar转发是best-effort，不具备本合同，需要实施时补齐，不能当作已保证exactly-once。

**复盘回流**：查询范围固定账号/画像与实际发布记录；data-tracker快照/publish-log为数据底座，分析脚本只做消费，报告保存在该作品或明确分析范围。用户提供截图/口述时保留来源和日期，缺指标不补造；相关性不当因果性。多版本发布的指标归各自output，不自动归最新接受版。可生成长期提议，但真正写画像/频道/导演仍按上述明确保存；不直接复用旧共享context文件进行跨画像增量写。未授权的新抓取/定时任务/模型调用不得因交付结束自动发生。

**实现验收**：A2留可恢复来源/提议引用；A3/A4共用内容库和版本入口并实现受控长期保存；A5正反例覆盖自动事实登记、明确接受A/产生B、提议忽略/拒绝/重复保存、并发文件变更、跨画像、无画像、默认变化与旧Plan不变。发布/归因适配保留为后续具名任务，不自动扩大本轮实施。

当前导演闭环还有一个待验收差异：WorkService允许符合条件的manual_review_only成片经明确人工审阅接受，但CreativeCatalog的Director接受目前要求试片quality_state=passed。A1未覆盖此路径；A4须按已确认导演需求核实人工审片资格与独立接受回执，不能把作品已接受直接写成自动质量PASS。


### 9.8 频道/导演入口、依据来源与续作（补充提案，未实现）

用户要求补齐导演入口、频道入口与完整创作交互，目标旅程见[交互设计§11](20_CONVERSATIONAL_INTERACTION.md#11-导演频道入口与统一创作闭环)。复用现有CreativeCatalog、Work命令、OpenClaw受限会话桥和原对话/UI；以下为A2～A5增量，不扩大A1已验证的3工具，也不新建频道产线、导演Agent或作品数据库。

**入口上下文（逻辑合同，物理字段/路由待实施确定）**：复用A2持久绑定记录最少保存入口来源kind/ref、明确意图（新作/续接/形成导演/频道设置）、profile/channel、具体director_revision、所选项来源（明确选择/频道默认/画像默认/建议）及来源版本、附件/brief引用；续接还需指定work_id/output_id。导航返回位置只作UI信息，不能决定命令对象。点击目录只读预览；明确创作/拆解才落适当草稿Work，创建频道设置可独立保存，不为每个管理动作造Work。频道/导演选择本身不产生服务授权。

- 宿主校验真实引用、归属与可用状态；新作默认只取已接受导演版本，显式试片允许已确认风格候选。目录结果与源版本在服务端解析，模型返回的名称/ID与UI全局选项不是可信绑定。投给OpenClaw的是本片有权使用的最小内容，不复制全目录/其他画像或原参考媒体。
- 解析的制作设置仍用现有合法schema：本片明确值优先；频道/画像默认只补空缺；导演不覆盖固定声音/字幕。保持来源，以便区分用户要求和预填建议。冻结Plan前比较当前依据版本/hash；确认后不重新读取新默认改变已冻结Plan；新请求不能套用旧授权。
- **频道语义配置缺口**：现有catalog.settings白名单只有制作参数，不能塞入定位/主题/受众。A2需在现有频道对象补版本化创作依据，旧记录空值兼容；具体字段和前向迁移在实施时确定。自然语言设置提议要有目标频道/expected_revision/差异/command_id，确认后保存；Planning只通过有来源brief/冻结依据读取。频道归属仍固定一个Profile，无画像临时作不自动建立频道/Profile。
- 目录create/update/accept继续由明确卡操作适配现有catalog.command及命令回执，不把通用catalog写工具交给模型。形成导演时，宿主将明确参考拆解意图与本片空闲Work/输入版本、reference_input_ids、分析授权绑定；复用analyze_director任务。参考访问/导入和多片段来源需实测，不能仅靠标题/文本“拆解”宣称看过视频。style确认与完整Plan确认各针对不同对象，style确认不启动生产。
- 正式首版兼试片：同一Work在空闲/输入和所选版本有效时可继续规划；试片输出必须实际出自Plan.director_revision_id所指版本。成片accept、导演accept、频道default更新各用独立固定command_id/目标版本，不默认联动；同一收尾卡可明确选择多个动作，并显示每项成功/冲突/待处理，非原子组合失败不重复已成功副作用。Director人工审片资格差异依§9.7/A4处理，不能改QC事实绕过。
- 确认前切换创作依据使旧待确认卡失效；活动Run不改输入或工具目标；确认后创作变更走revision。仅收纳归属变更复用assignment：同Profile频道/空频道，不改冻结Plan、原导演或设置。历史恢复必须读原快照，不能以当前目录默认重新构建历史。
- **fork缺口**：当前_create会重新合并频道默认，_fork未复制原settings/导演，只带主题、画像、频道和所选输出参考（Rights UNKNOWN），不承诺原风格精确沿用。后续用服务适配明确选择沿用原导演/声音/字幕或采用频道当前默认；向新Work传验证后的显式设置并保存来源，不覆盖原Work、不复制旧grants。输出参考也不成为新作可直接重剪的授权素材。
- 频道历史/导演使用视图从原Work、Plan、acceptance、导演代表试片引用投影；未接受作品保持待审/进行中分区，导演代表试片仅由合法导演accept更新。切换UI选择不改变既有学习提议目标或误写其他频道。归档/默认失效与并发保存返回明确错误，不静默替换版本。

验收加入S6-14A UI19～UI25：三入口同链、默认优先级、跨画像/归档拒绝、频道语义依据、同Work正式首版兼试片与双接受、历史恢复/仅归属变更、fork设置与新授权。以上均为待执行验收，不能由A1隔离PASS或S6-13离线管理功能证明已通过。


### 9.9 创建提案、目录卡与恢复（整体审查补充，未实现）

创建流程见[交互设计§11](20_CONVERSATIONAL_INTERACTION.md#11-导演频道入口与统一创作闭环)，本节补齐尚无Work时的合同。目录写入仍复用CreativeCatalog，生产仍复用WorkService；不新增目录Agent/生产队列，也不将候选协议冒充A1已经提供的工具。

**无Work阶段**：在既有会话/turn/卡片记录中保存有类型的设置提案，最少逻辑信息为proposal_id、kind（channel_create/director_formation）、revision/hash、来源消息/附件、目标Profile及可选channel/director、用户值/系统建议、状态及applied_entity_ref/receipt_ref。work_id此时可空。宿主以受限运行段与明确Profile/目录目标校验范围，只给所选信息；不能为取得工具上下文先创建无内容Work。模型结构化候选由宿主按schema/来源校验后保存为提案，不从自由Markdown推导执行卡/授权，候选本身不写catalog。

**目录卡**：沿用持久卡投影，但entity_ref可为有类型的创建提案、Channel、DirectorRevision或分析Task；work_id仅在有关联Work时出现。提案使用自己的revision/hash，已存在目录对象使用catalog revision，分析进度使用所属Work cursor。不得把三种版本混用。kind/动作固定枚举；模型不能定义按钮动作/URL。每次修改生成提案新版本，旧卡不可提交；卡片显示未保存、提交中、待核实、已保存及真实实体引用，成功状态来自命令回执。关闭/刷新从持久记录恢复。

**确认动作**：首期channel_create、director_analysis、style_confirm、director_accept和channel_default与生产confirm一样，只由明确卡操作提交，正文同意只定位卡片，不自行生成执行权限。服务器重新核对提案hash、目标范围、目录/输入版本与授权；首次动作固定command_id，响应丢失复用原ID取回执。同一已应用提案不因重复点击/另一窗口/新的toolCallId再次创建。服务端语义校验、允许值和来源仍必要，用户点击不把模型生成的任意路径/字段合法化。

**分步创建与衔接**：频道保存独立于Work，不启动生产；后续进入新作若失败只恢复绑定，不能重建频道。导演分析需Work→输入登记→catalog create/analyze，这些沿用各自固定命令并保留步骤回执/输入映射；中途失败从未完成步骤续接，成功/UNKNOWN分析不重发。参考专用Work的初始主题取用户实际“分析这些参考并形成风格”的请求，不编造其经历或正式脚本；以后在空闲状态用来源明确的本期brief承接正式首版。现有API直接创建导演时即创建分析Run，不存在“先建一个空导演就可用”的阶段。

**目录关联与组合动作**：显式“关联并设为频道默认”提交准确channel revision、完整保留后的director_ids及已接受的default_director_revision；只设置默认而缺关联的请求由适配校验/补齐用户已确认的那一个关联，不清除其他关联。现有catalog只检查默认版本可用，没有完整强制默认属于关联集合，须在实施时补一致性校验。试片收尾若用户选择多项，作品accept与导演accept分别留回执；设置默认依赖导演accept实际成功，否则保持待处理，不伪造全组成功或重跑已成功动作。失败提示目标和可恢复动作，不自动扩大选择范围。

**输入与权限**：上传归属/句柄/hash/symlink检查必须通过；Rights UNKNOWN可以作为合法登记的风格参考，不赋予剪入成片/原声复用的许可。远端链接须通过既有受控获取/媒体输入适配解析为句柄，受限聊天工具不接受任意URL/文件路径。下载/分析本身遵守允许来源与服务授权，无法取得媒体显示未分析。新增参考重拆同一导演需明确target director/base revision、空闲Work和新输入证据，保留旧已接受版本；当前catalog没有该完整入口，留待A2/A4适配，不通过revision接口替换evidence绕过分析。

**终止与恢复**：删除聊天撤销继续工具调用的能力，清理聊天正文副本；在途invocation/command与结果待核实映射作为最小业务核实记录保留至结清，不能删除后遗忘UNKNOWN再重发。任务/成果/目录对象独立存续。原生段与Work/Profile绑定的恢复遵守§9.4，跨作品不能共用旧原生转录。拒绝/丢弃未保存提案不删除既有频道、导演、原素材或成功任务；不能把关闭页面当cancel。

人工模式导演接受继续按§9.7保留为A4资格适配事项：当前不具备时卡片如实提示，保留待接受草稿，用户仍可独立接受符合条件的作品；不把semantic not_tested写成PASS，也不为解锁按钮自动运行收费检查。完成创建后回到新作讨论，不自动执行Planning/TTS/发布。
