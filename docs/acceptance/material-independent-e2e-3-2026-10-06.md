# 第三次独立 Material E2E（2026-10-06）

状态：**FAIL / Planning Truth Gate 自动停止 / 未进入 Material Supply**。新作品《给一天留一点空白》`cr_7e2e84a687d9493095ff371425d7e930`，Attempt `fa_f0ff6daa752e339819a677b2d893a6fc`。全程没有工程救场；未进入 Authoring、Hypit Build、Video Quality、Selected Output 或发布。前两次独立验收 FAIL 均保留，不恢复、不复用、不倒算。

## 固定版本与预检

- 分支 `easel-studio`；commit `36ead76beaeed02ce53d1580dc4f0fb56ddcd88e`；production source SHA `5f6e21a2fb301358c906291bbf4a811fa44ac986ace214a1c7ef687c10b0aede`。与前次正式加载记录的全部 Git 跟踪 easel/web/scripts 文件逐项摘要相同；已有无关文档整理保留，未修改生产源码。
- Web PID45709、Gateway PID45701，均为北京时间21:04:30加载的进程；本轮不重启。Web端口7860且网关就绪；Gateway runtimeVersion=2026.9.4。预检683任务均终态，active/queued=0，taskAudit warnings/errors=0。
- 全部15个旧Creation均无pending/submitting或pending runtime release，无活动operation。前两轮FAIL的各自`attempt:prepare`失败计数3与exhausted_operation均保留。终态再次对账15份旧JSON SHA全部不变。
- AGENTS.md要求的Astra正式E2E前只读复核CONTINUE：须确认前正式绑定素材终点，Owner到Gate后停止；新预算独立，视频生成/BGM生成不在本轮范围。此意见不证明E2E通过。

## 正常入口与授权

- 北京时间21:08:35从正常Easel新对话新建作品，沿用当前画像“个人经营实践”和clear_memo_video v1.3；主题为普通生活建议，36秒、9:16 1080×1920、简体中文字幕、普通话男声与轻柔无歌词BGM。
- 正常方案Agent两次：初始完整方案与确认前修订。修订消除第一人称真实经历和“再也不回”表述，要求旁白完整；保留画面、旁白/BGM、规格，不指定Provider、素材数量或删减Planning Need。初始和修订原文均留存。
- 用户在本线程独立授权¥10，仅MiniMax图片和现有预置旁白；不转授前两轮额度，不授权AI视频、AI音乐及Build。
- 21:09:08经正式同源本机Operator Session及`/delivery/material-endpoint`绑定MATERIAL_READY；回读未确认、无Attempt。21:14:49在正式画布填写10元并点击“按这个方案制作”。没有改数据库、冻结输入或正式证据。
- 视频方案SHA `f45449b52416cce36274c5bf862507d1922aac2d34bb4370d5d758d3b38c0037`；整体确认SHA `dd0ea663cd07ee47e8a8dbf62375c824974cfb94572e3237fd76a8e6beed2585`。确认原子绑定预算、输入使用声明与终点。scope含通用video_model字段，但确认方案排除AI视频，素材终点自动选择也跳过视频；未调用手动生成入口。

## 真实执行与失败现场

- Preparation一次真实派发，21:16:40冻结Content Core/Truth Packet/Creator Context并建立新Handoff/Attempt。Planning从21:16:40开始，一次初始派发；21:19:06进入一次系统Truth审阅。
- 本次Planning真实产出MaterialPlan和MATERIAL_REQUIREMENTS，全部9个Need均required：6 image、1 Voice、1 BGM、1 SFX。Domain、模态约束、NeedCompiler及全部6视觉要求合同由正常系统校验通过，落盘6份requirements缓存。没有Planning结构修复派发；此前修复的声音跨模态错误未出现。
- **未建立正式PLANNING_READY。** Truth审阅前的结构校验通过不等于正式Planning完成，更不等于进入素材供应。materials中supply-runs/generation-runs/assets均空；只有合同缓存，无供应、资产、Match、Rights、Bundle或Readiness。
- `planning/SCRIPT.md`保存了确认方案“文案”段全文：6句旁白之外，还包含字数/人称说明、TTS预计30–34秒和旁白完整性/留白指令。系统审阅将claim-0001～0006判creative_expression；claim-0007和0009判rewrite_required；claim-0008（未来TTS时长预测）判unresolved。报告原文、SHA及输入均保留，没有人工改判。
- 确认稿保护分支拒绝系统改写，实际触发异常为发现rewrite_required后在`web/app.py:3445`抛出“已确认文案存在待核实事实，请回到方案讨论处理；系统不会擅自改写”。不能把此泛化错误等同六句旁白事实均有问题，也不能只把unresolved看作唯一触发项。
- 21:20:28第一次失败，随后后台复用同一有效审阅产物，于21:20:29、21:20:32累计相同prepare错误3次；21:20:35最后runtime释放/持久更新，Delivery failed、operation=null、exhausted_operation具名保存。三次失败未增加Agent派发；无人工Retry、修改方案或审核放行。
- 当前只读诊断表明：正常确认稿“文案”段混入元说明，整段恢复至SCRIPT，再由Truth按全部文本分类，导致冻结稿与需重写意见冲突。代码证据为`web/app.py:3097`、`3270`、`2643`、`3445`；本轮只记录，不修复或恢复。

