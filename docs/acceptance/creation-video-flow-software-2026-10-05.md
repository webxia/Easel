# 视频制作流程软件验收（2026-10-05）

> 对应 [Task](../tasks/creation-video-flow-software-2026-10-05.md)。结论：确定性软件验证通过，可进入分支整合；没有执行真实 Planning/观察模型、Authoring、Build 或成片感知验收。

## 1. 范围、基线与隔离

- 基线：`easel-studio` / `6223406526b4de3faef654d29515fb417a42a500`；交付分支：`codex/video-flow-software`。
- worktree：`/Users/xgx/.codex/worktrees/video-flow-software/Easel`；测试使用主工作区已有 `.venv`，未安装框架或改依赖。
- 主工作区原有文档、BGM 校准脚本/产物及未提交修改未覆盖。本分支仅更新自己的 Task 和本验收记录；Current State、Roadmap 与总顺序由整合 Owner 更新。
- 未改 BGM 判定、声音策略身份、Material V1.3 Domain、冻结 required、素材/模型额度、费用账本、Provider 或 Hypit 生产主链。
- 未加载生产服务；没有读取/写入旧作品 Creation、Attempt、数据库、预算或运行报告。测试只使用临时目录、固定媒体字节和确定性执行器。

## 2. 已存在的修复与本轮新增缺口

| 环节 | 基线已存在的行为（不计作本轮成果） | 本轮有证据的缺口与最小纠正 |
|---|---|---|
| 选材 | Need/source 排序、相关小批、冻结提名、关联账本、已覆盖停止；不为 desired_options 继续消耗 | 本轮没有新的排序缺口；保留现有候选数和停止规则 |
| 原文与偏好 | 程序绑定编号和原文位置，模型只交分类/检查；显式偏好不能升为 required；真实源动作不能转后期 | 同轮 Planning 合同写入 `requirements-digest(input)`，观察只查带 compiler policy 的另一个键，造成再次分类；统一精确读取，优先 Planning，只有缺记录才允许现有分类 |
| 模型报告交付 | 提交前保存 runId，未知执行只等原 run；终态文本持久化；按 3000 UTF-16 容量拆分必要检查；已有一次结构修复 | 缺失/截断/超容量终态和耗尽的结构修复仍落入泛化异常，可能重复空重试；新增具名错误，保留原 run，Owner 停止原操作，不转为素材缺口 |
| 观察复用 | 完成的 compact 结果、报告、共享帧事实均持久化 | 后续批次补入 shared facts，恢复时前一成功批次请求身份变化，导致重复观察；派发前冻结批次 payload 和摘要，恢复复用相同请求 |
| 合同与缓存 | Need/asset/frame 身份已校验 | 合法旧报告的 required/postproduction 分类可能不同于当前合法 Planning 合同；在 Web、底层复用、已合格资产入口和 Production.prepare 校验完整合同与摘要，冲突具名停止，保留旧证据 |
| 扩展检索 | 已完成供给、生成和费用 reservation 可接续 | recovery 以 Need SHA 扫描任意旧要求文件，可能忽略冻结上下文/模式；改为同一精确输入读取，不追加检索机制 |
| 后期表达 | 分类已有 postproduction，冻结 Planning 原文仍交给 Authoring | 没有明确传递已分类的待后期条款；新增独立服务端只读 JSON，绑定原文范围、合同 SHA 与阶段输入 SHA；不改 selection 或素材准入语义 |
| 用户进度 | 页面投影真实 blocking Needs、Delivery 原因和已有成果 | 无需重建界面；新具名错误由既有 last_error 路径展示，没有乐观 READY |

## 3. 真实调用链与责任边界

