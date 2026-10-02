# Creator 素材缺口恢复

历史基线 / 具名验收记录（2026-10-02 归档标识）：下文状态、当前作品、恢复授权与 READY 判断只适用于当时范围，不是当前执行指令。当前唯一范围见 [自主首版 Task](creator-autonomous-first-cut-2026-09-30.md)，实际状态见 [Current State](../02_CURRENT_STATE.md)。

状态：软件修复与同一 Creation 的阶段恢复完成；最终音画修订版已由 Creator 确认并入库，未发布。自主 E2E 因工程介入为 FAIL，不能将入库等同自主性通过。用户授权先修复根因，再继续同一个 Creation；本次现有旁白明确允许使用，无需再次确认或生成。

根因：Planning 将真实授权素材误收窄为特定来源，长镜头说明直接变成检索词；素材 NOT_READY 后没有正式来源修订/补料入口，重跑 Supply 又丢弃既有素材集合。

范围：制作开始前，正常作品区提供一次有身份绑定、幂等留痕的素材恢复操作。仅允许明确选择扩展配乐来源及修改检索提示；保留脚本、场景、Director、冻结 Handoff 和生成音频。复用字节核验通过的素材，只检索未覆盖需求；不调用生成、不提交 Build。脚本、规格和场景修改不在本次范围。

边界：不更改 Material V1.3 Domain；来源修订记录旧/新 Plan revision 和原 Bundle checkpoint，重新计算 Match/Rights/Readiness，不升级未知权利或伪造语义证据。已执行/批准制作时拒绝该恢复。付费生成批准不能复用到新生成。用户本次旁白指示通过既有正式 Rights 复核记录为素材级许可声明，不当作第三方条款保证。

依赖与顺序：检索提示合同及保留素材 Supply → 正式素材恢复入口及 revision 身份/幂等性 → 普通作品区动作 → 确定性跨模块验证 → 同一 Creation 阶段重放。

验收：恢复不丢既有 Asset/证据、不重新请求已覆盖需求、不调用付费生成；过期身份与已进入制作的状态阻断；相同请求复用结果；旁白脚本哈希与生成历史保留；重新 Match/Readiness 仍阻断不合格/未知许可素材。真实验收只使用现有一个 Creation。


追加根因：生成旁白没有可用语义证据；原匹配复核只支持视觉，Creator 已试听通过的结论无法进入 Gate，已获许可音频反而被 UI 误报为缺失。复用既有素材/SHA 复核入口支持脚本绑定旁白及配乐试听，未知 Rights 和署名缺口独立阻断。普通 Rights 卡只列实际待处理素材，不重复复核已准入许可。

验证：127 项 Preparation/Material/生成/制作边界测试通过；随后音频审核与来源修订最终增量的 Material/Compiler/Rights/敏感接口组合 52 passed（28 deselected）。前端 lint/build、compileall、技能合同验证、diff check 通过。回归覆盖同请求复用、Supply 已完成但 Gate 更新中断时对账、旁白脚本身份错配拒绝、音频试听不能清除 Rights/署名阻断、父 SupplyRun 链接和原素材保留。

实际阶段重放：仅现有 Creation `cr_046bb34c26a7444f9fd335c991ec1cc4`。记录 Creator 当前旁白使用声明及已给出的试听结论；旁白不再阻断。普通补料入口运行完成，原 7 个 Asset 全部保留，当前 38 个 Asset，生成记录仍为 1 次。剩余 5 个视觉 Need 与 1 个配乐 Need 待核对。没有新 TTS、Authoring、Plan、Build、最终输出或入库；不宣称本轮 Creator E2E 通过。

## 同一作品局部修改阶段修复

实际进展已进入 [音画验收](../acceptance/creator-audio-quality-e2e-2026-09-30.md)：素材通过、一次零媒体 Provider 计费 Build 导出 36 秒音画成片，第四场景因从原片开头取景而近黑。普通 composition 反馈开启同一 Creation 的修订 Attempt；第一次修订 Authoring 未提交 Build，模型网关 502 后重试 400，返回 HTML 错误页。

新增根因与最小范围：隔离助手只具备文件 read/write/edit，无法列目录，但合同没有文件索引，导致反复猜目录/包版本文件名；错误被统一异常丢失；局部修改提示声称声音不变，却缺少正式产物对比，隔离草稿实际改了 gain/fade 和字幕。提供只读合同索引与精确路径；仅保留安全的模型失败分类/退出码，不写原始模型输出或凭证；在产物提升前、完成 Authoring 与 Plan 前对比原可信 checkpoint 的音轨/来源/规范化/时间线及字幕/排版引用，变更拒绝。原成片 fingerprint 变化也拒绝。明确局部补丁保留原组件 ID/声音/字幕，不整片重写。

不改变素材 Domain，不换 Provider，不改现有声音，不延长超时，不绕过 check/核价/费用/审片门。确定性 Authoring/Hypit/Material 边界组合 79 passed，compileall 与 diff check 通过；真实页面仅重放同一失败修订阶段。服务重载后页面先显示最后可信状态，刷新返回恢复同一作品，未因断连重复派发。局部修改结果与最终审片仍待实际验证。

追加已观测根因：局部 trim 按错误帧率换算，静态校验没有原片范围证据，越界直到 Build 才拒绝。安装版源码确认 recipe/Normalize 时钟/原片标准化帧数语义；前置准入视频截取检查，错误源码由正常 Authoring 修复，不手动裁素材。失败 Build 恢复遇到无效编排停在 AUTHORING_REPAIR_REQUIRED，素材/内容保留，完整 Authoring 通过后才 READY，重新核价/批准不变；相同恢复请求不能覆盖修复中源码。83 项组合回归和前端检查通过，实际恢复已拦截同一越界范围并进入正常编排重试。

恢复路径继续暴露原生 Run 的隔离校验副本漏复制绑定身份 sidecar；成对复制至同目录临时校验名后仍走原身份转换器，错配/缺失均拒绝。扩展既有 selection integration，83 项回归通过，正常 UI 仅重放同一失败恢复 Attempt。

## 收尾状态

同一 Creation 最终恢复 Attempt `fa_4839c063b5849993dcd0720b965bc41e` 经普通编排/核价/制作/审片完成 36 秒输出；Creator 明确确认保存内容库。Selected Output 与归档 SHA 一致，配乐 CC BY 署名保留，旁白没有重复生成，未发布。完整身份、质量限制、人审回复与最终指标见 [音画验收收尾证据](../acceptance/creator-audio-quality-e2e-2026-09-30.md#最终修订creator-审片与入库收尾证据)。上文未完成状态为当时阶段现场；当前用户暂停后仅授权文档提交推送，不继续生产或开启另一作品。