## 耗时、调用与费用

- 正常入口新建21:08:35→终态21:20:35：12分00秒；正式确认21:14:49→终态：5分46秒。Planning21:16:40→Truth检查及失败停止：3分55秒；其中初始Planning至Truth开始2分26秒。系统phase_timings中约1秒值是异步派发耗时，不冒充整个Planning墙钟。
- Material Supply→MATERIAL_READY耗时：N/A，未进入供应。
- Agent派发5：方案2、Preparation1、Planning1、Truth1；Delivery prepare预算计量3/24。Gateway/tool内部HTTP、模型续段计数UNKNOWN；工具调用不是额外Agent派发。
- Provider/query/candidate=0/0/0；素材observation/report repair/supplementation=0/0/0；AI图片/TTS/视频生成=0/0/0；Narration/BGM验证=0/0。
- 系统observe_agent计110（Preparation35、Attempt75），属于对账轮询；Truth phase进入4次（首次派发加3次终态消费），复用同一报告。相同错误失败3次，没有无变化模型重派或重复采购。
- 本轮素材授权¥10，占额¥0、实际素材生成采购¥0。模型真实账单与总实际费用UNKNOWN；Gateway transcript usage/cost零值为占位，不能当免费证明。旧费用和预算不清零、不转授。

## 未覆盖 required Need

全部9项未供给：

| Need | 类型 |
|---|---|
| img_beat1_phone_screen_down | image |
| img_beat2_stand_up_leave | image |
| img_beat3_pick_up_empty_cup | image |
| img_beat4_pour_water_walk_to_window | image |
| img_beat5_water_ripple_light | image |
| img_beat6_back_to_window | image |
| voice_narration_full | Voice |
| bgm_instrumental_bed | BGM |
| sfx_cup_water_ripple | SFX |

供给覆盖0/9仅表示无资产供给，不冒充已运行的正式Readiness结果。视觉、旁白、BGM均未正式准入，Rights/Match/Readiness均未执行。

## 最终结果

```text
MATERIAL_E2E = FAIL
AUTONOMOUS_EXECUTION = YES
AUTONOMOUS_DELIVERY = NO
REQUIRED_COVERAGE = 0/9 (0%; 无正式Readiness Gate)
PLANNING_RESULT = 结构/视觉合同通过；Truth失败；PLANNING_READY未建立
MATERIAL_SUPPLY_ENTERED = NO
MATERIAL_READY = NO
ELAPSED_TIME = 确认至终态5分46秒；Planning至终态3分55秒；Supply→Ready N/A
CALLS = Agent5；Provider/query/candidate/observation/repair/supplementation/声音验证均0；系统观察110
GENERATION = 图片0 / TTS0 / 视频0
COST = 授权¥10；占额¥0；素材采购¥0；模型及总实际费用UNKNOWN
ENGINEERING_INTERVENTION = 0
BLOCKERS = 已确认SCRIPT含方案元说明；Truth需重写但冻结稿不得自动改写
```

AUTONOMOUS_EXECUTION=YES仅表示确认后由系统执行至失败，无工程救场，不证明自主交付成功。

## 脱敏记录与停点

本机归档：`/Users/xgx/Library/Application Support/Easel/acceptance/material-independent-3-2026-10-06`。保留固定/加载预检、Astra条件、终点设置、授权/确认、新作品连续快照、Preparation draft/snapshot/Handoff、全部终态工作区文本/JSON及原字节SHA、4个Gateway session脱敏完整transcript（hasMore=false）、5个具名任务、正常对话执行日志、本轮失败截图、机器结果和最终对账。文件600、目录700，不包含凭证/认证配置/未脱敏服务日志。

终态Gateway active/queued=0、taskAudit warnings/errors=0；本轮3个Delivery Agent均ok且runtime released，无pending/submitting。生产文件SHA不变，15个旧Creation SHA不变。未修改代码、正式素材/报告/审核/Rights或冻结输入；本验收记录与Current State更新仅为验收记账，不作为系统正式证据。未执行后续视频阶段；失败现场保留，不开启下一轮优化或工程恢复。