1. `web/app.py` 的 Planning executor 消费冻结 Brief/Script/Scene/模式，`PlanningIntegration.persist` 保存 Plan 和同轮要求合同。`visual_contract.planning_contracts` 绑定程序侧原文，`read_requirements_contract` 按完整 `compilation_input` 验证输入、原 response 重建值和保存的完整 contract。
2. `MaterialProductOrchestrator.observe_visual_materials` 先恢复已完成生成记录，检查已合格资产的 scoped observation 与当前合同，再沿现有 Need/source 排序、冻结提名和未覆盖关联观察。`web._observe_material_group → _observe_material_frames` 复用报告或按必要条款拆批；偏好仅作上下文，后期条款不变成源素材检查。
3. `_material_compact_result → run_agent_sync → openclaw_delivery.run_delivery_agent` 继续通过原 OpenClaw RPC。dispatch 前记录 runId 和累计 reservation；unknown 只 `agent.wait` 同一 run；终态回复在原 call 记录保存后解析，compact 成功结果单独 checkpoint。无 Provider 直连或第二条生成链。
4. 每个观察批次以除 shared facts 外的不可变 payload 生成 `observation-batch-*` 键；首次派发前保存完整 resolved_facts 快照及 payload SHA。恢复验证全部不可变字段和摘要，然后复用原 compact/run。没有新重试计数。旧版本没有 snapshot 时，仅查询当前事实与空事实两个精确 compact 键，保留已完成结果；不扫描其他 Need/asset/合同历史。
5. `assemble_report → read_observation_report → apply_observation → MaterialMatcher / MaterialGateIntegration` 仍负责必要内容证据、Rights、技术/匹配和 MATERIAL_READY。缓存报告须与当前要求合同完整一致。已合格资产通过实际 scoped evidence 找回所用报告校验，避免 READY 直接跳过。合同损坏/冲突停止，不自动重分类、不覆盖旧报告或伪造新内容缺口。
6. `recover_managed_materials` 保留原恢复账本和生成接续，仅把扩展 queries 的要求合同选择改为精确 Need + context_refs + 冻结模式。
7. `ProductionAuthoringIntegration.prepare` 在原 Gate 后生成 `productions/easel-authoring/POSTPRODUCTION_REQUIREMENTS.json`：`PENDING_AUTHORING`、Creation/Attempt/Plan/revision、Need/scope、合同 SHA、条款 id/path/start/end/text。缺少旧合同的 Need 列入 `unclassified_need_ids`，使用原 Planning；不在准备阶段调用新分类。该文件不是完成证据、Material Domain 字段或 selection 字段。
8. `_run_film_authoring → postproduction_authoring_instruction → run_attempt_scoped_authoring` 在原 Authoring message 中绑定 JSON 文件 SHA。真实 `_stage_authoring_inputs` 把文件复制到受限工作区；派发前、结果返回后及静态修复后核对源文件/副本 SHA。只提升原 allowlist 文件，不回写此服务端输入。保留的旧消息不补新 marker；已有新阶段输入变化则保留 stage/result，拒绝认领原执行，不重新派发。
9. 前端 `creatorWorkspace.ts` 第 75–76 行合并 Gate/choice 的 blocking Need IDs，第 105 行消费 `delivery.last_error`；本轮未改前端。

具名故障沿原 Owner 进入 `failed`（观察对账操作为 `observation_failed`），保存 `exhausted_operation`、`last_failure_kind` 和脱敏原因；原操作不自动空跑。显式 Retry 的现有预算与历史接续仍有效，未清零累计费用或新增 SDK 内部重试。

## 4. 固定输入局部回放

回放入口：`test_visual_chunks_resume_with_fixed_requests_and_preserve_planning_contract` 的两个参数。相同一个 Need、一个固定 PNG、12 个必要片段、一个后期表达与一个显式角度偏好，容量规划得到 3 个观察分组；第二组在提交成功后模拟未知执行。模型输出由 fixture 按固定编号生成，不证明真实视觉语义。

| 指标 | 修改前 | 修改后 |
|---|---:|---:|
| 直接观察输入的 Need / 候选数 | 1 / 1 | 1 / 1 |
| 观察分组 | 3 | 3 |
| 中断前调用 | 第 0、1 组 | 第 0、1 组 |
| 恢复后累计新观察 dispatch | 4：`0,1,0,2` | 3：`0,1,2` |
| 重复成功观察 | 第 0 组重复 1 次 | 0 |
| 同轮 Planning 合同已保存时的额外分类 | 旧读取键遗漏，独立分类 1 次 | 0 |
| 未保存 Planning 合同的分类 | 1 次 | 1 次 |
| 恢复步骤 | 1 次恢复进入；完成后再次读取 | 相同；完成后再次读取不追加调用 |
| 搜索 / 生成调用 | 回放禁止 | 0，任何调用即测试失败 |

修改前新增用例的失败轨迹为 `[(0,0),(1,0),(0,0),(2,0)]`；修改后为 `[(0,0),(1,0),(2,0)]`，第二个数字为 repair ordinal。升级兼容参数删除新 batch snapshot、保留旧 compact 文件，仍复用成功第 0 组。候选排序和提名算法未修改，原有多候选/覆盖停止回归通过；以上直接观察回放不作为新的排序性能结论。

回放继续将观察证据写回 asset，计算真实 Gate READY，然后只执行 Production.prepare 和实际 staging copy。验证后期原文/位置/合同 SHA 不丢失，状态仍为待编排；副本被修改立即拒绝。之后保留合法原报告，安装另一份合法 Planning 分类：Web 缓存、READY orchestrator 和 Production.prepare 均拒绝混用，原报告未删除、模型调用不增加。再损坏当前合同，仍拒绝覆盖或再次分类。

没有同环境整片基线，因此不报告成片耗时或提速比例。

## 5. 验证结果

