# v0.6 BGM 首轮能力校准：FAILED，未进入生产修复或作品恢复

日期：2026-10-05。范围：唯一[后续 Task](../tasks/creation-latency-2026-10-02.md) G0，以及其停止条件允许的一项现成辅助能力比较。结论：**没有规则同时满足关键负例零误放行和器乐至少 5/6 合格；G0 能力门未通过，G1/G2 未启动。** 原作品仍为 8/9 / MATERIAL_NOT_READY，不能认领目标完成。

## 1. 身份与预处理核对

- 生产基线：`ad31091e`；工作分支 `easel-studio`。本轮只新增离线实验工具和证据、更新状态路由；没有改生产模块、加载服务、安装模型、恢复 Owner 或调用付费 Provider。
- 现有模型：`MIT/ast-finetuned-audioset-10-10-0.4593` / `f826b80d28226b62986cc218e5cec390b1096902`。三个文件摘要与 `music_observation.py:MODEL_FILES` 全部一致：

| 文件 | SHA-256 |
|---|---|
| config.json | a93d525511d77e8ecc933d09674b85099815bbbb417c228a4edd655e252fb9ff |
| preprocessor_config.json | 8d04ba5a9c6fca5d39d0de2b1fd05ecf79deb589fbba279728bbebac39934231 |
| model.safetensors | ae0c1e2ad4e1381d851fa9bf298ba13ebc9c5a914cdee2dbe427a6583869924d |

- 本机 527 个标签与 AST 官方 `31088be8a3f6ef96416145c4b8d43c81f99eba7a` 的 `egs/audioset/data/class_labels_indices.csv` 逐项一致。确认 Choir、A capella、Yodeling、Mantra 是人声相关类别；Singing bowl 是不同的乐器类别，不使用名称通配符扩展声乐集合。
- 代码核对：FFmpeg 解码为 16kHz 单声道；特征为 128 mel / 1024 帧，`(fbank - (-4.2677393)) / (4.5689974 * 2)`；模型 logits 后 sigmoid。10 秒窗、5 秒步长和完整尾部与当前实现一致。
- 实验环境：torch 2.14.1、transformers 4.57.6、numpy 2.5.3、FFmpeg 8.1。未装 torchaudio，实际使用 Transformers 内置 NumPy fbank 分支；核对其 Hanning、400 样本帧长、160 步长、512 FFT、预加重、去直流和归一化源码。**这是实现/配置核对，未声称已做原始 torchaudio 分支的逐元素数值等价实验。** 特征提取源码 SHA：`bcf0729ca7e380d09cd9ce93de477900ac6cb2d8ca048e59fa8370b51007ed56`。运行时出现 mel 空滤波器警告，固定模型与提取器仍正常完成；不凭该警告认领根因或更换预处理。

## 2. 样本、许可与预登记

