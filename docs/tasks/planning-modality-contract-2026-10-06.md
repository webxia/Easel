# Planning 声音参数与视觉合同边界修复

状态：SOFTWARE_ACCEPTED；确定性验证完成，Astra 最终 CONTINUE。所属 Workstream：[素材层可靠供给与耗时优化](creation-latency-2026-10-02.md)。用户于2026-10-06要求先检查第二轮失败根因、写方案、设目标并优先解决。

## 目标与范围

修复 Planning producer、既有结构修复、NeedCompiler、视觉合同和声音执行参数之间的模态职责不一致，使合法 Voice 参数保持 canonical 对象、错误模态得到具体且一致的拒绝。以第二轮真实输入保护该边界，完成确定性验证后再评估新 E2E 的软件前置。

不恢复两轮失败 Creation，不改其 Plan、Need、冻结输入、报告或数据库；不加载服务、不调用真实 Provider/模型/生成，不进入 Authoring/Build/Quality。required/optional、创作语义、Rights/Match/Readiness、Material V1.3 主链不变；不靠增加模型重试解决该问题。

## 已核实根因

证据为[第二次独立验收](../acceptance/material-independent-e2e-2-2026-10-06.md)，Creation `cr_223021d92de643f0a35faea2907de7ed` / Attempt `fa_d5e99b227faa224b82f5347174850a1b`。

1. **污染发生于初始 Planning。** 保存的初始 Plan 已在所有10个 Need 上复制 `constraints.voice_delivery`，包括7视觉、1 Voice、1 BGM、1 SFX。初始 Voice 还只写 `text_ref`、漏写配对 `text_sha256`，先触发 Domain 错误。
2. **合法 Voice 对象原本受支持。** `NeedCompiler.compile()` 已对 VoiceNeedSpec 的 `voice_delivery` 调用既有 `validate_voice_delivery()` 并排除于检索过滤器。真实 scalar 错误来自非Voice Need上的对象；不能误判为需要让所有模态接受声音对象。
3. **初始与修复提示不一致，错误缺少定位。** 初始提示说明声音对象，但未明确禁止复制至其他模态；修复提示笼统写“constraints只能标量”，没有保留Voice对象例外。通用错误没有给出Need ID与模态，诱导模型全局摊平字段。
4. **扁平别名没有被拦截。** 系统修复把参数摊成 `voice_pace_ratio`、`voice_pitch_semitones`、`voice_tone`，写入全部Need。这些不是声音执行consumer使用的正式字段，却可通过通用scalar过滤；声音consumer仍只读取canonical `voice_delivery`，存在执行参数静默丢失风险。
5. **末端视觉校验只是最终拦截点。** 要求根对象包含全部7视觉ID、未含audio ID；但每项的 `constraints/voice_tone="neutral"` 成为未引用字符串源，严格完整覆盖拒绝。不能通过给视觉补“neutral”条款或一概忽略声音字段来掩盖上游错误。

6. **单次修复没有跨重入保持身份。** 原局部限制只覆盖一次函数调用；异步返回后，错误文字变化会生成不同请求digest，同一Attempt累计7次修复。已观察error的旧请求还可自动派发新run。这是调用放大的独立机制，不能仅靠改善提示解决。

## Canonical 与最小方案

- 声音执行参数唯一结构仍为 Voice Need 的 `constraints.voice_delivery={pace_ratio,pitch_semitones,tone}`，合法值继续由现有 `validate_voice_delivery` 定义。检索不将它当硬过滤，生成consumer读取它并保留实际参数。
- `voice_delivery` 不能存在于 image/video/BGM/SFX；三个已证实扁平声音别名在所有Need上均拒绝，并指向canonical结构。明确视觉偏好仍只属于视觉Need。任意其他未知结构化约束仍按原严格规则拒绝。
- 建立一处小型 application 层模态参数边界，复用于检索、视觉合同和声音生成入口。错误包含Need ID、具体字段路径、实际模态及合法位置；不自动删除、搬移、合并或猜测声音参数，不改Domain对外schema。
- 初始Planning与现有repair共用同一段模态参数规则和对象例外，去掉冲突的scalar-only表述。视觉条款仍完整引用全部真实视觉要求；audio Need不进入visual sidecar。
- 将既有“单次结构修复”落实到持久边界：按Attempt、冻结refs及确认方案SHA保存原message与route，派发前落盘；pending/未知/超时重入仅观察原请求，即使草稿看似有效也先确认远端终态；complete只验产物，failed不重派。错误文字、文件变化和普通Owner Retry不再增加额度。adapter局部使用retry_failed=False，其余调用保留默认行为，不重构Delivery Owner。
- 此项明确改变恢复行为；不是宣称所有行为不变。Material V1.3语义、合法声音结构和取值范围不变，既有非法跨模态字段及已证实别名提前拒绝。

