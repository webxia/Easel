# v0.5 素材层正式恢复验收（2026-10-05）

状态：FAILED / 5 of 9 / MATERIAL_NOT_READY / R1与R2监护停止、R3自动失败上限 / 未自主完成。用户授权本轮继续素材层独立跑通并记录问题；终点仅 MATERIAL_READY，不进入 Authoring / Build / 成片审片。

## 固定输入与起点

- 继续 Creation `cr_77175a2271bf4e408a359884efc438e6` / Attempt `fa_22f91d9f97ab6e7c355d46ba87bb478b`，复用正式 Planning；Plan revision `5e83f86c1486cfe88030ef5be47d35683a43e1faad3037e416ebe30b98593846`，不重规划、不手造 Need。
- 已提交基线 `964104fe792e30297fb2da0e3e28b1ce7068eb59`，Python 生产源码集合 SHA `e5d42a819f8bee25df5c3c8ca88fa4950e844158ac97201d33660678ef39bc14`。本轮不修改业务代码、模型配置或审核结论；运行故障按五类记录，不工程救场。
- 起点 required 4/9；A/B 与 E/G 的合格素材、既有图片及旁白保留。Prepare 7/24，Material 88/1840；历史失败和累计调用不清零。
- 当前授权 CNY10，仅当前真实缺口；已占额0.1048，剩余9.8952；实际账单 unknown，不扩展服务、模型或费用。不下载备用声音模型，使用已提交的有限低置信规则。
- 原委托 endpoint=MATERIAL_READY；Authoring未开始、Build NOT_SUBMITTED。原具名 Acceptance 保持，恢复段自主性不能倒算历史整轮 AUTONOMOUS=NO。
- 预检网关2026.9.4：active0 / queued0；已知 agent 全部终态，两项已购生成均 COMPLETE，无未知生成提交。Web旧PID57771，加载已提交版本属于本轮运行前置，不是运行中工程救场。网关/Hypit不重启；离线安装补丁的实际内存加载不认领。

## 验收指标与问题分类

逐 Need 正式 qualified 覆盖及 Gate；本轮是否有人改代码、代写报告或人工放行；新增墙钟、调用/关联、复用、各阶段等待、失败及费用。与历史84分38秒/51视觉请求只能作恢复参考，不是同条件独立提速比例。

问题分类：搜索召回 / 观察判断 / 报告保存 / 音频验证 / 补位策略。未知请求先对账，不因为轮询超时重新派发；正式失败保留现场及具体缺口。足够覆盖才算交付成功，有界停止不算成功。

## 本轮进展

- 2026-10-04T23:56:54.565061+00:00 保存只读起点及冻结文件摘要；未派发新素材工作。

- 2026-10-04T23:57:18.115773+00:00 Web新PID81540经原服务加载已提交版本；通过正式 Operator `/delivery/retry`恢复同作品，endpoint复核仍为MATERIAL_READY。未清累计账本、未重规划。

- 自动监测 `{"at": "2026-10-04T23:57:54.059962+00:00", "status": "observing_material", "operation": null, "coverage": 5, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "new_agent_calls": 0, "live_runs": [], "material_calls": 89, "last_error": null}`

- 自动监测 `{"at": "2026-10-04T23:57:59.085948+00:00", "status": "observing_material", "operation": "observe_material", "coverage": 5, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "new_agent_calls": 0, "live_runs": [], "material_calls": 89, "last_error": null}`

- 自动监测 `{"at": "2026-10-04T23:58:04.127024+00:00", "status": "observing_material", "operation": null, "coverage": 5, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "new_agent_calls": 0, "live_runs": [], "material_calls": 89, "last_error": null}`

- 自动监测 `{"at": "2026-10-04T23:58:14.192797+00:00", "status": "observing_material", "operation": "observe_material", "coverage": 5, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "new_agent_calls": 0, "live_runs": [], "material_calls": 89, "last_error": null}`

- 自动监测 `{"at": "2026-10-04T23:58:19.237069+00:00", "status": "observing_material", "operation": null, "coverage": 5, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "new_agent_calls": 0, "live_runs": [], "material_calls": 89, "last_error": null}`

- 自动监测 `{"at": "2026-10-05T00:00:10.071004+00:00", "status": "observing_material", "operation": "observe_material", "coverage": 5, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "new_agent_calls": 0, "live_runs": [], "material_calls": 89, "last_error": null}`

- 2026-10-05T00:00:10.143067+00:00 确认网关active0、无未知请求后，因空观察循环设置原Creation的持久`delivery.stopped=true`控制位，Owner按现有停止语义结束新工作；只写停止控制位及原因，不改Plan、资产、审核报告、Gate、预算或调用计数。现有Web缺少单作品Owner停止API，未借修改方案或取消不存在Build停止。此监护停止为操作干预，不能认领本轮自主完成。

- 自动监测 `{"at": "2026-10-05T00:00:15.115577+00:00", "status": "stopped", "operation": null, "coverage": 5, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "new_agent_calls": 0, "live_runs": [], "material_calls": 89, "last_error": null}`


## 最终结果与计量

北京时间 07:57:18 正式恢复，08:00:10 请求监护停止，08:00:15 确认 Owner stopped / operation=null；新增工作窗口约 **2分52秒**，到停止确认约 **2分57秒**。这不是素材齐备时间，也不能认领相较历史84分38秒提速。正式 `materials/readiness.json` 为 NOT_READY，Gate 为 MATERIAL_NOT_READY。

- required：**5/9（55.6%）**。沿用 A/B 与 E/G 四项覆盖；`voice_narration_full` 正式新增合格。缺口为 `img_C_pen_corner`、`img_D_pen_above_list`、`img_F_papers_beneath`、`bgm_subordinate`。
- Owner 新增 `recover_voice_timing` 1次 / 0.214511秒；`observe_material` **55次 / 累计31.983872秒**。55次是调度操作次数，包含第一次本地音乐观察及后续空观察，不是55次云端视觉调用；操作耗时不能与嵌套模型时间相加。
- Material调用88→89 /1840，唯一新增计量为本地音乐观察1次；Prepare仍7/24。新增 Provider搜索、云端视觉、agent派发、ASR、TTS、生图、报价和生成提交均0。没有新模型/网络等待样本，不能判断单次视觉模型时延已经改善。
- 两项既有生成仍complete且原资产保留，正式报价占额仍¥0.104800，授权余额¥9.895200；新增生成占额0。实际模型账单仍unknown，不能称整轮费用为零。
- 18项冻结Planning/Handoff文件SHA一致；生产源码集合SHA仍为起点值；没有运行中代码修复、代写报告或人工改审核/Gate。Authoring没有派发，execution_status=NOT_SUBMITTED，outputs为空；READY_FOR_EXTERNAL_AUTHORING只是已有输入准备状态，不是本轮进入Authoring。
- `next_operation` 为 `(None, stopped)`。人工设置停止控制位属于监护操作干预，故本段也不能认领自主完成；没有通过清零账本或继续盲重试隐藏失败。

旁白复用了原95字完整识别、实际分数与Provider字幕证据，沿普通内容/时序/Rights/Match完成准入，无新识别或重购。既有识别最低0.281995、低置信1字、字符加权均值0.987533，按获批有限规则通过；原报告与真实概率不改。BGM仍无正式合格覆盖。

## 五类问题收口

| 分类 | 本轮结论与证据 | 边界 |
|---|---|---|
| 搜索召回 | 未执行新增搜索；三项视觉缺口保留 | 不能认领来源接续、英文query或实际召回改善；也不能把空观察解释为搜索无结果 |
| 观察判断 | 旧报告待重评与新提名额度不兼容，无法执行有效重评；已覆盖A/B的旧负面报告仍可触发pending | 未产生新视觉判断，偏好误拒与模型判断能力本轮未验收 |
| 报告保存 | 无新增云端视觉报告；旧证据复用、停止状态和正式readiness已保存 | 紧凑报告的真实交付可靠性未执行，不能以无失败认领通过 |
| 音频验证 | 旁白正式通过；BGM仍缺。旁白资产误进入BGM本地音乐观察，新增1次无用工作 | 新音乐记录音频SHA与旁白一致，时长27.1635秒、5个窗口；未把旁白认领为合格BGM，不放宽音乐/人声/Rights |
| 补位策略 | **主要失败：Owner无限重复空观察，阻挡后续补料/合法生成；没有自主有界停止** | 监护停止保留现场；本轮未验证必要时生图补位，0生成不等于合理避免生成 |