执行日期：2026-10-05。工作目录为上述独立 worktree，Python 命令使用 `/Users/xgx/Projects/Easel/.venv/bin/python`。

```text
python -m pytest -q tests/test_material_*.py tests/test_creation_preparation.py \
  tests/test_openclaw_authoring_boundary.py tests/test_openclaw_finalization_patch.py \
  tests/test_hypit_integration.py --tb=short
418 passed, 2 warnings in 23.69s

python scripts/validate_skills.py
OK: 115 skills and publisher execution contracts conform

python -m compileall -q easel web scripts tests
通过

git diff --check
通过
```

两条 warning 来自已有 Starlette/httpx 和 anyio 别名弃用。前端未变，本轮未运行 npm lint/build；未新增依赖。`test_creation_preparation` fixture 改为临时目录中的固定 persona，消除依赖主工作区未跟踪的本机 profile；产品校验没有放宽。

| 风险 | 确定性证据 |
|---|---|
| 偏好不可拒绝、必要主体仍拒绝、源动作不可转后期、错号/遗漏不可准入 | `test_required_paper_and_optional_angle_have_distinct_admission_contracts`：扩展既有风险矩阵，保留纸张缺失反例 |
| 证据 unknown 不伪造满足；结构修复耗尽不触发供给 | `test_system_visual_observation_is_per_need_and_resumes_without_supply`：独立 Need、uncertain、missing/duplicate/syntax/persistent/silent；成功旧报告保留 |
| 合同复用、三组恢复、升级旧 checkpoint、旧报告与新合同冲突 | `test_visual_chunks_resume_with_fixed_requests_and_preserve_planning_contract`；包括合法旧报告未删除时的各层拒绝 |
| 小批选材、达到覆盖停止、旧偏好拒绝才重评 | `test_visual_replacement_stops_at_usable_choice_or_bound_and_reuses_saved_report`、`test_sparse_shared_observation_explores_unknown_metadata_and_skips_covered_scenes`、`test_only_obsolete_preference_refusal_is_reassessed` |
| 同一 run 回复/未知状态恢复，截断/容量不盲修，整个回复缺失走一次既有修复 | `test_material_result_is_received_from_same_run_and_reused_without_dispatch`；两次 advance 只执行一次原操作，派发数为 1 |
| 生成身份、reservation、已完成结果、费用/调用累计不重置 | `test_commission_generation_reserves_before_submit_and_survives_restart`、`test_material_recovery_preserves_generation_and_reconciles_without_resupply`、`test_delivery_stage_budget_counts_nested_calls_and_survives_digest_retry` |
| 后期输入真实副本、受限输出提升、不可认领输入变化的旧阶段 | `test_attempt_authoring_stages_inputs_and_promotes_only_approved_files`、`test_delivery_authoring_keeps_live_stage_and_recovers_completed_files`：新绑定/旧消息两参数，漂移保留旧 stage，恢复原字节继续原 run |
| 原同轮 Planning 写入、真实 frozen refs 消费、source/action/selection 边界 | `test_director_planning_executor_consumes_frozen_refs_and_not_fixed_image`、`test_same_planning_turn_binds_requirements_and_queries_to_the_canonical_need` 及既有 Material/Hypit integration 组合 |

上述测试名称中的 Authoring/Build 指确定性测试执行器或已有检查点回放，未调用真实 Authoring 或 Production Build。

## 6. 参考实现、版本与许可

参考研究在主工作区已核实；本轮对固定 commit 的相关源码和 LICENSE 再核对。没有直接复制上游代码或安装它们的 SDK/服务；使用 Easel 既有恢复存储、异常和受限 Authoring 边界实现小范围修正。