## 实施顺序

1. 保存真实初始/中间/终态的最小回归证据与SHA；原现场只读。
2. Astra按AGENTS.md做跨模块边界前置复核，Main根据证据完成最小取舍。
3. 实施共享模态校验、producer/repair一致提示、必要入口接线及持久单次结构修复身份。
4. 扩展现有高价值合同与Planning集成回归，运行相关测试/技能合同/compileall/diff检查。
5. 记录软件结论与尚未验证的真实能力；两轮FAIL保留，新E2E另行启动。

## 验收条件

- 真实污染Plan在最早公共入口得到具体模态错误；不会被静默过滤或变成视觉要求，也不会流入TTS默认参数。
- 合法Voice对象通过NeedCompiler，参数完整保留且不进入检索filters；视觉、BGM、SFX拒绝声音对象，所有模态拒绝三个扁平别名。
- 无效Voice范围/类型、未知结构化约束继续拒绝；原画面required/optional及全部原文覆盖不放宽。
- 一个合法混合Plan通过同一Planning→合同→consumer路径；全部视觉Need及音频Need保持ID/importance/内容，合法声音参数传至已有生成准备协议；模型/Provider调用由测试禁止或替身统计为零。
- 初始与repair收到同一模态边界指令；真实失败作为拒绝回归，测试构造的合法对照明确标记为隔离测试，绝不回写现场。
- 第一轮真实wrapper、缓存一致性、required/optional、音频ID隔离回归继续通过。软件通过不等于MATERIAL_READY或第三轮真实E2E成功。

## 实施记录

- `easel/materials/application/need_constraints.py` 为单一模态约束入口；NeedCompiler、视觉source、PlanningIntegration默认合并前、图片/声音生成入口共用。producer与repair共用同一规则段，保留voice_delivery及search_query_variants_en两个对象例外。
- 真实对象污染与扁平污染JSON原字节加入[fixture](../../tests/fixtures/planning-modality-contract-2026-10-06/README.md)。负例只拒绝不修写；合法混合对照仅在测试内构造，原7视觉、9required/1optional、全部10个ID保持，visual sidecar/cache一致；TTS mock验证合法参数原值传递、别名在调用前被拒绝。
- 恢复回归覆盖changed-error、pending-valid、timeout、终态无效、终态失败及已观察adapter错误不重派；初始与repair同规则，旧wrapper/cache/确认三文件与路径保护继续验证。
- Astra前置MODIFY指出持久重入缺口，最小补齐后最终CONTINUE；未改变架构责任边界。

## 最终验证与保留现场

- 全量 `.venv/bin/python -m pytest -q --tb=short`：**731 passed、5 skipped，46.05秒**；2条第三方弃用提示，无测试失败。相关子集此前249项通过，随后补入终态失败重入场景由全量覆盖。
- `validate_skills.py`：115合同通过；`compileall` 与 `git diff --check` 通过。测试仅使用隔离临时目录和替身，未调用真实模型/Provider。
- 第二轮workspace原18项文件SHA全部不变；14个旧Creation JSON SHA全部不变，含第一轮FAIL。第二轮delivery仍failed、operation为空；Web/Gateway PID39338/39348及20:04:10启动时间未变。原预算未消耗，不恢复旧Creation。
- 本次修改留在easel-studio工作区，未提交、未重载生产服务；不混入已有无关文档整理。新真实验收前仍须独立提交固定版本、加载版本核验和新Creation流程。

```text
ROOT_CAUSE = 初始跨模态复制voice_delivery；冲突的标量修复指令诱发扁平别名；异步重入未持久限制单次修复
CANONICAL_CONTRACT = Voice Need constraints.voice_delivery；视觉sidecar仍为全部image/video Need ID -> clauses/queries
FIX = 共享模态校验、producer/repair一致规则、消费者提前拒绝、持久单次修复请求
REGRESSION = 731 passed / 5 skipped；真实失败原字节、合法混合对照、声音参数执行与异步恢复边界
CONTRACT_CHANGED = NO（合法Domain/Material V1.3语义不变；非法输入提前拒绝，恢复重派行为有意收紧）
READY_FOR_NEW_MATERIAL_E2E = YES（仅软件前置；版本尚未提交加载，未授权或启动本轮后的新真实验收）
```

## 提交与服务加载授权

用户在软件目标完成后明确要求提交全部改动代码并重启服务，为第三次E2E做准备。本次仅固定已验证修复、保留回归及安全加载Web/Gateway；不启动新Creation或转授前两轮预算。加载核验记录保存于本机`acceptance/planning-modality-release-2026-10-06`，当前加载状态见Current State。以上“未提交/未加载”为软件修复阶段的历史状态。