## 已定位根因及最小后续范围（未实施）

1. `easel/creation_delivery.py` 的 `pending_visual_reassessment` 优先级高于补料/生成；只要旧报告待重评就返回observe，不校验本次行动是否可执行或上次有无进展。
2. `easel/materials/application/visual_observation.py` 扫描旧outcomes时没有排除已正式覆盖Need；A/B未使用的旧负面报告仍能触发待重评。
3. `easel/integrations/material_layer.py` 将重评与新候选提名共用 `9 - 历史associations数量` 条件。当前C/D/F历史数量23/23/21，额度非正，不能入批；空批却返回COMPLETE且不解除pending。Owner下轮再次选择observe，没有新付费调用或失败计数，也就不能靠调用额度/失败上限自行停止。不是余额不足或外部模型慢。
4. 同一观察入口按AUDIO/时长/Rights选BGM候选，没有先排除已知旁白用途，导致刚通过Rights的旁白被送入音乐观察。

后续仍在原A1/A2/A3/B1/B2内收敛，不另建Task或素材主链：让“待重评”与实际可执行集合一致，只重评真实缺口且有效身份相符的证据；已有关联重评不得重获新候选额度，但应有一次显式修复机会并计入累计调用边界；不可执行时明确原因并转入合法接续或有界停止，不能空完成后无限重派。已知旁白从BGM提名前排除。确定性回归应组合覆盖旧超限账本、旧负面报告、已覆盖Need和原旁白，证明有限进展/停止及无重复付费；修复通过后才另行真实复验9/9及自主性。

本轮仅记录定位，不改业务代码、不放宽必要准入、不重置预算、不再恢复制作。历史Acceptance原文保留；完整视频继续后置。


## R2 获批修复后恢复（2026-10-05，准备中）

用户另行明确批准修复调度循环和旁白误入BGM观察，验证后恢复原作品。R1失败及监护停止不改写；R2分别报告自主性、新增时间/调用和累计账本。

软件：Owner与执行器共用待重评集合，正式已覆盖Need跳过旧负面报告；当前要求版本已重评报告不重复派发。既有关联重评可在历史九项候选额度耗尽时执行有界两张批次，但不增加/清零关联额度，模型调用仍走原累计账本；没有可执行候选时明确失败而非空COMPLETE。已知生成旁白及普通逐Need旁白内容证据从BGM候选排除。

确定性全量682 passed、5 skipped（44.60秒）；扩展已有回归验证历史23项关联保留且一次重评闭合、旁白零音乐观察而缺口BGM正常观察。compileall、115项合同及diff check通过。后续新增当前要求版本拒绝不重评断言，复核后才加载/恢复。没有改冻结Plan、正式审核结论、预算、模型或Provider范围。

- R2 2026-10-05T00:16:38.202593+00:00 原Web服务安全加载修复源码后，经正式Operator delivery/retry恢复。网关/Hypit未重启；源码SHA 2bf68aa65f8c18fefa5978cc8ee1505701d53f62ca801796bc73cd15879689d5，起点5/9、Material89/1840、占额0.1048，冻结输入核对一致。

- R2 2026-10-05T00:17:21.106900+00:00 正式retry只处理exhausted_operation，未解除R1监护停止位，首次请求没有派发。按用户明确恢复授权，在原Owner执行锁下仅解除该控制位并记录history，Owner恢复pending；不改Plan、Gate、观察、累计调用/失败或费用。记录此接口控制缺口，不扩大本批代码范围。


### R2 结果：FAIL / 5 of 9 / 监护停止，生成成果保留

08:17:21解除R1监护控制后，Owner正常选择generate，C/D/F三张图片均complete。随后三次observe仅空返回：绑定生成结果仍受旧图库关联23/23/21额度阻挡。本段停止新工作时保留正在运行的原补料run，Owner沿原runId观察至ok/释放后停止，没有重派。状态stopped / next_operation=(None, stopped)，仍5/9，AUTONOMOUS=NO。

新增正式计量7次：报价3、提交3、补料建议1；Material89→96/1840。新增observe_material3次/累计1.460620秒，generate_material3次/67.837577秒，recover_material1次/1.772517秒，原run观察13次/11.189528秒。操作与等待嵌套不能求和当墙钟；云端视觉、实际图库搜索、本机音乐、ASR/TTS新增0。既有旁白不误派BGM已在真实段保持。生成占额0.1048→0.1798，余额9.8202；实际账单unknown。没有正式合格新增视觉，不能把生成complete计作覆盖。

同一调度根因的最小补充：原绑定Need的生成结果准入采用显式generated_intakes记录，图库候选associations不增不清零，正式生成授权/价格/调用账本及普通观察/Rights/Match保持；不允许生成结果默认服务全池。旧候选额度只能约束图库提名，不能废弃已授权购买结果的必要验证。扩展原image_ready恢复回归证明历史23项原样保留、绑定图片独立观察及普通准入。补充完成后继续同作品，另记R3，不倒算R2自主通过。


## R3 补齐绑定生成准入后恢复（FAILED / 自动达到失败上限）

- 2026-10-05T00:22:20.078195+00:00 全量682 passed、5 skipped（41.29秒），compileall/115合同/diff check通过。核实网关active0/queued0、全部请求终态与五项生成complete、冻结18文件一致后，仅Web加载新代码，源码SHA 1d5b2af35441892ab9671542b59d37f837efcf3b1ac07d56505dd223c2ef4443。沿原停止控制位解除及正式retry恢复原Owner；起点5/9、Material96/1840、占额0.1798，生成结果和历史保留。本段仅素材验收，不进Authoring/Build。

- R3监测 `2026-10-05T00:22:34.529948+00:00 {"status": "recovering_material", "operation": "recover_material", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 102, "live": [], "error": null}`

- R3监测 `2026-10-05T00:22:39.546639+00:00 {"status": "recovering_material", "operation": "recover_material", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 104, "live": [], "error": null}`

- R3监测 `2026-10-05T00:22:44.561551+00:00 {"status": "execution_uncertain", "operation": "observe_material", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 105, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending"}], "error": null}`

- R3监测 `2026-10-05T00:22:49.576787+00:00 {"status": "observing_execution", "operation": "observe_agent", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 105, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending"}], "error": null}`

- R3监测 `2026-10-05T00:22:54.593037+00:00 {"status": "observing_execution", "operation": null, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 105, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending"}], "error": null}`

- R3监测 `2026-10-05T00:23:04.617727+00:00 {"status": "observing_execution", "operation": "observe_agent", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 105, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending"}], "error": null}`

- R3监测 `2026-10-05T00:23:09.635251+00:00 {"status": "observing_execution", "operation": null, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 105, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending"}], "error": null}`

- R3监测 `2026-10-05T00:23:19.657562+00:00 {"status": "observing_execution", "operation": "observe_agent", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 105, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending"}], "error": null}`

- R3监测 `2026-10-05T00:23:24.672560+00:00 {"status": "observing_execution", "operation": null, "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 105, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending"}], "error": null}`

- R3监测 `2026-10-05T00:23:56.597570+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 105, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending", "created_at": "2026-10-05T00:22:42+00:00"}], "error": null}`

- R3监测 `2026-10-05T00:24:11.645199+00:00 {"status": "observing_material", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 106, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "submitting", "created_at": "2026-10-05T00:24:11+00:00"}], "error": "编排网关已确认本次执行失败；保留输入并按阶段恢复"}`

- R3监测 `2026-10-05T00:24:16.656758+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 106, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending", "created_at": "2026-10-05T00:24:11+00:00"}], "error": null}`

- R3监测 `2026-10-05T00:25:13.892085+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 106, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "run_id": "easel-699c269de33744278a4ed60829f912dd", "status": "pending"}], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 1}, "error": null}`

- R3监测 `2026-10-05T00:25:43.978866+00:00 {"status": "execution_uncertain", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 107, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "run_id": "easel-56483995c4cc4ace9b4671720fcb9e68", "status": "pending"}], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 2}, "error": null}`

- R3监测 `2026-10-05T00:25:48.993803+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 107, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "run_id": "easel-56483995c4cc4ace9b4671720fcb9e68", "status": "pending"}], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 2}, "error": null}`

