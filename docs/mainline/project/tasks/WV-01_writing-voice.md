# WV-01 · V2.1 写稿与声音表达专项

- **目标**：真实输入、六维画像及已确认导演形成忠实可说的稿件；固定声音身份，支持有语义的表达与局部修订。
- **阶段**：已统一合并、推送并部署V2；软件收口完成，完整作品验证与Creator接受仍PARTIAL。
- **授权**：2026-10-27 用户明确授权调查、设计、实现、离线验证、独立分支提交推送及 Draft PR；允许并行独立审计。开工时未授权新增付费调用，后续已明确批准本轮5次同声线配音实验（见授权更新）；生产部署/合并、模型权重下载、个人录音外传仍不在范围。
- **基线**：`5809a94ca687540c5178b6ee1c72d85d406bb259`，本地 V2 比 origin/V2 的 `2bde5351` 领先一提交，无分叉。独立 worktree，分支 `codex/v2.1-writing-voice`。主工作区五个既有 Dirty 文件及个人素材未复制、未改动；V3 不动。
- **官方检查**：fetch upstream 后 HEAD `5a597e5f`；新增媒体/harness/chat 生命周期、上下文诊断与记录卡片改动，仅调查，不合入。
- **现有生产断点**：沿 CRE-01 保存，不恢复、接受或发布现有作品。

## 调查证据与归因

最近真实作品已只读核验：两版方案、三条写稿 MODEL 请求及已完成试听记录。私有正文、标识和媒体不纳入 Git。

1. 三条写稿请求分别约13,595、22,173、31,217字符；六维画像、导演和本期输入实际存在，重规划含完整旧方案，未发现该样本写稿输入截断。修订要求已进入但抽象重复仍存在，当前证据指向生成取舍不足，不以堆规则补救。
2. 当前真实方案使用 continuous/voice_driven，六场停顿均为空；visual 中的聊天语气、理解空间、兴奋意图没有独立声学表达通路。现有适配器只消费正文、停顿与固定声音参数。
3. 连续旁白通常聚合为一个资产，局部改稿会改变整块内容身份；不能承诺块内满意声音不变。分组/表达参数需要明确设计及独立保护验证，不默认逐句合成。
4. 代码已保护完整原音，固定片长超时阻断；未发现本链路全局 atempo。不能据播报感认定加速或裁切。
5. 已复现停顿0.123被编译为供应商标签，但官方要求最多两位小数；这是确定协议缺口，拒绝非法新值，不偷偷四舍五入旧稿。
6. 已有六次 MiniMax 实验授权已消耗，五份音频可复用，一份供应商成功但本地音频丢失且未重发。不能作为新调用授权。

## 实施与验证顺序

| 包 | 范围 | 验证 |
|---|---|---|
| W0 | 基线与真实链路取证、同内容比较样本、能力/许可核验 | 原始请求与当前代码交叉验证；原媒体只读 |
| W1 | 停顿精度新稿准入及发送前保护 | 合法字节稳定、非法拒绝、旧冻结值可读、无重发 |
| W2 | 根据已证缺口设计表达及可复用段落 | 固定声音、实际消费、局部复用、字幕/时间线与恢复身份；不搭空接口 |
| W3 | 同内容 A/B/C 短样本及完整作品 | 新服务调用须单独授权；先稿件后表达，一次只改变一个因素 |

不迁入新Provider或短剧平台，不默认改变音高/速度/情绪，不引入多Agent创作审核链。导演配置及生产服务保持原样。

## 验收与限制

- SOFTWARE_PASS：全仓2692通过/11跳过，原生42通过/14跳过。
- REAL_AUDIO_VALIDATED：PARTIAL。5次真实生成及局部复用通过；当前工具没有真实听音能力，自然度NOT_TESTED。
- FULL_VIDEO_VALIDATED：NOT_TESTED。
- CREATOR_ACCEPTED：NOT_TESTED，必须由用户试听确认。

## 下一动作

已完成W1/W2离线回归及真实短配音，下一步由Creator盲听编号样本并指出具体句子/接缝；据此决定表达方案与后续完整作品验证。保持Draft PR，不合并、不部署。

## W2 设计决定（2026-10-27）

在既有 NarrationPolicy 增加可选语义段 groups，每段稳定 id、连续场景引用和可选 emotion。导演选择语义段，经本版 Plan 确认，不要求用户逐句配置。没有 groups 的旧方案保持原分段及序列化身份。段内连续合成，改一段只使该段声学缓存失效；这不提供已有整条录音内部的无损任意字级编辑，也不能保证新段接缝自然。

固定 settings.voice 不变；只有已支持的段落 emotion 可进入有效请求。用户明确固定全局 emotion 时冲突必须显式解决；不覆盖声音身份、speed、模型或服务。声音资产保存真实有效参数，缓存含实际声学请求。成片后 narration 修订允许修改既有段表达而不偷偷重分组；重分组走重新规划。字幕及后续时间线按新实测重新定位，满意部分的音频字节可复用，绝对时间不承诺不动。固定片长、原声、BGM/SFX及UNKNOWN保护保持。

新能力按真实最终分段验证，不按单场假定：已发现每场4个合法停顿合为36个时，原逐场检查通过但发送上限32失败。将规划检查与生产分段粒度统一，不增加新的审美Gate。

## 官方研究与取舍

核验于2026-10-27；以下均非本机听感或性能证明。