| 来源与固定版本 | 核对的文件与许可 | 本轮采用 / 明确不采用 |
|---|---|---|
| [OpenMontage](https://github.com/calesthio/OpenMontage/tree/9327439db69021ab4b0e2776729bf3b58fdb5a87) `9327439db69021ab4b0e2776729bf3b58fdb5a87` | [asset-director.md](https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/skills/pipelines/documentary-montage/asset-director.md) 第 23–24 行小批；[schemas/artifacts/scene_plan.schema.json](https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/schemas/artifacts/scene_plan.schema.json) 的 camera_movement / shot_intent / required_assets；[LICENSE](https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/LICENSE)：AGPL-3.0 | 对照小批选材与源素材/后期责任分离，现有选材重叠部分保留，新增只读后期输入；无源码移植，无 CLIP 库，无其过宽最终质检标准 |
| [Instructor](https://github.com/567-labs/instructor/tree/e12f8b49203b0c1f253d27c1e709d0a09b9fc5a8) `e12f8b49203b0c1f253d27c1e709d0a09b9fc5a8` | [instructor/v2/core/retry.py](https://github.com/567-labs/instructor/blob/e12f8b49203b0c1f253d27c1e709d0a09b9fc5a8/instructor/v2/core/retry.py)：max_retries+1、IncompleteOutputException 直接传播和解析错误分离；[LICENSE](https://github.com/567-labs/instructor/blob/e12f8b49203b0c1f253d27c1e709d0a09b9fc5a8/LICENSE)：MIT | 对照截断与结构故障分离、累计用量；自有 typed error 接入原 Owner，不引入 SDK 或额外 retry 层 |
| [Temporal Python SDK](https://github.com/temporalio/sdk-python/tree/e47c9629b75a48e21abd4f72fed7f72a27562f53) `e47c9629b75a48e21abd4f72fed7f72a27562f53` | [temporalio/common.py](https://github.com/temporalio/sdk-python/blob/e47c9629b75a48e21abd4f72fed7f72a27562f53/temporalio/common.py)：maximum_attempts、non_retryable_error_types；[README.md](https://github.com/temporalio/sdk-python/blob/e47c9629b75a48e21abd4f72fed7f72a27562f53/README.md)：heartbeat 持久化恢复；[LICENSE](https://github.com/temporalio/sdk-python/blob/e47c9629b75a48e21abd4f72fed7f72a27562f53/LICENSE)：MIT | 对照明确不可重复故障与 durable checkpoint，新增原存储中的批次快照；不引入 Temporal runtime/service，不采用 maximum_attempts=0 的默认无界重试 |
| 本机 `@hypit/hypit` `0.2.7` | 已安装 package.json、LICENSE 与 `media-track/src/motion.ts`、`surface.ts`、typography 真实源码；LICENSE 为附加条件的 Apache-2.0，包声明 `SEE LICENSE IN LICENSE` | 只核对现有安装版合同及原受限 copy/allowlist 路径；无 Hypit 源码移植或新 SVML 语法，不声称已渲染出镜头运动 |

固定来源文件 SHA256（用于研究材料定位，不进入运行合同）：

```text
OpenMontage asset-director.md 24ea30adf34c62f2655569fdbd35558fb97dfa5d3e1c45421860c352dc60f7d1
OpenMontage scene_plan.schema.json 7b833b7643a73921011270189e5baf645ca67d09390a5d143f6a4b55a667d7a9
OpenMontage LICENSE 0d96a4ff68ad6d4b6f1f30f713b18d5184912ba8dd389f86aa7710db079abcb0
Instructor retry.py 1e9a80546b540f7280a5926eae94b5f44084663aa80f681971c5536c22d8b538
Instructor LICENSE 1fdd867197ab4d56e3c00ee835e4ea53aac5d54f6e6ac6d247bf866bcf3a9352
Temporal common.py f8d2a7cb6389cceea3f93b0bab2cd28c27a1506cdcaa05b26d8f39a9704181de
Temporal README.md 902880e487fa379d06f3e173c18d14d7928c7e9fe609e7a0d00f9523dc6584b1
Temporal LICENSE d7706f28d144dabf07e4946553a4d117d1dab5cda6bf34a602959b4a2fa86b38
```

## 7. 复核、整合与真实验收边界

Astra 前置复核为 `MODIFY`：要求后期投影独立于 selection，由服务端生成；完整合同校验；绑定保留的 message/stage；固定批次请求。Owner 按要求修改。首轮末尾复核又发现旧报告与当前合同可能冲突以及整体缺失 terminalReply 的分类遗漏，补齐各层检查与保留旧报告的反例后，最终 `DECISION = CONTINUE`，`MINIMUM_CORRECTION = 无新增必修代码项`。Reviewer 只读核对 diff/证据与 diff-check；418 项测试由 Owner 执行。

整合时以提交 diff 合并到 `easel-studio`，与 BGM 分支共同文件分别保留局部差异，并重跑本记录中的相关组合回归。独立分支软件通过不代表 BGM 已验收，也不代表旧作品状态已更新。

后续真实验收须在 BGM 达到 MATERIAL_READY、两分支完成整合回归且另获授权后进行：

1. 固定真实语义案例核对 Planning 的 required/preference/postproduction/unresolved；检验主体缺失、真动作缺失和 unknown，没有用格式通过替代语义正确。
2. 通过既有 Hypit Authoring 主链读取新待编排输入，核对镜头运动/字幕落实；执行正式静态检查、Build 和 Quality 的实际画面感知验证。新 JSON 及 fixture 不是落实证据。
3. 若当前权威合同与旧观察冲突，先查明合同来源并按当前合同完成明确重评；不得删除旧证据后默默认领、扩大 required 或重复付费。软件已保证具名停止，未自动迁移其语义。
4. 以相同环境记录完整视频调用、费用、恢复与耗时。当前局部调用减少不能推断真实成片速度或稳定性；G4 新 Content 仍是独立后续阶段。