- [固定样本清单及逐来源证据](fixtures/bgm-g0-manifest-2026-10-05.json)：32 个基础样本，8 个风险层各 4 项，原始来源划分校准/留出各 16；另有短人声混音各 16 项，合计 64 个音频。
- 28 个媒体来源取自 MUSAN 原始分类与标注：器乐 N、含声乐 Y、中英文 LibriVox 旁白和背景噪声；另 4 个是本地生成的静音、440Hz/1000Hz 纯音、脉冲。合唱包括 Advent Chamber / Handel 和 Tudor Consort / Scarlatti 的独立原始录音；弱人声由另四项已标注旁白衰减得到。
- 逐曲标注/许可证保存在原归档中，并与 FluidInference/musan `3edcfdf89b56dbe6a395ff29f9c29489e03d1321` 映射核对。媒体按需从 `thusinh1969/musan` 固定提交 `386f1cb86397a73ec5f3c124246cc0896bf8f873` 的 `musan/musan.zip` 读取；中央目录列出 2050 个成员，选定成员完整解压并验证 ZIP CRC，源文件总计 99,199,598 字节。没有下载 11GB 整包；源文件 SHA、成员路径、标注与对应许可块均在清单中。
- 原始来源在跑分前确定，选择时的标注断言排除了不满足器乐 N 的候选，没有根据模型分数换样本。同曲变体和混音的两个来源均不跨校准/留出；不同歌曲同表演者不视为同一录音。
- 低能量层使用原始器乐片段 ×0.03，弱人声层使用独立旁白 ×0.01。曲尾层保留真实原始终点；末 2 秒 RMS / 前段 RMS 分别约 0.00012、0.0329、0.0428、0.0706，说明存在能量衰减，仍不替代独立试听。该小集不证明覆盖所有自然稀疏器乐、吟唱或哼唱分布。
- 短人声混音由已标注中文旁白的有能量区段插入已标注器乐：0.5/3 秒，首/5秒窗口交界/中/尾，语音与音乐 RMS 比 -6/-18dB。区段及混音参数在模型跑分前确定，不由 AST 分数生成 ground truth；没有对每个短区段执行人审逐字转录，结果的适用范围是这些来源和变换。
- [首轮参数预登记](fixtures/bgm-g0-policies-2026-10-05.json)：现规则基线；A 只补声乐标签；B 使用 Music 0.5/0.6/0.7/0.8、覆盖率 0.9/0.95/1、最大 unknown 2/5秒、边界过渡 0/2秒的有限网格。Music 支持按窗口边界分割真实时间区间，要求所有覆盖窗一致支持；不以重叠窗数、总均值或多数票消掉声乐风险。
- 原作品 BGM SHA `531ebe4ef5a843c5cd98cf4b56b917898907785276506a7f896270853dc93f03` 未出现在媒体或源文件摘要中；原报告没有参与参数选择或新规则应用。两轮实验只观察校准的 32 项，**留出的 32 项未跑分，也未选择留出规则。**

## 3. 首轮 AST 结果

通过条件沿用 Task：器乐至少 5/6 合格、三层各至少一项；26 个校准负例（10 个基础 + 16 个混音）零误放行。unknown 计作正例未通过。

| 规则 | 器乐合格 / 6 | 负例误放行 / 26 | 能力门 |
|---|---|---|---|
| 生产旧规则 | 1 / 6 | 5 / 26 | FAILED |
| A：补全标签，保留旧阈值 | 1 / 6 | 5 / 26 | FAILED |
| B：能通过 5 项器乐的候选 | 5 / 6 | 5 / 26 | FAILED |

全部 50 项评估（基线、A、48 个 B 参数组合）没有可选规则；校准过程 104.899 秒。不能凭五项音乐合格就冻结 B，也不能把“补全标签”当作短人声风险已解决。

具名反例：`calibration-speech-mix-0.5s-6db-at-15s`。30 秒器乐中部包含 0.5 秒中文旁白，全部窗 Music 最低 0.950700，补全标签后人声最高仍只有 0.002588；旧规则、A、B 都认领 `instrumental_music`。其余四个误放行也为预登记的 0.5 秒插入变体。**这不是原作品 BGM 有人声的证据，而是“10 秒 AST 窗 + 当前声乐标签阈值足以证明纯器乐”这一能力假设不成立的反例。**

## 4. 一项现成辅助能力比较

AST 首轮失败后按 Task 停止条件比较本机已有能力：faster-whisper 1.2.1 附带 `silero_vad_v6.onnx`，SHA `4cbf549b8326f60f80f2536d9eefeb450a9abe83365a098031c89719f1be17d2`。未安装或下载模型；不把 speech VAD 当唱歌检测器，AST 原声乐检查仍保留。

[辅助比较预登记](fixtures/bgm-g0-vad-comparison-2026-10-05.json)在 VAD 跑分前保存。固定 16kHz / 512 样本步长，VAD 0.3/0.5/0.7、连续风险 64/128ms 作为额外 veto，比较 288 个 C 组合；原 AST 报告完全复用。VAD、派生评估及技术反例合计 11.648 秒。

| C 的条件 | 实测结果 | 能力门 |
|---|---|---|
| 负例零误放行 | 器乐最多 4 / 6 合格 | FAILED |
| 器乐至少 5 / 6 合格 | 负例至少 4 / 26 被误放行 | FAILED |