- R3监测 `2026-10-05T00:27:10.514553+00:00 {"status": "failed", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 107, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "编排网关已确认本次执行失败；保留输入并按阶段恢复"}`


### R3 最终结果与根因收口

08:22:20.078有效恢复→08:27:04 Owner保存失败，新增墙钟约 **4分44秒**；素材仍NOT_READY / **5/9**，C/D/F+BGM未覆盖。原三张生成图均complete保留，失败发生在第一张C补位图的普通视觉观察；D/F生成图尚未完成观察，不把生成成功计作合格。图库关联账本A13/B13/C23/D23/E12/F21/G12保持，新增独立generated_intakes仅C1，验证已购结果确实越过图库额度进入准入。

新增正式计量 **11次**：来源适配8（local4、Pexels3、Openverse Audio1）+视觉派发3。每个视觉原run确认终态error并释放后才派下一次，三次均保留runId/history；没有因为轮询超时重发。累计Material **107/1840**，Prepare仍7/24。三次视觉运行约85.106 / 87.434 / 78.892秒，总251.432秒（含模型/网关等待，不等于纯推理耗时）。原run轮询83次/累计68.566617秒是嵌套监测，不再另加到模型/墙钟。observe_material6次/4.799174秒含派发与确认失败；recover_material1次/19.906212秒含实际供料。

三次网关日志均明确 `provider=minimax/MiniMax-M3 stopReason=length hasCurrentAttemptAssistant=yes payloads=0 tools=0`，并以format / chain_exhausted终止。第一项run `easel-b720d33675044cedad0ca7c62192a253`，之后 `easel-699c269de33744278a4ed60829f912dd`、`easel-56483995c4cc4ace9b4671720fcb9e68`。这是**模型输出截断、没有有效终态报告**，不是文件写权限、未召回图片或生成失败；本轮没有证据证明具体token配置、推理开销或提示尺寸哪个占主因，不凭length推断纯网络慢。无有效新视觉结果，报告可靠性验收失败。

Owner按原3次上限保存status=failed、exhausted_operation=<原Attempt>:observe_material；本段没有运行中代码修改、人工放行或监护停止。`next_operation`静态选择仍为observe_material，但`advance_creation`按该exhausted key阻止继续执行，不能只看选择函数判定活跃。最终执行锁可用、全部agent终态且runtime释放，网关active0/queued0；未再次retry。

#### 本段实际来源与query（不是全部Provider均调用）

| Need | 来源 / 实际query | 回召 / 获取 |
|---|---|---|
| C | Pexels / `still life single pen at desk edge paper list softly blurred behind shallow depth` | 20候选 / 3获取记录 |
| D | Pexels / `top down single pen horizontal tip hovering above handwritten list shallow focus` | 20 / 3 |
| F | Pexels / `low angle top list notebook extra page corners peeking out from beneath` | 20 / 3 |
| BGM | Openverse Audio / `solo piano background music no vocals 60 to 80 bpm calm 45 seconds` | 0 / 0 |

另有local来源4次（无query）：三项视觉0/0；BGM1候选/0新获取。获取记录不等于唯一字节数或合格数量；新增正式合格0。当前音频query仍含时长等词，本批没有扩大到query编译重构或新Provider建设。英文查询实际参与不等于已经证明召回/提速改善。

#### 五类最终分类

- 搜索召回：实际Pexels有返回；BGM Openverse Audio本query零返回，仍缺正式音乐与Rights闭环。没有证据将视觉失败归因零召回。
- 观察判断：没有有效新结果，正确性未验证；已有四项视觉与旁白合格保持。
- 报告保存：**主阻塞**，三次模型length后未交付有效报告，不能越过合同或把故障转为再次生成。
- 音频验证：旁白已有普通准入保持，R2/R3新增ASR/TTS/音乐观察均0；旁白误入BGM已消除，BGM未合格。
- 补位策略：三张图片按授权完成且C进入普通观察，生成结果不受旧图库额度丢弃；后续因报告故障有界停止。补位“生成→正式准入→齐备”的完整效果仍未通过。

最新源码SHA保持 `1d5b2af35441892ab9671542b59d37f837efcf3b1ac07d56505dd223c2ef4443`；18项冻结输入不变。R3没有新生成/报价，占额仍¥0.1798、剩余¥9.8202，实际账单unknown；全部旧失败及累计计量保留。execution_status=NOT_SUBMITTED、outputs={}，没有Authoring/Build/成片审阅。

本次软件修复验证通过，但作品交付未通过。R3由Owner自主有界停止，不等于自主完成；整个R1–R3含工程诊断及监护停止，仍AUTONOMOUS=NO。没有同条件成功基线，不宣称提速比例。后续最小范围是核对真实视觉请求的输出容量、推理/回复交付及失败恢复合同，先有限真实报告能力验证，不能再盲重试当前作品。本批不继续改报告链路、换模型/服务或重新运行；不创建平行Task。


## R4 输出截断根因修复与原作品恢复（2026-10-05，验证中）

用户批准“查下根因，修复后继续”。只读R3具名会话SQLite transcript确认：三次实际处于无图片的“审核要求编译”，输入相同，assistant仅两个换行、stopReason=length，usage为网关投影的0而非可靠模型账单。因此前文“视觉派发3”是素材阶段计量分类，不代表已完成三次实际看图；R3尚未到画面事实观察。