| 候选 | 已核验机制/限制 | 本期取舍 |
|---|---|---|
| MiniMax 2.8 | [同步接口](https://platform.minimax.io/docs/api-reference/speech-t2a-http)支持停顿、情绪、字幕；停顿最多两位小数。当前代码已支持有限情绪但未区分段落表达；词级字幕尚未贯通消费者 | 接通既有段落表达与复用，不默认calm/降速；词级对齐待具体需求，不仅加开关 |
| IndexTTS 2.5 | [推理代码](https://github.com/index-tts/index-tts/blob/d9e41aac89fd00b3d71497fddb287b7f24613712/indextts/infer_v2_5.py)独立spk/emo参考、向量及文本；[代码许可](https://github.com/index-tts/index-tts/blob/d9e41aac89fd00b3d71497fddb287b7f24613712/LICENSE)与[权重许可](https://huggingface.co/IndexTeam/IndexTTS-2.5/blob/main/LICENSE)为bilibili Model Use License，有适用条件 | 借鉴职责分离，不下载/部署；本Mac资源/延迟未测 |
| Fish Speech | [请求结构](https://github.com/fishaudio/fish-speech/blob/541566932abbaebcb0a40e562a1f846738383f38/fish_speech/utils/schema.py)的普通TTS没有保留指定旧音频区间的接口；[安装](https://speech.fish.audio/install/)对GPU有要求，Drama3需48GB FP8/NVIDIA，非Apple MPS；[代码许可](https://github.com/fishaudio/fish-speech/blob/541566932abbaebcb0a40e562a1f846738383f38/LICENSE)与[S2权重许可](https://huggingface.co/fishaudio/s2-pro)不能混同 | 仅候选对照，模型宣传局部编辑不等于现有HTTP支持不可变资产复用 |
| SonicVale | [台词服务](https://github.com/xcLee001/SonicVale/blob/cee15e67cc68a925995c3146557b281e0248dc9c/SonicVale/app/services/line_service.py)绑定角色、情绪和单段音频；[许可声明](https://github.com/xcLee001/SonicVale/blob/cee15e67cc68a925995c3146557b281e0248dc9c/README.md)AGPL与额外商业限制需澄清 | 仅借鉴段落绑定和试听机制，不复制其删除旧音频的实现，不迁入平台 |

中国MiniMax [刊例](https://platform.minimax.cn/docs/pricing/overview)：2.8-turbo每万计费字符¥2，汉字按2，其他字符按1；1000正文字符上限的小实验约¥0.4并须计入标签。模型回执usage与账单保留，套餐不等同免费。精确MiniMax-M3.1-Flash-Preview价格未核清，不拿无Preview型号价格代替。

已向用户集中提出最多5次同声线短配音授权，未收到回复前不发送。A复用已有音频，B写稿与C表达依次比较，最后一次验证局部修订；本轮不含新增规划模型调用。短样本不能证明整片稳定，后续完整作品调用须另核授权。

## 本轮原片技术复核

原片85.033333秒、H.264/AAC、48kHz双声道，FFmpeg全片解码无错误；原始旁白84.024秒，时间线0.2秒起，gain=1，fade_in=0.15、fade_out=0.25，整条源音频完整使用。BGM及两条SFX存在。未真实听音，不能从这些数值判定播报感、尾字可听或混音自然。

同义重复的定位来自既有字幕时间线：37.8–40.7、76.1–79.5、82.3–84.22秒；它们是待试听定位参考，不是听审或词级声学对齐。私有证据保存在隔离工作树 outputs 下的专项目录，包括请求摘要、原稿/候选改稿、事实对照、原片/音频摘要；不入Git。

写稿传递回归2项已通过：真实WorkService→Worker→RecordedModelTransport链路逐值验证六维/频道/导演/原话/最新反馈，且排队后的画像变化不污染快照。原模型输入并未丢失，因此暂不因缺乏听评而重写整套自然表达Prompt。已有候选改稿可审阅，但这不是稳定生成质量的证明。

文档检查首次出现4项基线问题：CRE-01引用的本机临时scratch目录未跟踪、隔离工作树不存在；不复制个人脚本来凑通过，后续以本轮文档独立检查和基线对照记录。

## 隔离环境与使用方法

本分支的Web端口7862、预留Gateway18792；配置为本工作树.env，数据库为本工作树outputs的_production子目录，Profile与输出同样位于本工作树。初始不复制生产配置/凭证/画像，API底座无Key时不调用服务。只读启动检查已完成：capabilities可读、模型未配置、works/operations均为0，正式7860/18789原进程不变。

从独立工作树根启动（解释器替换为有仓库依赖的Python，不能在主工作区执行）：

```sh
env -i PATH="$PATH" LANG=en_US.UTF-8 \
  EASEL_PRODUCTION_ENABLED=1 EASEL_AGENT_RUNTIME=api \
  EASEL_PORT=7862 EASEL_GATEWAY_PORT=18792 OPENCLAW_GATEWAY_PORT=18792 \
  EASEL_OPENCLAW_STATE_DIR="$PWD/outputs/_writing_voice/openclaw" \
  EASEL_OPENCLAW_WORKSPACE="$PWD/outputs/_writing_voice/workspace" \
  /path/to/venv/bin/python -m uvicorn web.app:app --host 127.0.0.1 --port 7862
```

这只启动隔离后端；真实聊天需独立且已获授权的配置，不能拿无模型状态当完整体验通过。测试中只读复用已安装解释器，不更改主环境依赖。只停止自己启动的进程即可回退；不迁移或覆盖原生产库，旧版产物无需回退。

对话方式仍为原流程：提出本期内容→审阅方案→确认制作；需要局部保留时，在方案中由导演提出语义组，不要求逐句配置。成片后可以说“只改第二段这句话，其他段落声音保留”，走既有narration修订范围和新稿确认。分组前的整条旧音频不能无损自动分成可编辑组；首次重分组要明确重新规划，新版试听满意后再确认。满意程度是Creator判断，不自动更新长期画像/导演。

## 真实调用授权更新

2026-10-27 用户回复“可以进行使用，不论金额，主要是调试好，效果能让我满意”。本轮先执行已解释的同声线最多5次短配音，实际范围固定在私有实验清单，金额放开不等于无目的重试。无新增规划模型调用、无正式作品修改、无图片/视频生成或发布。

为分离变量，顺序为A复用原稿音频、B整段候选、C0同稿中性分组、C1仅末组happy、R仅末组改稿；B1次+C0两次+C1新增1次+R新增1次，总计最多5次。C0/C1/R复用未改首组，合成后以相同0.25秒段间间隔比较；不将分组变化和情绪变化同时混为一个因素。每条件单样本，不能据此认定稳定提升。

## 软件检查点

2026-10-27：全仓Python 2692 passed / 11 skipped / 14 warnings（187.90秒）；原生插件42 passed / 14环境跳过。独立审查及18项专项复跑通过。变更文档路径检查0新增错误，全库保留4项隔离工作树缺失本机scratch目录的基线问题。diff检查通过。

SOFTWARE_PASS（本轮实现与离线覆盖）；REAL_AUDIO_VALIDATED / FULL_VIDEO_VALIDATED / CREATOR_ACCEPTED仍NOT_TESTED。隔离后端启动及空库readiness检查完成后已停止自己的验证进程，正式服务未停启。真实配音实验准备中，完成后追加实际结果，不将本检查点标为最终自然度交付。

## 真实声音接口分阶段验证（2026-10-27）

受测源码提交 `9b0bb9772b56d3e12732a225850f448fda570f0b`；隔离DIAGNOSTIC_API，使用原MiniMax 2.8-turbo及原声线/速度。人工候选稿经既有WorkService保存及确认，Worker仅执行VoiceTasks；不是自动写稿模型或完整视频E2E，未伪造成片、语义审阅或接受。

| 阶段 | 唯一变化 | 新TTS请求 | 结果 |
|---|---|---|---|
| A | 原稿原声 | 0，复用已有31.392秒音频 | 原基准保留 |
| B | 同事实候选稿，原整段方式 | 1 | 26.640秒音频，Operation succeeded，摘要校验通过 |
| C0 | 同B稿，拆为两语义组，无情绪覆盖 | 2 | 两段13.049625/13.351500秒 |
| C1 | 仅末组happy，其余保持 | 1 | 首组原operation及SHA复用，末组13.130906秒 |
| R | 仅修改末组最后一句，保持C1表达 | 1 | 首组原operation及SHA再次复用，末组12.109219秒 |

共5次POST、实际wire正文412字符、所有配音Operation成功；未重发。4条用量回执共471计费字符；首条HTTP200且音频成功，但独立遥测未解析用量，保留原失败标记，通过成功持久回执及文件SHA只读核实，不用重付费补齐统计。后续显式identity传输编码后遥测正常；未修改产品适配器。费用不能用471作为全部实际账单，按刊例仅已记录部分约¥0.0942，首条未知；总金额应以服务商账户为准。

原音保留，生成5条随机编号试听副本，只有固定增益响度匹配，无变速、裁字或动态压缩；分组样本采用原调度0.25秒间隔。副本约25.4～31.4秒，全片解码通过。此样本比预期30～60秒稍短，未为凑长度添加口播；不以短片段证明完整作品稳定。私有音频、映射、正文/事实对照、Operation/请求及回执留在本工作树outputs专项目录。

本轮补充状态：SOFTWARE_PASS；REAL_AUDIO_VALIDATED=PARTIAL（真实服务、固定身份、局部复用、解码通过，实际听感NOT_TESTED）；FULL_VIDEO_VALIDATED=NOT_TESTED；CREATOR_ACCEPTED=NOT_TESTED。工具无真实听音能力，没有将音量测量或HTTP成功当作自然度。

## 提交与下一步

已推送专用分支，维护[Draft PR #14](https://github.com/webxia/Easel/pull/14)，不合并/不部署。远端V2仍落后基线一提交，因此PR包含继承的5809a94c；本专项源码从9b0bb977开始，不能把该继承差异视为本轮新增功能。PR未报告远端CI检查，不能写CI PASS。

主工作区HEAD及开工记录的五个Dirty文件摘要复核未变；正式服务进程保持。个人素材、生产记录、凭证、实验脚本及音频未提交。父任务PARTIAL：等待Creator盲听反馈，以具体句子/接缝决定是否保留分组/表达方案；尚未完成真实规划模型的同内容A/B、真实对话改稿以及完整作品视听验证，不能作为最终稳定版交付或声称播报腔已解决。完整验证不应在短样本尚未听评时盲目扩大。


## Creator短样本听评更新（2026-10-27）

用户表示些许改善，并对原稿基准与改稿/分组/末段情绪样本均给出正向听评，未在两者间排序。盲听映射已核实，原话及编号映射保留在私有实验目录。不能由此判定新稿优于原稿、分组必然更自然或happy应成为默认情绪；两个样本同时改变多个因素，且只有单次生成。现有声线无需因此替换，保留原稿基准及可选段落表达，尚不推广固定表达模板。

REAL_AUDIO_VALIDATED仍PARTIAL，但不再是完全没有用户听评；完整作品与CREATOR_ACCEPTED仍NOT_TESTED。下一步先保留两条获正向反馈的参考，后续验证真实写稿及完整作品中的表达稳定性，避免重复微调短样本或把临时样本偏好保存为长期画像规则。本次仅记录听评，未新增调用、合并或部署。

## 完整链路授权与实施（2026-10-27）

用户明确继续补齐写稿与声音代码，并在隔离分支完成真实多轮改稿和完整出片；沿用现有模型与声线、BGM及音效，不合并或部署生产。此最新授权覆盖本专项真实规划、对话及制作验证，不新增AI图片/视频或发布。短样本1的情绪表达获得更明确正向反馈，仍不推定所有段落应使用相同情绪。

当前实施：已有CreativePlan字段调整生成顺序，让事实、观点与约束先于稿件；修正对话层整条配音必重做的陈旧说明，语气/停顿修改进入既有narration修订，按实际分组及缓存决定复用。等待真实生成、多轮修订与完整视频证明，不以字段顺序测试证明写稿质量。隔离Web7862/Gateway18792使用独立运行目录及凭证环境引用，生产服务保持。

## 正式工作区调试授权（2026-10-27）

用户最新明确“直接部署到正式工作区调试”，替代此前隔离部署边界；允许同步本专项代码并重载正式Web/Gateway，继续真实多轮与成片验证。不因此自动合并或提交V2、不发布视频。正式HEAD5809a94c，其余既有Dirty修复保留；专项13个非重叠文件同步，数据库一致备份及原Dirty摘要保存于outputs/_debug/wv-deploy-20261027-083209。部署前619成功/7UNKNOWN Operation、无在途Run或活动对话，历史UNKNOWN保留。

隔离真实Web尝试未到G2：先误入普通对话，默认medium与模型不符；修正启动环境并切换视频入口后bootstrap会话身份校验失败，原turn保持unknown，未盲目重发。该轮无视频/配音，不宣称真实通过。按用户最新要求转正式既有配置继续，隔离证据留存。

正式部署结果：组合版本production测试1448通过/5跳过/13warnings；Web47678、Gateway47691重载完成，gateway=true、reload_required=false。原有Dirty代码摘要保持。部署证据result.json及tests.txt位于上述备份目录；未合并提交V2，业务验证仍需继续。

## 第三条真实经历作品验证（2026-10-27）

用户明确通过正式Web创作第三条视频并验证写稿与声音：本期独立Work，保持当前画像/频道及唯一已确认风格导演，先生成完整正式方案供本人确认，再生产。允许必要故障修复/测试/重载，不合并或发布，不修改长期设置。当前模型、固定声线和字幕已核实，后台无在途制作，7历史UNKNOWN不自动重发。私有源版本及配置证据：outputs/_debug/third-story-20261027/。

已从正式Web选择选定创作者画像、视频创作入口，提交本期事实与创作要求；未把研发清单送入创作。正在正式规划，尚未确认制作；G2～G6不得提前记PASS。

### 本期实证缺口：声音能力未进入首轮写稿（修复中）

真实方案曾选择固定speech-2.8-turbo不支持的fluent；NarrationGroup为多模型共用合同允许该值，但首轮author上下文没有voice_execution_contract，critic才收到，且合同未列出当前模型支持的emotion值。真实纠正只收到泛化“不支持此组表达”，因此先移除全部情绪，后续审阅又要求补表达，造成重复纠正。该问题不能用更多自然表达Prompt解决。

复用现有voice_execution_contract，在PlanningTasks.context按冻结creation_basis的声音设置生成并传给首轮author及后续任务；合同增加由现有适配器supported_emotions计算的合法值；错误标明分组、固定模型、不支持值及合法选择。不增加Provider/参数，不放宽校验，不修改已保存方案或历史回执。真实音频还未发送。离线真实Worker→MODEL边界按2.8与2.6对照验证合法值及固定wire身份，并验证不支持值仍拒绝、2.6的合法扩展仍允许。69项关联通过，正式组合回归进行中。

正式组合关联83通过/1跳过，diff检查通过；确认无在途生产Operation及活动Turn后，仅重载既有Web/Gateway，reload_required=false。未改历史方案/回执/私有数据。原Web已请求按真实能力恢复同Work重新规划，用户原稿件确认停止点保持，修订后的真实效果尚待回执。

### 本期实证缺口：审阅要求与实际分组合同冲突

声音能力修复后首轮author实际收到合法emotion，初稿四组选择calm/默认且结构通过。但后续critic持续要求group对象内新增语义依据/局限字段，与NarrationGroup额外字段禁止合同冲突；用户原要求只是每组说明，request整理将其扩大为强制字段，审阅上下文又没有该草稿字段合同。critic还反复自行计数字符/停顿，和草稿多处手写数字发生漂移，造成两轮返工后仍needs_decision。所有失败保留，不能为PASS删除审查。

必要修复：current_draft_context向critic及返修传递从真实NarrationGroup生成的JSON schema；修订既有字段合同说明，组解释可在purpose/visual，null代表默认，禁止以不存在字段作为必修缺陷。duration_execution_contract增加从实际script/scenes/pauses计算的字符数、停顿、场景总时长及逐场计数；缺少任一场景时长时总计为null，不伪装0，不推断实际声音时长。没有新增业务字段或修改已有方案。97项关联离线通过，主工作区同版本97项回归通过后授权重载。私有原审查回执包括“必须每个group对象内包含”要求，与schema正反例可独立对照。

本期当前检查点：第2版已合法保存，真实Web/G0～G2完成，6镜/4声音组（默认、calm、默认、calm），尚无TTS或成片。30次MODEL包含失败后合法重新规划及多轮校验/审阅，不宣称稳定一次通过或自然度已解决。等待Creator确认稿件与方向，后续制作与局部修订仍为父任务待办；运行记录见runs/2026-10-27-web-e2e-01.md。

### 本期实证缺口：同轮只读缓存与方案读取膨胀

第2版成功保存后，原生回复反复读到先前running/plan_revision=null并输出英文过程。PersistentWorkToolBridge.dispatch按tool+args缓存了全部结果，包含pending/context，只读再次调用仍返回同一旧快照；full详情又包含完整冻结依据及历史，截断前看不到当前正文。停止的是对话回复循环，原Work第2版与30次MODEL成功回执均保留，不重发规划。

必要修复：pending/preview/context/input-evidence只读调用重新观察当前持久状态；有副作用调用继续原fingerprint防重保护。现有pending增加detail=plan视图，仅返回当前方案及身份/工作状态，省略可由full审计读取的画像快照和冻结上下文；默认摘要的frozen_basis改为摘要hash/字段与原详情引用，不改原记录、服务权限、合同hash或授权身份。原6工具不增加，原full视图保持完整。226项关联通过；preview只读分类最终定向125通过；原生插件29通过。无在途调用后安全重载，正在原Web执行“只读第2版”验证，不规划/不配音/不下载/不渲染。

## 当前停止点：第2版可审阅，等待Creator

读取修复已真实验证：旧回复取消后旧Turn仍unknown，新消息按保护被拒绝，未清状态或伪造native结束。经内容库“继续创作”合法建立同一Work的续接对话，不新建作品；新回合pending detail=plan返回约8133字符，第2版正文与声音分组正常用中文展示，回合ended。未重跑规划，生产MODEL仍30、VOICE/IMAGE/VIDEO均0。旧UNKNOWN回合保留；对话取消后的原生未知结束恢复尚未完成，不宣称所有取消场景通过。页面将6个scene误写7镜并自行解释，真实记录按6场为准，未由此修改Plan。

当前G0～G2 PASS（经过故障修复及同Work续接，不是原对话一次自主通过）；G3待本人确认，G4～G6 NOT_TESTED。完整可读方案与截图在私有运行目录，已向用户提出稿件/视听确认；等待期间不自动配音/下载/渲染。不合并或推送主线，原Dirty和历史作品保留。

## 深入稳定性调试（2026-10-27，继续原目标）

用户要求调试完成后继续深入，目标稳定出片；本期稿件仍待确认，普通继续不代替稿件/制作确认。先完成不依赖批准的真实讨论边界与软件检查。

- 正式同Work续接对话测试“只讨论、不改稿”：回复后works、plan_revisions、work_briefs、runs、operations、conversation_proposals逐行相等，当前方案仍v2，生产MODEL仍30，无新增配音/素材/渲染。不是Creator反馈或接受。
- 加一项临时合成音集成回归：既有分组测量/字幕对齐→真实FFmpeg两次渲染；首组延长0.6秒后，解码频带验证后组新位置完整、旧位置不重复、无变速截断、BGM首尾及SFX新位置，画面像素验证字幕同移。1 passed。未经过CreationTasks模型或真实TTS，不能作为真人听感或完整业务E2E。
- 原中断回合的安全保护不放宽，reserve返回具体当前状态与合法继续路径，替代通用“工具校验失败”；unknown不释放、不重发，活动回合仍阻断。关联82 passed。
- 首次全仓默认pytest误收集私有before备份内同名测试，保留collection failure，改用规范tests目录，不删备份或配置跳过。首次正式全量2711 passed/1 failed/11 skipped，检出上一轮frozen_basis摘要化丢失原要求。保留既有失败断言，撤回该过度精简，保留冻结conversation_brief/channel等原语义，仅排除原有worker表达规则；独立plan读取视图与实时读取修复不变。删除本轮错误设计新增的“允许隐藏全部依据”的用例，既有语义保留断言完整通过。105项关联通过。

正在对最终组合源码重新执行完整tests回归；不会用第一次部分PASS冒充最终通过。旧失败和各版源码/日志保存在私有运行目录。禁止把本轮软件音频测试称REAL_AUDIO_VALIDATED或FULL_VIDEO_VALIDATED。

### 最终组合回归与部署复核

最终规范入口pytest tests：2713 passed / 11 skipped / 14 warnings（201.07秒）；原生插件42 passed / 14环境跳过。独立实际FFmpeg分组渲染1 passed已纳入本次全量。git diff --check通过；仅测试文件末尾空行整理无行为变化，不重复全量。

确认无在途Operation/活动Turn后仅重载正式Web，Gateway未作无关重启。DIAGNOSTIC_API针对本片旧unknown回合的真实HTTP请求返回409 invocation_pending及具体合法继续提示，production operations数量相等、旧unknown状态未变；backend reload_required=false。此诊断不冒充原Web Creator验收。

SOFTWARE_PASS（本轮组合版本）；真实只讨论边界通过、完整读取/同Work续接已有证据；REAL_AUDIO_VALIDATED/FULL_VIDEO_VALIDATED/CREATOR_ACCEPTED均未因本轮软件测试提升。当前第2版稿件待本人确认，未新增生产调用/配音/下载/渲染，未提交或推送主线。保留取消后的native未知结束限制及原记录；下一步是本人确认本版或提出修改，随后原Work正式确认制作并继续BGM/SFX完整出片及成片后修订验收。

## 统一V2主线授权（2026-10-27）

用户明确要求全部有效代码合并到easel-v2-rebuild，提交、推送并部署，后续只维护V2；本轮仅软件收口/部署，不据此代替作品稿件或制作确认。保留旧工作树作恢复依据，不再作为活动开发线。整合现有V2 Dirty、V2.1已提交与后续未提交实现，排除个人素材、凭证、私有运行库及输出。源码与最终2713通过/11跳过、原生42通过/14环境跳过的受测摘要相等，不伪造新的E2E或听评。工程快照、合并、远端和部署证据保存在outputs/_debug/v2-unification-20261027/。

### V2统一收口完成

快照ed2cf36a纳入28个明确源码/测试/脱敏工程文档路径；正常合并V2.1的3个提交，5处冲突逐项核对后保留后续已验证实现、测试及最新记录，形成正式merge 68a66aac。合并树与收口快照逐字相等，原9b0bb977/854a5d95/352aeb6c均已成为V2祖先；没有用未审查的全局冲突策略。后续V2.1工作树不再作为活动开发线。

origin/easel-v2-rebuild已从2bde5351更新至合并提交，GitHub PR #14已标记MERGED。受管Web70757/Gateway70755启动于统一V2目录，gateway=true、reload_required=false、协议2/原6工具及权限保持。部署前一致备份后逐表对比，仅cleanup_jobs例行维护发生变化；外键检查为空，649成功Operation/7UNKNOWN、61份Plan和49个output记录保留，不生成新媒体。私有备份/冲突说明/推送和部署证据在outputs/_debug/v2-unification-20261027/，不提交。

已扫描暂存范围及配置凭证，排除所有个人未跟踪素材、二维码、skills/_scratch、outputs、Profile及数据库。工作树个人文件不删除；不自动发布或代签作品接受。完整作品E2E并未因此通过，原待确认稿及修订断点保持。

## 第三条作品开放创作委托续作（2026-10-27）

用户明确调整本片创作方式：导演自主承担主编/视听创作，Codex仅推进、处理真实故障与验证；已有本期结构、时长及逐段表达细化要求不再作硬约束，真实经历、当前配置、Rights/费用/生成额度及正式确认不放宽。继续原Work，当前Plan2未确认，仅有规划服务授权；不将这次一般委托代签未来Plan制作确认或成片接受。保留已有Dirty/旧作品/7UNKNOWN，正式Web/Gateway加载了前轮语言与Hook修复。

已通过正式内容库继续同一作品（未新建Work），将用户本次背景、问题及导演创作自由交给本期Planning；未外部代写口播，未送入Git/E2E工程清单。复用已有有效planning授权请求原作品重新规划，当前等待实际回执。原始依据/基线/实际请求与后续媒体只保留outputs/_debug/third-story-director-20261027/；运行断点沿2026-10-27-web-e2e-04维护。

续作结果：原Work第3版Planning完成，6场/84秒估计、4语义组（2默认/2calm），沿固定声线与字幕。6次MODEL成功，Easel自身修订事实边界与手填字符统计；Codex未代写或作审美返工。完整稿和正式服务/额度确认提案已在原Web展示，并将本版完整稿交本人确认。旧Plan与Operation回执、Work配置和0生成额度均保留；尚无新配音/下载/渲染，G3待本版真人答复，不重复未来方案代签。运行04为当前唯一制作断点。

### 第3版制作确认授权

用户在展示完整稿/导演方向/实际服务提案后明确“你全部代签”。据此代执行本版方案及列明制作服务的正式确认，不虚构Creator亲自审片结论、不自动发布，不扩展新服务/生成额度。已在原Web发送明确确认，要求answer原提案并继续同Work完整制作；不再等待重复方案确认。当前运行04继续记录实际生产和交付。

### 第3版生产首次失败与恢复修复

真实supply成功后已生成4组固定声线音频，edit首次报timed_audio_requires_fixed_duration。原MaterialIntent将门把/翻页/时间线/车门/合盖5处普通动作错误标为absolute，只有滴答为scene；原声/固定事件保护正确生效。修复在现有FrozenIntentCompiler增加前置时基检查，并沿原edit、原MODEL授权有界重审同一意图；只准改timing_basis，保留查询/用途/必需性/场景/时间估计，真实absolute继续阻断，受保护原声/历史Run/已有工程不可修改。成功模型纠错回执及事件持久化后，仅修正当前Run尚未出片的material_uses，原意图/回执/媒体/Plan保留；不清字段或改固定片长。

首次恢复完成分类纠错，却报narration_timing_missing：edit失败前已成功配音的引用未持久化，reuse_existing_media_only跳过配音准备后丢引用。补齐失败前保存asset_ids；恢复只在本Run完整语义组缺引用时走reuse_only缓存读取，缓存缺失/UNKNOWN不能submit/observe或重新合成，成功已有配音不reserve重写Operation。已完整资产的恢复以及静音/纯音乐恢复仍不调用VoiceTasks，原相关反例保持。

本轮首次175项定向通过，随后恢复引用88项通过；新增夹具最初遗漏schema_version被库约束检出，补正确夹具，未放宽数据库；第一次统一调用声音准备的实现触发两条原“禁止重配”回归，收窄为仅缺引用的有声恢复后通过。最终全量2727通过/12跳过，diff检查通过。两次均无在途时备份并仅重载正式Web，回同Work同edit通过正式resume继续；当前4条原VOICE回执不变，4个引用已保存，真实CreativeEdit发送中，实测自然长度90.433秒。仍未出片，不将软件或模型成功冒充完成。

### 独立叠加文字删除阻断与恢复

第2版原Web建立并确认两项edit/preserve_audio修订，模型选择已有合法情境镜头，但尝试用单空格覆盖上方文字；最终invalid_edit_project保护拒绝，原片与声音未改。根因是changes只能替换字幕，缺少删除独立overlay的表达，且修订工程漏存caption_roles。补显式remove_caption_ids，必须引用已登记overlay且不得与替换重复；旁白/未知角色默认保护。旧修订仅从对应已保存、文本/时间匹配的原提案读取角色，后续角色持久化，已存在旁白不得由模型改标overlay。局部校验只容许删除已知独立文字，不放开其他文案/时码/素材保护；空格替换在模型结果纠错中明确拒绝。

已知invalid_edit_project沿原resume恢复，从成功回执使用新纠错身份，不重新发送旧Operation、不复用被拒绝的编译结果。173项关联回归通过；真实原工程只读回放验证仅删独立文字后38条旁白、90.433秒及音轨相同，无生产写入。全量运行中修改源码导致旧进程freshness保护拒绝的尝试已保留并中止，不记PASS；随后全量2729通过/2组件失败，定位为无字幕/无review_id时不必要查询夹具reviews表，增加无来源时直接保护返回后，定向通过。最终冻结源码全量2731通过/12跳过/14警告（218.58秒），没有豁免失败断言。

无在途Operation/Turn时一致备份，仅安全重载正式Web。原Web读取新resume选项恢复同一个修订Task/Run，已成功生成第3版工程：38条旁白、独立overlay实际删除、指定代码镜头替换为原合法候选、audio_preserved=true；当前等待原render/QC及播放器。原VOICE回执不变、未新增配音/供料/AI画面或发布。私有证据仍在同一third-story-director目录，源码补丁与所有尝试日志保留，不提交个人数据。

## VIDEO_DELIVERED：第4版完整片交付

第3版两项明确缺陷已消除，随后现有有界自动修订处理原抽样复查新列的乒乓球拍歧义、重复键盘与视频流程表达；Codex未追加人工审美轮次或外部代写。第4版90.433秒1920×1080/30fps正式回传同一对话，Work为reviewable，accepted_output_id为空。4版原始成果及全部QC意见保留，最终技术PASS、sampled_visual_only.visual_status=pass且findings=[]；semantic行仍not_tested，audio_reviewed/full_av_reviewed=false，不写成完整视听通过。

独立证据：最新文件摘要吻合、全片解码PASS；确认Plan3/hash及全文不变，4组实际voice身份/文本/完整时长吻合；4条原成功VOICE行不变，第1/2/3/4版独立AudioClip对象及编码AAC摘要相同。最终38条底部旁白字幕，无额外overlay，BGM两段铺底/3处SFX真实使用，实际来源与使用位置在私有sources-and-credits.md。BGM为Wikimedia的No Cadillac（Loyalty Freak Music，CC0记录），SFX实际复用用户既已确认授权的Adobe Audition本地库存，并非虚报全部来自Wikimedia；视觉实际检索/库存记录保持。

从本轮起始快照计，生产账本新增23次成功MODEL与4次成功VOICE（不含产品内对话模型计费）；无新UNKNOWN，全局旧7条保留，当前无在途Operation。真实账单金额未取得，不估作已核实费用。最终组合软件2731通过/12跳过/14警告；SOFTWARE_PASS及本片技术生产/局部画面修订通过，REAL_AUDIO_VALIDATED、完整FULL_VIDEO_VALIDATED、CREATOR_ACCEPTED均未通过，PUBLISHED未执行。完整播放器从头到尾/刷新恢复另记下节；VIDEO_DELIVERED后等待用户实际审片反馈，不继续自动重做。

### 正式播放器与最终停点

通过原Web点击第4版播放，自0.253秒开始连续播放至90.433秒、ended=true、readyState=4、无媒体错误；不是跳到结尾。刷新后仍显示第4版卡片，仍加载同一artifact且readyState=4。截图、DOM播放结束与刷新证据仅私有保存。不能据此宣称实际听音或连续语义已观察。

VIDEO_DELIVERED达成；G5技术/抽样/正式播放器范围通过，G6 Creator实际审片和接受仍待反馈，PUBLISHED未执行。无进一步自动返工或调用，停在本人审片。修复源码保持主工作区HEAD 50454629加具名Dirty，正式Web已加载，未提交推送；保留其他Dirty、个人素材和旧UNKNOWN。详细原稿、许可/署名、使用位置、实际用量、完整检查和可播放文件在同一私有交付目录。

## 2026-10-29 成片配乐遮蔽与字幕提前：根因修复

- 授权：用户要求查清并解决已交付第六条视频的BGM过大、字幕提前。仅修生产实现与隔离验证；已认可的本机修正版、原片及生产状态保持，不新配音、不重制、不发布。本轮未获新的部署或主线推送授权。
- 基线：easel-v2-rebuild / 409a55f8，加开工前已有多文件Dirty；本轮增量不覆盖其他开发、画像及运行成果。
- 一手证据：严格按本片Work关联原工程、两条VOICE资产与回执。工程music gain=0.5；原VOICE timing无provider_alignment、word_timestamps=null、local_alignment=unavailable。原适配器仅显式subtitle_enable=true才请求字幕；本机对齐却又要求供应商先提供匹配的29秒内锚点，无锚点即退出。字幕编译最终回退模型时码，不是播放器时钟错误。
- 配乐首因：渲染原样应用模型增益、amix normalize=0，没有与实际旁白比较。原素材实测旁白均值约-25.4dBFS，配乐按0.5增益后约-21.62dBFS，配乐反而高约3.78dB；增益数值不能代表听觉相对音量。
- 最小修复：MiniMax默认请求已有字幕能力（显式false保持）；在现有可选本机对齐模块中，缺锚点或锚点过长时仅用本机识别定位短窗，再强制对齐确认原文。识别稿不替换正文；词句匹配不足、窗口不可靠或模型未安装仍如实unavailable，不下载模型、不重发TTS、不新增审核。
- 混音复用FFmpeg执行器：仅在旁白与music重叠处，测量真实裁切源的均值，以旁白优先的12dB均值差向下衰减配乐；保留已经更轻的增益、显式0、SFX和原声，纯音乐片保持。短组间隙合并，音量变化做短渐变。保存audio-balance.json列明请求/有效增益和依据；新混音缓存及作业身份含策略版本，不误取旧缓存。平均电平不是逐时刻峰值或人工听感保证。
- 原片隔离复验：已用未改字节的两条原VOICE实际运行本机识别与强制对齐，均返回received（63/73个原文字幕单元）；规范化原文完全一致，明确local_recognition_anchors=true、provider_paragraph_anchors=false、precision=estimated。无新增云模型/TTS调用。原音轨实测混音配方在旁白区间将music由0.5衰减为约0.08128；未据此重渲染原片，不能把配方验证冒充整片听审。
- 私有证据：保留本片exports/audio-subtitle-fix/root-cause-verification内的本机对齐结果、音量测量及配方；作品ID、原文、音频和实际路径不写入Git。
- 验收：固定源码下，continuous_narration、render_local、voice_subtitles、grouped_voice_render、creative_captions、revision_pipeline、creation_flow七组回归 **87 passed / 1 skipped**（61.54秒）。新增覆盖供应商字幕默认/显式关闭、无锚点及长锚点的声学窗口、无关识别拒用、长匹配块内部拆窗、衰减作用域/不提增/显式0、真实编码PCM电平与缓存依据复用；既有声音身份、字幕、修订和完整生产夹具回归保持。原VOICE业务请求另核对仅emotion=calm、speed=1，未开启字幕，不能将代码重建的HTTP正文当抓包。文档链接与diff格式检查通过。软件通过、部署及真实新片端到端分别判定；后两者本轮未执行，不关闭WV-01/CRE-01父任务。


### 同轮授权部署与定向确认

用户后续明确授权部署本次修复，保留已有Dirty与已认可修正版，不重新配音、不重制、不发布。部署前确认无在途Operation、无未结束Task，原8UNKNOWN保留；记录29张正式业务表的逐表行数/内容摘要及修正版文件摘要。未创建数据库或媒体备份。

按唯一主工作区既有LaunchAgent重载Easel Web；源码仍为easel-v2-rebuild / 409a55f8加保留Dirty，未改配置、Gateway或前端。新服务PID20003，工作目录核实为当前项目；正式/api/production/capabilities由reload_required=true变为false，首页HTTP200，三份修复源码的部署前后摘要一致。部署后针对字幕默认/显式关闭、无/长供应商锚点、误识别拒用、短窗分割、衰减作用域以及真实PCM/混音缓存依据复用的8项定向回归全部通过（40项未选择，2.45秒）；此前87通过/1跳过仍为完整关联证据，不将本轮8项写为全量回归。

部署前后29张业务表的行数和内容摘要完全一致，修正版MP4摘要不变：无新业务请求、配音、渲染或发布，旧UNKNOWN未处置。确认新源码已由服务加载、对应逻辑定向验证通过；未发送真实MiniMax请求、未新做一条影片，因此供应商实际新字幕回执与未来新片完整听感/同步仍NOT_TESTED，不关闭父功能。


### 本次修复单独提交

用户明确授权仅提交并推送本次BGM/字幕同步代码、测试及文档到easel-v2-rebuild；不含其他Dirty、个人画像与运行文件，不新增制作或发布。按代码段构造暂存树，排除同文件内其他任务的图解frame/情绪/恢复等变更。暂存仅8文件；隔离导出该树执行同七组适用测试，**83 passed / 1 skipped**（56.57秒），与此前含其他Dirty的87项结果分别记录。凭证模式、差异格式和文档路径检查通过，原工作文件内容校验保持；仅本段交接记录追加到工作区与暂存。后续Git身份以提交/远端回执为准，不把提交状态当作新片或供应商复验。