纯器乐 `music-fma-0010` VAD 最大约 0.506511；多个短语音混音最大约 0.504144。简单 veto 阈值在该集合中无法同时保留器乐与识别所有插入语音。不继续围绕同样本追加任意组合，不将此比较直接部署。

## 5. 技术与复现验证

- 隔离候选拒绝 8 项技术反例：非有限时长/分数/RMS、起点覆盖缺口、缺尾、缺 Choir、错误音频 SHA、实际解码失败。**这些是候选实验验证，不是生产规则已修复声明。**
- 同时复现独立生产缺口：在合法器乐报告中只将 `duration_seconds` 改为 NaN，当前 `assess_music` 仍返回 `instrumental_music`；候选校准器明确拒绝。后续 G1 需要将非有限时长拒绝与标签、策略身份一起保护，但当前未进入 G1。
- 单一离线工具：[scripts/calibrate_bgm.py](../../scripts/calibrate_bgm.py)。只读取本地媒体、保存隔离原始分数并比较固定规则，没有 Asset 注册、Gate 更新、Owner 恢复或网络/付费模型入口。当前工具补充了媒体重建功能；两次实际运行各自的原脚本快照与锁中 SHA 已核对，原记录不改写。
- 64 项媒体按清单从原始文件/确定性信号重建，全部字节 SHA 一致。50 项及 338 项（含 288 个 C）评估离线重放与原结果逐项一致；没有新增 AST 推理或解封留出。
- `pytest -q tests/test_material_audio_supply.py`：**4 passed**。`compileall`（该脚本）及 `git diff --check` 通过。本轮未改生产代码，不重新认领以前的 701/5 为本轮验证。
- [机器可读评估摘要](fixtures/bgm-g0-evidence-2026-10-05.json)保存模型/观察/参数/脚本身份、逐窗口 Music 与现有/扩展 vocal 最大值、原完整报告摘要和全部候选指标。完整 527 标签报告、VAD 分数、媒体及原脚本快照保留在本机实验目录 `/tmp/easel-bgm-g0-20261005/`，未进入 Git；重新实验需复现完整原报告，摘要不替代原始证据。

在项目根目录使用清单复现媒体（原始来源先按清单取得，示例路径可替换）：

```bash
.venv/bin/python scripts/calibrate_bgm.py \
  --manifest docs/acceptance/fixtures/bgm-g0-manifest-2026-10-05.json \
  --preregistration docs/acceptance/fixtures/bgm-g0-policies-2026-10-05.json \
  --source-root /tmp/easel-bgm-g0-20261005/sources \
  --media-root /tmp/easel-bgm-replay/media \
  --output /tmp/easel-bgm-replay/results --phase calibration --prepare-only
```

去掉 `--prepare-only` 即在新的隔离目录执行首轮校准；加 `--vad-preregistration docs/acceptance/fixtures/bgm-g0-vad-comparison-2026-10-05.json` 可在另一新目录执行具名辅助比较。工具在任何分数前保存输入锁，校准无可行规则时拒绝 `--phase holdout`；修改参数须新目录，已观察过的留出不能反复调参再宣称通过。

## 6. 原作品与后续边界

只读核对原 Creation `cr_77175a2271bf4e408a359884efc438e6` / Attempt `fa_22f91d9f97ab6e7c355d46ba87bb478b`：Gate MATERIAL_NOT_READY，唯一 blocking Need 为 `bgm_subordinate`，Owner 为 `material_supply_exhausted`，原 BGM 报告仍为 50 窗。原 Plan/Bundle revision 与[R16 恢复记录](creation-latency-v05-material-resume-2026-10-05.md)保留，现有预算/调用/失败记录没有写入；无 Authoring/Build。

当前可部署 BGM 策略为零，**不执行 G1/G2，不声称 9/9、自主完成或提速比例**。原方案首轮和一个辅助比较均已触发停止条件；后续需重新界定并验证一项声音能力或正式素材证据路径，再恢复原 G0 能力门。原样本不足以支持任意音乐的可靠性结论；如未来新规则通过校准，仍须面对未观察的独立留出，不能用本次失败历史换取放行。