官方合同[MiniMax OpenAI SDK](https://platform.minimaxi.com/docs/api-reference/text-openai-api.md)明确：M3省略thinking默认adaptive，thinking token计入max_tokens，上限不足可length且正文为空；M3可用thinking.type=disabled，M3.1 Flash不能关闭。当前安装OpenClaw2026.9.4的MiniMax禁思考wrapper仅作用于anthropic-messages；本作品为openai-completions，通用--thinking off会省略reasoning_effort，未提供原生thinking。model.reasoning=false只是元数据，不等价于Provider关闭思考。旧本机配置也没有M3 extra_body开关。

通过当前安装OpenClaw真实applyExtraParamsToAgent的离线wire模拟，修复前thinking=null、max_tokens=8192，修复后thinking={type:disabled}、max_tokens仍8192；未联网推理。新增幂等本机配置脚本scripts/configure_minimax_m3_thinking.py，仅精确MiniMax-M3+OpenAI主模型允许，保留其他模型/授权/参数，拒绝M3.1/M2/其他通道。原配置备份及配置只留本机受保护目录，0600，不进入Git/运行产物/聊天；仓库仅脚本和无凭证回归。

10:35:21网关日志确认config hot reload applied (agents.defaults.models.minimax/MiniMax-M3)，无Web/网关/Hypit重启、无新服务/模型，也未提高8192输出上限。合同回归1passed，原Gateway/terminal/runtime6passed；最终全量完成后才正式恢复。保留R1–R3失败、当前5/9、三张生成图、Material107/1840和占额0.1798，不代写要求分类或观察结论。

- R4 2026-10-05T02:37:38.926630+00:00 全量683 passed、5 skipped（44.29秒），原冻结输入/未知提交/预算复核通过，正式Operator delivery/retry恢复同作品。按原入口重置当前exhausted步骤恢复计数，R3原run及错误history保留；累计调用、授权、生成占额不重置。没有服务重启。

- R4监测 `2026-10-05T02:37:39.011781+00:00 {"status": "pending", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 107, "live": [], "failures": {}, "error": null}`

- R4监测 `2026-10-05T02:37:44.028179+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 108, "live": [{"id": "070f6dbc91c15ebe247a59b12648a4c0bfe1d18db9175cf7ef5930f6cbae51f6", "status": "pending", "run_id": "easel-7662e6a05c3948209e449dfc5a0ba0db"}], "failures": {}, "error": null}`

- R4监测 `2026-10-05T02:37:49.041631+00:00 {"status": "retrying", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 108, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 1}, "error": "运行结果缺失、截断、超出协议容量或包含敏感内容；保留原运行，不重新派发"}`

- R4监测 `2026-10-05T02:37:54.058504+00:00 {"status": "failed", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 108, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "运行结果缺失、截断、超出协议容量或包含敏感内容；保留原运行，不重新派发"}`


### R4 结果及补充诊断（同一用户批准范围）

10:37:38.927恢复后，原编译run在10:37:45以stop正常结束，正文NO_REPLY、terminalDisposition=not-visible；原报告入口拒绝该结果并复用同run，约15秒内按原失败上限停为failed，仍5/9。新增1次模型派发，Material107→108。这是报告合同失败，不是素材不适合；不能把无正文正常终态当成准入成功。新原生参数确实消除了这一运行的length，但复杂编译可靠性仍未通过。

新增两次已授权诊断均计入原素材账本：原生M3接口的小型固定JSON请求，thinking.disabled/max_tokens512，4.274秒、finish_reason=stop、无thinking正文、正确14字符JSON，usage提示173输入/6输出token（不把网关历史0当账单）；原OpenClaw通道的干净会话也返回同样有效JSON，未另建正式生产入口或将诊断响应当Material报告。累计调用108→110。诊断证明本机原生禁思考和原Gateway基本交付都可工作；复杂旧编译会话已包含三次截断重放，不能将NO_REPLY归因所有M3禁思考都不可用。

最小报告恢复修复：有效编译/事实缓存仍按原输入身份复用；新执行策略revision仅给失败请求新会话，避免沿用截断会话，不清累计额度。silent/容量等已确认无效终态作为报告故障交给原一次修复，持久无效结果避免同条件重发；不吞未知运行或工具/网关异常，不伪造观察结论。要求编译的一次修复增加明确校验反馈，要求和实际观察明确NO_REPLY不是协议输出；实图看不清仍unknown。扩展既有跨Need/中断恢复回归，证明silent编译一次修复、有效前子项复用及Rights不变。全量通过并加载后再继续原作品，另记R5。


## R5 原生思考开关及干净报告恢复（FAILED / 5 of 9）

- 2026-10-05T04:20:25.026875+00:00 全量684 passed、5 skipped（41.59秒），compileall/115合同/diff check通过。冻结18文件、无未知/活动请求、原预算核实，Web加载修复后正式retry原Attempt。起点5/9、Material110/1840（含两项能力诊断）、占额0.1798；源码SHA 4a5aa76438e0209e47e596e06350a9be9c280adb9f530ace6cb1100828241f9c，网关/Hypit未重启。

- R5监测 `2026-10-05T04:20:25.102700+00:00 {"status": "pending", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 110, "live": [], "failures": {}, "error": null}`

- R5监测 `2026-10-05T04:20:30.117393+00:00 {"status": "observing_material", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 111, "live": [{"id": "abc59d4d244b4dd49b202e39c09c011fedd597b7a6fbb1941e84b63d6c34e25d", "status": "submitting", "run_id": "easel-b4945fd8a9324814ae8ad85ad2ef350e"}], "failures": {}, "error": null}`

- R5监测 `2026-10-05T04:20:35.135287+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 111, "live": [{"id": "abc59d4d244b4dd49b202e39c09c011fedd597b7a6fbb1941e84b63d6c34e25d", "status": "pending", "run_id": "easel-b4945fd8a9324814ae8ad85ad2ef350e"}], "failures": {}, "error": null}`

- R5监测 `2026-10-05T04:20:45.156483+00:00 {"status": "execution_uncertain", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 112, "live": [{"id": "d9a339ed8882fffc07983f0ecc64c6e1296043c5fb1e8cb6f691465427ac1456", "status": "pending", "run_id": "easel-21d022a4825a4cddb6b4bd71f3602d81"}], "failures": {}, "error": null}`

- R5监测 `2026-10-05T04:20:50.173495+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 112, "live": [], "failures": {}, "error": null}`

- R5监测 `2026-10-05T04:20:55.187586+00:00 {"status": "retrying", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 112, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 2}, "error": "审核要求一次修复后仍未完整：审核要求须有完整且有界的原文条款"}`

- R5监测 `2026-10-05T04:21:00.199839+00:00 {"status": "failed", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 112, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "审核要求一次修复后仍未完整：审核要求须有完整且有界的原文条款"}`


### R5 根因与合同修复

12:20:25→12:21:00，约35秒内有界失败，Material110→112，两次要求编译均正常交付正文，无新length；没有实图观察、生成或音乐验证。首份493字符JSON把139字原文的末尾报为150，漏空格、越界等导致完整覆盖校验失败；一次修复的1269字符JSON另带Markdown围栏，仍有错误偏移。故主因是**把精确字符索引交给模型计算**，不是当前视觉素材不适合；未知/错误合同不得触发生图或放行。旧失败响应和账本保留。

最小修复让模型逐段逐字引用冻结原文并分类，由程序绑定实际位置，仍要求不重叠、完整覆盖及显式偏好不得升级必要项；已有数值合同保持兼容。输入加入引用协议身份，自然隔离旧无效结果，不清任何缓存或额度。仅接收完整单一JSON围栏，不提取混杂正文中的片段。有效合同/事实、逐Need判断、Rights及普通准入保持；修复反馈及一次修复上限保持。确定性组合回归涵盖silent→围栏恢复、原文缺字拒绝、有效前子项复用及Rights不变。下一段R6在验证/对账后沿原作品恢复，不能倒算R5自主通过。


## R6 原文引用合同恢复（FAILED / 5 of 9）

- 2026-10-05T11:37:55.450049+00:00 验证686 passed/5 skipped（40.48秒）及围栏恢复组合6 passed，compileall/115合同/diff check通过。18冻结文件不变、65运行终态释放、网关active0/queued0、Owner锁可用、5项生成complete；仅Web加载新业务版本，网关/Hypit未重启。正式retry同Attempt，起点5/9、Material112/1840、占额0.1798，源码SHA 21f97221d124eb479d89ee5af1cd3c655c8a8afb63f551f7201cc65fe2cf5a52，终点仅MATERIAL_READY。

- R6监测 `2026-10-05T11:38:13.964452+00:00 {"status": "execution_uncertain", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 114, "live": [{"id": "01dca378d23889f92d9fbeb6a9c1ede2edafab60382504dd1b6659572eda70bd", "status": "pending", "run_id": "easel-b7957ec8a1404df1807c106211d1d62d"}], "failures": {}, "error": null}`

- R6监测 `2026-10-05T11:38:18.981409+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 114, "live": [{"id": "01dca378d23889f92d9fbeb6a9c1ede2edafab60382504dd1b6659572eda70bd", "status": "pending", "run_id": "easel-b7957ec8a1404df1807c106211d1d62d"}], "failures": {}, "error": null}`

- R6监测 `2026-10-05T11:38:23.994942+00:00 {"status": "retrying", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 114, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 2}, "error": "审核要求一次修复后仍未完整：条款须逐段逐字引用冻结原文，不能改写、遗漏或重排"}`

- R6监测 `2026-10-05T11:38:29.006391+00:00 {"status": "failed", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 114, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "审核要求一次修复后仍未完整：条款须逐段逐字引用冻结原文，不能改写、遗漏或重排"}`


R6 19:37:55→19:38:29，约34秒有界失败，Material112→114。两次回复完整且未截断；但编译输入同时提供sources与完整Need中的同义字段，模型产生重复整段/子段、1基编号及过长query，逐字覆盖校验拒绝。没有进入实图、生成或音乐调用。最小输入修正仅传单份原文及明确0基source编号，完整冻结输入摘要保留；来源不增删，要求、分类及正式准入不变。旧失败结果保留，新输入身份隔离；不清额度。下一段另记R7。


## R7 单份编号原文编译恢复（FAILED / 5 of 9）

- 2026-10-05T11:41:10.352067+00:00 全量686 passed、5 skipped（43.62秒），compileall/115合同/diff check通过；18冻结文件、原账本及全部终态/释放核实。仅Web加载，正式retry原作品。起点5/9、Material114/1840，源码SHA d6a586d61ecd20708e07cf33da03312327914fd0d37247165e70e64b31b3b0cd；不新增服务或预算，终点仅MATERIAL_READY。

- R7监测 `2026-10-05T11:41:10.394382+00:00 {"status": "pending", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 114, "live": [], "failures": {}, "error": null}`

- R7监测 `2026-10-05T11:41:15.406457+00:00 {"status": "execution_uncertain", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 115, "live": [{"id": "81b4e87a030da3383ecdb3c7d154fd94085b836f1a0ae9aabc829f9e161df08e", "status": "pending", "run_id": "easel-2d590eb8754e4ffeb1b7b303269af482"}], "failures": {}, "error": null}`

- R7监测 `2026-10-05T11:41:20.418927+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 115, "live": [{"id": "81b4e87a030da3383ecdb3c7d154fd94085b836f1a0ae9aabc829f9e161df08e", "status": "pending", "run_id": "easel-2d590eb8754e4ffeb1b7b303269af482"}], "failures": {}, "error": null}`

- R7监测 `2026-10-05T11:41:25.427386+00:00 {"status": "execution_uncertain", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 116, "live": [{"id": "2610a92e03acec0a8c1679f7ff5de1fb72ae600b1d257244039bf2e71ed11156", "status": "pending", "run_id": "easel-43561c12a0d048149506b7303f740ea9"}], "failures": {}, "error": null}`

- R7监测 `2026-10-05T11:41:30.438185+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 116, "live": [{"id": "2610a92e03acec0a8c1679f7ff5de1fb72ae600b1d257244039bf2e71ed11156", "status": "pending", "run_id": "easel-43561c12a0d048149506b7303f740ea9"}], "failures": {}, "error": null}`

- R7监测 `2026-10-05T11:41:35.446505+00:00 {"status": "retrying", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 116, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 2}, "error": "审核要求一次修复后仍未完整：审核要求须有完整且有界的原文条款"}`

- R7监测 `2026-10-05T11:41:40.454911+00:00 {"status": "failed", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 116, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "审核要求一次修复后仍未完整：审核要求须有完整且有界的原文条款"}`


R7 19:41:10→19:41:40，约30秒有界失败，Material114→116；编号及引用恢复正确，但首份kind=null，一次修复则把required/preference作为裸JSON标识符。实际提示的形状示例含未加引号的kind与中文占位符，是不合法JSON，对无思考结构化输出形成明确歧义。将示例修为合法JSON对象，分类值全带双引号且显式字段，仍由模型负责语义，绝不程序猜null或解析裸词。原失败保留；该输入协议revision变更后另记R8，未实图观察或购买。


## R8 合法JSON对象编译恢复（FAILED / 5 of 9）

- 2026-10-05T11:49:28.683049+00:00 全量686 passed、5 skipped（43.38秒），compileall/115合同/diff check通过。初次终态预检未通过断言，未retry；复核确认所有请求终态释放/网关active0queued0/Owner锁空闲及18冻结文件不变后正式retry；仅Web加载，网关/Hypit未重启。原作品起点5/9、Material116/1840，源码SHA 37d5ba5fabe5d155ea4f6c521b60dce4cf26d7592b4c9183c9a273b642278c2b，授权及累计历史保持。

- R8监测 `2026-10-05T11:49:28.827614+00:00 {"status": "pending", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 116, "live": [], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:49:33.840826+00:00 {"status": "execution_uncertain", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 117, "live": [{"id": "f431ab8ff9faf1cb74bf3c5edd79433695494d1687a6be2998df749c05ca7024", "status": "pending", "run_id": "easel-113064c619bf43648c7bd2a86f164d9e"}], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:49:38.852923+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 117, "live": [{"id": "f431ab8ff9faf1cb74bf3c5edd79433695494d1687a6be2998df749c05ca7024", "status": "pending", "run_id": "easel-113064c619bf43648c7bd2a86f164d9e"}], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:49:43.865340+00:00 {"status": "observing_material", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 118, "live": [{"id": "b716bc22a37bfc322b4da4a2b63d29cea5bef2357edb9b2e930f99bce1e462ac", "status": "submitting", "run_id": "easel-2d278531c8b84afe9a9af8c44d49be3b"}], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:49:48.874337+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 118, "live": [{"id": "b716bc22a37bfc322b4da4a2b63d29cea5bef2357edb9b2e930f99bce1e462ac", "status": "pending", "run_id": "easel-2d278531c8b84afe9a9af8c44d49be3b"}], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:49:58.897264+00:00 {"status": "observing_material", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 119, "live": [{"id": "2dcfd34f2359420676723e42d29bd41aef174e557a8b2cbd8fca841c329b7c63", "status": "submitting", "run_id": "easel-92d0e4342b2c461e87dd92dd0a7ff9aa"}], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:50:03.908064+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 119, "live": [{"id": "2dcfd34f2359420676723e42d29bd41aef174e557a8b2cbd8fca841c329b7c63", "status": "pending", "run_id": "easel-92d0e4342b2c461e87dd92dd0a7ff9aa"}], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:50:08.917028+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 119, "live": [], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:50:13.925507+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 120, "live": [{"id": "299581d4d1e8aa1090d36de175e87186342c1b52fffc634625af0ae735d5cf69", "status": "pending", "run_id": "easel-e93fbfdceb364bbf8ffa0d8ff39e96ce"}], "failures": {}, "error": null}`

- R8监测 `2026-10-05T11:50:18.931925+00:00 {"status": "retrying", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 120, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 1}, "error": "素材结果一次修复后仍无效：必要项漏报、重复或编号错误"}`

- R8监测 `2026-10-05T11:50:23.943956+00:00 {"status": "failed", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 120, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "素材结果一次修复后仍无效：必要项漏报、重复或编号错误"}`


R8 19:49:28→19:50:23，约55秒有界失败，Material116→120（编译1+真实观察3；含一次正常修复及不同校验反馈的失败复用路径）。合法JSON编译一次成功，实图附件确已观察；但结果混入偏好编号2/3/4、生成非合同partly_met，偏好/亮度被用作必要项拒绝依据，“承载停顿”被当作图像必须呈现动态暂停。报告校验拒绝，无正式新覆盖，未生成/重购。最小修复：偏好传无检查编号的纯文本，检查名单/允许状态显式，部分必要不符仍not_met；编译明确叙事/剪辑节奏的postproduction职责，含必要和显式偏好的段落须拆分。仍保留源动作、真实证据、完整原文及普通准入；编译策略身份隔离未完成Need旧分类，不重审已有有效正式报告。下一段R9，历史记录与额度保持。


## R9 观察合同隔离恢复（FAILED / 5 of 9）

- 2026-10-05T11:53:23.706348+00:00 全量686 passed、5 skipped（42.55秒），compileall/115合同/diff check通过；18冻结输入、全部终态释放、网关active0queued0及Owner锁空闲对账通过后，仅Web加载，正式retry原Attempt。起点120/1840、5/9、占额0.1798；源码SHA 9d169f855d25fc453665989221dd35a06be6fb0019c251d2fb49a78662477fa3，网关/Hypit未重启，终点仅MATERIAL_READY。

- R9监测 `2026-10-05T11:53:29.632898+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 121, "live": [{"id": "21a2ff4c4926154b5e210013c0df9bac8a9b8eb4cc37ebdab77659845d6383e9", "status": "pending", "run_id": "easel-7e68394e939e47e4bf524f36ab105740"}], "failures": {}, "error": null}`

- R9监测 `2026-10-05T11:53:34.646177+00:00 {"status": "execution_uncertain", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 122, "live": [{"id": "506a517d0d76f8f96b4e29fd3fc5663c6309610d8831e445204120698ddf8ef2", "status": "pending", "run_id": "easel-f1877935f7af4ffd98d38de99029e8ba"}], "failures": {}, "error": null}`

- R9监测 `2026-10-05T11:53:39.656402+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 122, "live": [{"id": "506a517d0d76f8f96b4e29fd3fc5663c6309610d8831e445204120698ddf8ef2", "status": "pending", "run_id": "easel-f1877935f7af4ffd98d38de99029e8ba"}], "failures": {}, "error": null}`

- R9监测 `2026-10-05T11:53:44.669551+00:00 {"status": "execution_uncertain", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 123, "live": [{"id": "a73f06276fab1b4024409b4a78d19ac0674eca8f0cfe9c3cef1381c1dc16dc73", "status": "pending", "run_id": "easel-bec45875a0b44736bd563e781c7a1d9b"}], "failures": {}, "error": null}`

- R9监测 `2026-10-05T11:53:49.681965+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 123, "live": [{"id": "a73f06276fab1b4024409b4a78d19ac0674eca8f0cfe9c3cef1381c1dc16dc73", "status": "pending", "run_id": "easel-bec45875a0b44736bd563e781c7a1d9b"}], "failures": {}, "error": null}`

- R9监测 `2026-10-05T11:53:54.697771+00:00 {"status": "retrying", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 123, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 1}, "error": "审核要求仍有歧义，先由 Planning 澄清，未提交观察"}`

- R9监测 `2026-10-05T11:53:59.712630+00:00 {"status": "failed", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 123, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "审核要求仍有歧义，先由 Planning 澄清，未提交观察"}`


R9 19:53:23→19:53:59，约36秒有界失败，Material120→123，3次编译，未观察。模型把显式偏好中的重复主体升级required，修复又标unresolved；已有硬要求与偏好重复被错当冲突，Gate正确停止。最小职责修正：显式preferred字段已有冻结语义，由程序按原文登记preference；模型只解释混合intent，显式偏好作为无重复分类的上下文。必要主体保持required，重复风格/构图可引用原偏好；仍完整校验所有来源，真实歧义保留unresolved。不是人工选择审核结论，也不改冻结Need/导演语言；有效报告优先复用。下一段R10，历史额度保留。


## R10 明确偏好语义与普通观察恢复（PARTIAL / 6 of 9）

- 2026-10-05T11:56:54.626734+00:00 全量686 passed、5 skipped（41.81秒），compileall/115合同/diff check通过。18冻结文件及所有原请求/累计账本核实后仅Web加载；首次HTTP session请求因服务尚启动connection refused，未执行retry；服务可用后正式retry，无重复制作/模型提交。起点5/9、Material123/1840、占额0.1798；源码SHA 6859cc0b866cec161c7b2bb04022de57c8aa1715b862f3b90208ad3468886796，网关/Hypit未重启，终点MATERIAL_READY。

- R10监测 `2026-10-05T11:56:54.670378+00:00 {"status": "pending", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 123, "live": [], "failures": {}, "error": null}`

- R10监测 `2026-10-05T11:56:59.689809+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 124, "live": [{"id": "c92b816199f192480643c630fafaf59561a2eb41679a0ad79981a8f4053881f7", "status": "pending", "run_id": "easel-9f1ed52f35e942af84c9db9a032485f1"}], "failures": {}, "error": null}`

- R10监测 `2026-10-05T11:57:04.716878+00:00 {"status": "observing_material", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 124, "live": [], "failures": {}, "error": null}`

- R10监测 `2026-10-05T11:57:09.733354+00:00 {"status": "observing_execution", "blocking": ["img_C_pen_corner", "img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 125, "live": [{"id": "266301608bb5f76393e4f92d8ccdb2082a88cee3c0e71f556f29122a8bf13db1", "status": "pending", "run_id": "easel-a24a26c8ab3a466682662382c0746e35"}], "failures": {}, "error": null}`

- R10监测 `2026-10-05T11:57:14.750575+00:00 {"status": "material_supply_exhausted", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 125, "live": [], "failures": {}, "error": null}`


R10 19:56:54→19:57:14进入material_supply_exhausted，约20秒。两次模型请求（要求编译/实际图观察各1）有效交付，C已通过普通观察、Match和Gate，正式required **6/9**，D/F+BGM仍缺；累计Material123→125，无新生成/音乐/TTS/ASR。新增observe_material3次/4.230519秒，原run轮询4次/5.004023秒为嵌套记录；单次模型时间另对账，不混加作墙钟。

新调度根因：执行器允许绑定生成图独立准入，但candidate_progress优先按23/21项历史图库关联标budget_exhausted，即使next_candidates明确有已购D/F图片；Owner只认batch_complete，因而错误停为material_supply_exhausted。修正进度与Owner判断共用已完成静态补位真实待准入依据；老COMPLETE投影也可恢复，普通观察/权利不绕过。生成结果的回填不再污染图库associations，保留既有历史而不清零。扩展现有生成/重启合同回归为多Need已购排队场景，验证跨批至MATERIAL_READY、不重购且旧stock账本不增加。下一段R11，仅继续剩余准入；R10有进展但非交付成功。


## R11 多张补位接续（FAILED / 6 of 9）

- 2026-10-05T12:05:18.756476+00:00 全量687 passed、5 skipped（42.37秒），compileall/115合同/diff check通过；18冻结输入、全部终态释放、网关active0queued0及Owner锁空闲对账通过后，仅Web加载，沿原Owner自动接续原Attempt，不清失败/控制位。起点125/1840、6/9、占额0.1798；源码SHA a2449aa9dc1d4f086e2b830c271d6d0b2d9ba496fcb4ee9e87aa60f68593c770，网关/Hypit未重启，终点仅MATERIAL_READY。

- R11监测 `2026-10-05T12:05:27.335895+00:00 {"status": "observing_execution", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 126, "live": [{"id": "53b7ad322948955c7855d47ea4e9d0ea6b12c435ea53ffe046d761b39ddd309f", "status": "pending", "run_id": "easel-06ee0a2019394209bf4229c05de65021"}], "failures": {}, "error": null}`

- R11监测 `2026-10-05T12:05:37.363342+00:00 {"status": "observing_material", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 127, "live": [{"id": "66c0f9e9a6bb3f47e905c9944a3fbfb03804eb1dadf9cdcf4a0889f20c83d27a", "status": "submitting", "run_id": "easel-1e4b9e5a7248456393b787b589ac7eb7"}], "failures": {}, "error": null}`

- R11监测 `2026-10-05T12:05:42.379113+00:00 {"status": "observing_execution", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 127, "live": [{"id": "66c0f9e9a6bb3f47e905c9944a3fbfb03804eb1dadf9cdcf4a0889f20c83d27a", "status": "pending", "run_id": "easel-1e4b9e5a7248456393b787b589ac7eb7"}], "failures": {}, "error": null}`

- R11监测 `2026-10-05T12:05:52.395762+00:00 {"status": "execution_uncertain", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 128, "live": [{"id": "3b44b7aa7a8ddf85f30ae6afe9f9996eb0f2c6bd7f7c35bcb1f175f62d84f7f3", "status": "pending", "run_id": "easel-2c725a1871aa4f8c89389ef7a27f7e67"}], "failures": {}, "error": null}`

- R11监测 `2026-10-05T12:05:57.407086+00:00 {"status": "observing_execution", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 128, "live": [{"id": "3b44b7aa7a8ddf85f30ae6afe9f9996eb0f2c6bd7f7c35bcb1f175f62d84f7f3", "status": "pending", "run_id": "easel-2c725a1871aa4f8c89389ef7a27f7e67"}], "failures": {}, "error": null}`

- R11监测 `2026-10-05T12:06:02.419301+00:00 {"status": "retrying", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 128, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 2}, "error": "审核要求一次修复后仍未完整：条款须逐段逐字引用冻结原文，不能改写、遗漏或重排"}`

- R11监测 `2026-10-05T12:06:07.430750+00:00 {"status": "failed", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 128, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "审核要求一次修复后仍未完整：条款须逐段逐字引用冻结原文，不能改写、遗漏或重排"}`


R11 20:05:18→20:06:07，约49秒有界失败，Material125→128，3次要求编译；Owner确实自动接续D，C旧有效报告未重审。D编译仍反复漏空格、把偏好原文重列到必要来源。说明只把字符索引移到程序仍不充分：模型逐字复制也不可靠。最终职责收敛为程序按标点无损切分带稳定id的原文片段，模型只返回id分类和query；位置、空格/标点及显式preferred登记均由程序绑定。所有单元必须有且仅有一次，仍检验完整覆盖、hard/preference边界、真实歧义与普通准入；不由程序猜分类，不人工落报告。协议身份变更保留旧无效缓存。下一段R12在组合验证和原账本/请求检查后继续；根因与失败继续分类保留。


## R12 固定原文单元分类恢复（FAILED / 7 of 9）

- 2026-10-05T12:10:52.758090+00:00 全量690 passed、5 skipped（43.83秒），compileall/115合同/diff check通过。18冻结文件/原请求/账本核实后仅Web加载；初次session请求服务启动尚未可用，未制作retry，服务可用后正式retry。起点6/9、Material128/1840、占额0.1798；源码SHA d2f138e41b5b6c9ab93f1dc59fcd4bcaa9b4a87f60a1298babebfc468ab8ab1f，网关/Hypit未重启，终点MATERIAL_READY。

- R12监测 `2026-10-05T12:10:52.798137+00:00 {"status": "pending", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 128, "live": [], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:10:57.815186+00:00 {"status": "execution_uncertain", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 129, "live": [{"id": "7b1c983c9d9a1eed256ba9dc59ba219a2d8687ad9dbe43b9b82f367c898ca098", "status": "pending", "run_id": "easel-b786d0e31cf2483380122b2115f964b0"}], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:11:02.823710+00:00 {"status": "observing_execution", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 129, "live": [{"id": "7b1c983c9d9a1eed256ba9dc59ba219a2d8687ad9dbe43b9b82f367c898ca098", "status": "pending", "run_id": "easel-b786d0e31cf2483380122b2115f964b0"}], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:11:07.846745+00:00 {"status": "observing_material", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 130, "live": [{"id": "61594a14db423a14a9d5dcb24c04281f648e6c758499163b7f6662bda1e916ad", "status": "submitting", "run_id": "easel-62e9ea5c4f044573bb0ce54b33c899ae"}], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:11:12.863209+00:00 {"status": "observing_execution", "blocking": ["img_D_pen_above_list", "img_F_papers_beneath", "bgm_subordinate"], "calls": 130, "live": [{"id": "61594a14db423a14a9d5dcb24c04281f648e6c758499163b7f6662bda1e916ad", "status": "pending", "run_id": "easel-62e9ea5c4f044573bb0ce54b33c899ae"}], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:11:17.880915+00:00 {"status": "observing_material", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 131, "live": [{"id": "2a0f3f9f74c26de7bee4d4ed88055120a908f1733f2b246e47d150a9fb260ef1", "status": "submitting", "run_id": "easel-ac573ea3698b4641b1833bc6c8ff0597"}], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:11:22.893788+00:00 {"status": "observing_execution", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 131, "live": [{"id": "2a0f3f9f74c26de7bee4d4ed88055120a908f1733f2b246e47d150a9fb260ef1", "status": "pending", "run_id": "easel-ac573ea3698b4641b1833bc6c8ff0597"}], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:11:42.952978+00:00 {"status": "execution_uncertain", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 132, "live": [{"id": "7c6bc93a9bb2b34f2bfbb685253ac2986a54f188456b6c5b1c943ebc39a8da3b", "status": "pending", "run_id": "easel-d99a72e3c03549aebe354edf85090843"}], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:11:47.966496+00:00 {"status": "observing_execution", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 132, "live": [{"id": "7c6bc93a9bb2b34f2bfbb685253ac2986a54f188456b6c5b1c943ebc39a8da3b", "status": "pending", "run_id": "easel-d99a72e3c03549aebe354edf85090843"}], "failures": {}, "error": null}`

- R12监测 `2026-10-05T12:12:13.988259+00:00 {"status": "retrying", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 134, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 1}, "error": "素材结果一次修复后仍无效：观察事实缺失或超出容量"}`

- R12监测 `2026-10-05T12:12:18.998850+00:00 {"status": "failed", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 134, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:observe_material": 3}, "error": "素材结果一次修复后仍无效：观察事实缺失或超出容量"}`


R12 20:10:52→20:12:18，约86秒有界失败，Material128→134，D正式普通准入通过，**7/9**。D编译及图观察各1且有效；F编译1及图结果3（原一次修复/反馈不同产生第三身份），没有新生成/音频购买。F完整JSON不到3000协议容量，却被style32/preference_notes32/basis48等模型字符上限误拒，是真报告合同过严；同一旁白/预算及冻结Plan保持。另有F叙事function按逗号切分导致“not removed”丢失叙事上下文并被当成必须证明过去移除状态。最小修正function原句作为单元并向模型明确来源职责；明确源动作/证据仍required。按实际整份3000 UTF-16总容量保留严格检查，不对有效短事实再设人工细字段拒绝，不截断正文或依据。扩展原风险测试覆盖长偏好记录可保存、整份超限拒绝、叙事function整句，继续逐Need准入。下一段R13，仅剩F+BGM；历史调用、失败及占额保留。


## R13 完整叙事及总容量（PARTIAL / 7 of 9）

- 2026-10-05T12:16:29.829895+00:00 全量692 passed、5 skipped（42.23秒），compileall/115合同/diff check通过；18冻结输入、全部终态释放、网关active0queued0及Owner锁空闲对账通过后，仅Web加载，正式retry原Attempt。起点134/1840、7/9、占额0.1798；源码SHA 21faa7922ca740db486508d2f8523716bd4061b769edde0b1582dbc34d9e41a3，网关/Hypit未重启，终点仅MATERIAL_READY。

- R13监测 `2026-10-05T12:16:53.691136+00:00 {"status": "material_supply_exhausted", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 136, "live": [], "failures": {}, "error": null}`


R13 20:16:29→20:16:53，约24秒，Material134→136，两次完整有效报告（F编译/观察各1），无报告故障。但F被判unsuitable的唯一负面依据为“没有向上揭示镜头运动”，纸张及其他必要项均met，属于静态图摄影机运动职责误拒，不是缺页或真实动作不足。修复观察解释：静态图只核验该句中必要主体/数量/源状态，镜头运动保留后期职责；明确源动作/真实证据仍必要。只对结构化报告负面项全部为此旧误拒者有界重评一次，版本身份变更，不手改结论；已合格C/D及其他有效报告不重审。

配乐来源补充只读核实：官方incompetech单曲目录pieces.json返回At Rest / USUAN1100748，明确Piano, Voice, Strings, Choir，不能仅因旧本地标CC-BY就认领无声乐BGM；不补猜许可或放行。原恢复两批实际BGMquery均长句/参数堆叠，未实际使用现Compiler中的piano instrumental短备选。下一有限修复在原Owner/恢复记录内接续一次未用的已编译音频查询，保留同总账/历史，不新增来源或音乐生成，不重获全量检索额度。


## R14 观察合同隔离恢复（FAILED / 8 of 9）

- 2026-10-05T12:25:07.629840+00:00 全量694 passed、5 skipped（43.58秒），最后两处绑定生成优先修正的组合29项通过，compileall/115合同/diff check通过；18冻结输入、全部终态释放、网关active0queued0及Owner锁空闲对账通过后，仅Web加载，沿原Owner自动接续原Attempt，不清失败/控制位。起点136/1840、7/9、占额0.1798；源码SHA 53c5f2cf20907c308aba1bec06595ca9fe6d335dcd09261cc5097a93cb312f20，网关/Hypit未重启，终点仅MATERIAL_READY。

- R14监测 `2026-10-05T12:25:16.007524+00:00 {"status": "observing_execution", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 137, "live": [{"id": "66b0daf7f8bc4b3aafcf517dc06de63379eddac68940fc6f35d0b9501d160463", "status": "pending", "run_id": "easel-6252675684b946138bf2090c9023d76d"}], "failures": {}, "error": null}`

- R14监测 `2026-10-05T12:25:26.037762+00:00 {"status": "execution_uncertain", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 138, "live": [{"id": "1df0e0b401796f837fb80f7e59ff4d119c677c5a4823ff00c879ab8ef301521a", "status": "pending", "run_id": "easel-3a3e166105c0406ab91c19cf5a1f57a1"}], "failures": {}, "error": null}`

- R14监测 `2026-10-05T12:25:31.045565+00:00 {"status": "observing_execution", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 138, "live": [{"id": "1df0e0b401796f837fb80f7e59ff4d119c677c5a4823ff00c879ab8ef301521a", "status": "pending", "run_id": "easel-3a3e166105c0406ab91c19cf5a1f57a1"}], "failures": {}, "error": null}`

- R14监测 `2026-10-05T12:25:41.066971+00:00 {"status": "observing_material", "blocking": ["img_F_papers_beneath", "bgm_subordinate"], "calls": 138, "live": [], "failures": {}, "error": null}`

- R14监测 `2026-10-05T12:25:46.079442+00:00 {"status": "recovering_material", "blocking": ["bgm_subordinate"], "calls": 140, "live": [], "failures": {}, "error": null}`

- R14监测 `2026-10-05T12:25:51.083454+00:00 {"status": "recovering_material", "blocking": ["bgm_subordinate"], "calls": 141, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:recover_material": 1}, "error": "素材来源请求未完成；已保存的成功来源与素材会复用，重试仅继续未完成来源"}`

- R14监测 `2026-10-05T12:25:56.095820+00:00 {"status": "retrying", "blocking": ["bgm_subordinate"], "calls": 141, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:recover_material": 2}, "error": "素材来源请求未完成；已保存的成功来源与素材会复用，重试仅继续未完成来源"}`

- R14监测 `2026-10-05T12:26:01.108191+00:00 {"status": "recovering_material", "blocking": ["bgm_subordinate"], "calls": 142, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:recover_material": 2}, "error": "素材来源请求未完成；已保存的成功来源与素材会复用，重试仅继续未完成来源"}`

- R14监测 `2026-10-05T12:26:06.125262+00:00 {"status": "failed", "blocking": ["bgm_subordinate"], "calls": 142, "live": [], "failures": {"fa_22f91d9f97ab6e7c355d46ba87bb478b:recover_material": 3}, "error": "素材来源请求未完成；已保存的成功来源与素材会复用，重试仅继续未完成来源"}`


R14约58.5秒，F经一次合法JSON修复后普通准入通过，七项视觉和旁白合格，**8/9**；唯一缺口bgm_subordinate。Material136→142：视觉报告2、来源搜索4；无新生成/ASR/TTS。短query `piano instrumental`真实返回20候选，Top3获取均失败；原Owner达到3次供应失败上限停止。不能把20候选等同20条不可用，也不能认领MATERIAL_READY。

隔离诊断计入原Material第143次，耗时5.353016秒；只取原Openverse同query前三候选临时获取，结果全为Wikimedia CDN HTTP403，临时媒体未登记，报告保存在 `materials/recoveries/audio-intake-diagnostic-r14.json`。公网DNS回退校验通过，先前仅凭系统假IP怀疑DNS不足以归因。正式记录只保留AcquisitionError类名，是诊断可观测性缺口。下载器未发送User-Agent；官方 [Wikimedia请求标识规范](https://foundation.wikimedia.org/wiki/Policy:User-Agent_policy) 明确无描述性客户端身份可被阻断，规范请求使用真实Easel身份取得200，但尚不能据此证明媒体403已解决。

Astra只读复核要求MODIFY：BGM短查询耗尽可能提前阻断仍可执行的视觉第二轮。修正为局部音频耗尽，优先继续剩余视觉恢复，并从新视觉wave排除已耗尽BGM；扩展既有混合恢复回归。下载每跳补真实Easel/1.3及项目地址，不伪装浏览器、不带Cookie、不换出口、不扩大主机/Top3；HTTP403仍拒绝。失败摘要只保留严格匹配的三位HTTP状态，其他异常保持类型，避免签名URL/本地路径泄漏。只有验证并对账后沿同Attempt继续R15；失败/调用/占额不清零，Rights/Match/Readiness不放宽。


## R15 真实客户端标识与音频接续恢复（PARTIAL / 8 of 9）

- 2026-10-05T12:43:23.023506+00:00 全量696 passed、5 skipped（44.52秒），compileall/115合同/diff check通过；18冻结输入、全部终态释放、网关active0queued0及Owner锁空闲对账通过后，仅Web加载，正式retry原Attempt。起点143/1840、8/9、占额0.1798；源码SHA f750c57d03e50f3b99ee7cba9942b4b8c421d593aa628320f442fd1f956d96c9，网关/Hypit未重启，终点仅MATERIAL_READY。

- R15监测 `2026-10-05T12:43:35.001250+00:00 {"status": "recovering_material", "blocking": ["bgm_subordinate"], "calls": 144, "live": [], "failures": {}, "error": null}`

- R15监测 `2026-10-05T12:45:20.148887+00:00 {"status": "recovering_material", "blocking": ["bgm_subordinate"], "calls": 144, "live": [], "failures": {}, "error": null}`

- R15监测 `2026-10-05T12:46:29.769125+00:00 {"status": "recovering_material", "blocking": ["bgm_subordinate"], "calls": 144, "live": [], "failures": {}, "error": null}`

- R15监测 `2026-10-05T12:46:39.796009+00:00 {"status": "material_supply_exhausted", "blocking": ["bgm_subordinate"], "calls": 144, "live": [], "failures": {}, "error": null}`


R15约3分17秒，Material143→144，仅来源请求1，无新视觉/生成/ASR/TTS。Openverse同短query20候选/Top3中正式取得1音频，另2其他获取失败；补UA已验证取得部分真实供料，不能声称全部403唯一由UA导致。新asset `asset-ec9765907bcd4f14aec09b0177b3ade6` / Openverse item `7b77669a-afee-440c-b5d3-dd3dc71bb4cc`，技术PASSED、253.75秒，但Rights缺证据/署名，普通Gate仍8/9、有界供应耗尽。

原账本另计2项只读权利核验（Material144→146）：官方Openverse单曲API给出实际plain署名、Mcwpiano、CC BY4.0及foreign_landing_url curid196809597；同站无query `Special:Redirect/page/196809597`访问200。不保存带凭证/签名query。根因Acquirer只为KNOWN保留许可证据，漏传ATTRIBUTION_REQUIRED/PUBLIC_DOMAIN及现存Provider署名；全query脱敏又抹去Commons单曲身份。Rights拒绝正确，不当音频不适合或无素材，不绕过。

后续最小修复只传真实单曲事实：Adapter只规范准确Commons查看URL的唯一File标题或纯数字curid；CC BY4.0/CC0版本及许可URL必须一致，缺失/冲突保持阻断，署名沿实际发布文本并附真实来源。新获取与旧字节刷新共用中立Rights构造函数；旧素材刷新匹配Provider item、原媒体路径、Plan/Bundle和实际SHA，仅一次有界元数据GET，无重搜/重下载，不写人工reviewed_at。原Owner再走普通音乐观察/Match/Gate；事实登记不是音乐通过。五项集中风险回归通过，完整验证/复核后继续R16，终点仍MATERIAL_READY。


## R16 Provider权利事实恢复与普通音乐准入（PARTIAL / 8 of 9）

- 2026-10-05T13:00:50.134171+00:00 全量701 passed、5 skipped（最终耗时见本次验证），compileall/115合同/diff check通过；18冻结输入、全部终态释放、网关active0queued0及Owner锁空闲对账通过后，仅Web加载，沿原Owner自动接续原Attempt，不清失败/控制位。起点146/1840、8/9、占额0.1798；源码SHA d32e5710d38c087570cb3cd7ed7db23aaae1fc6a6a4684ccbca1703f9909ea91，网关/Hypit未重启，终点仅MATERIAL_READY。

- R16监测 `2026-10-05T13:00:59.199128+00:00 {"status": "observing_material", "blocking": ["bgm_subordinate"], "calls": 148, "live": [], "failures": {}, "error": null}`

- R16监测 `2026-10-05T13:01:19.246482+00:00 {"status": "material_supply_exhausted", "blocking": ["bgm_subordinate"], "calls": 148, "live": [], "failures": {}, "error": null}`


R16正式Owner观察动作耗时 **24.773932秒**，新增Material146→148：单曲元数据刷新1、本地音乐观察1；无重搜/重下载、云端视觉/生成/ASR/TTS均0。权利事实成功保留CC BY4.0的导出署名条件，原音频asset ID/SHA及技术结果不变，reviewed_at仍空；观察PENDING持久接续完成。全量701 passed、5 skipped（47.75秒），compileall/115合同/diff check、Astra CONTINUE后执行。

真实音乐报告50个重叠窗口、完整253.75秒。最大人声分数0.001171，音乐最低0.526289、均值0.75490602，34/50窗低于当前0.8门槛；规则要求每窗Music≥0.8且所有人声≤0.01，故普通推断 **unknown/PARTIAL**，不能以标题“instrumental”或低人声直接放行。报告 `materials/observations/music-76b34c34c830ac39eb13fe2a5cadfb72115af746eecc18cfac70233165ef3eb9.json`。这不是报告故障/权利缺失/没有候选，归类为**音频验证未确认**；当前Owner状态material_supply_exhausted是无剩余已获批供料策略，不能替代具体失败原因。没有将unknown作为硬不适合去无变化重搜或新生成。

最终仍 **8/9 / MATERIAL_NOT_READY / AUTONOMOUS=NO**，尚未证明独立素材自主完成或提速成功，未执行Authoring prepare/Build/成片审阅，outputs空。Prepare7/24、Material148/1840、五项已完成生成及占额0.1798/10保留；剩余额度足够不是继续无变化重试的理由，实际总账单unknown。18冻结Planning输入全部保持，请求终态释放、Owner锁空闲，网关active0/queued0。下一真实缺口是现模型对该BGM音乐性的确认；须校准验证证据或采用能正式合格的候选，不能仅为达到9/9降低门槛。此前“声音有限放宽”只落实旁白规则，不转授BGM任意放行。
