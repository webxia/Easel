# BGM 本地声学观察：独立样本检查

日期：2026-10-01。范围：固定模型实际加载、公开音频片段分类与受控语音混入；不是 Creation E2E、人工听感验收或分类准确率评测。

## 目的与执行

核对新接入的 BGM 声学判断是否只能通过 Fixture，尤其是否把低人声分数直接当成可用配乐。执行代码为 `easel/materials/application/music_observation.py` 的 `classify_music` / `assess_music`，本轮开始版本 `09359bfd`；没有改判断阈值。

- 模型：[MIT AST AudioSet](https://huggingface.co/MIT/ast-finetuned-audioset-10-10-0.4593/tree/f826b80d28226b62986cc218e5cec390b1096902)，固定 revision `f826b80d28226b62986cc218e5cec390b1096902`。权重 SHA-256：`ae0c1e2ad4e1381d851fa9bf298ba13ebc9c5a914cdee2dbe427a6583869924d`；配置/预处理文件也经代码摘要核对。
- 本地 CPU，torch 2.14.1 / transformers 4.57.6；不访问模型推理 API，不使用 API key。样本按现有 ffmpeg 路径转为 16 kHz 单声道 WAV，最长取前 30 秒；模型使用重叠 10 秒窗口，尾部完整覆盖。
- 公开原音频及署名文件从 [librosa 示例数据](https://librosa.org/data/audio/)取得，逐文件 SHA 与已安装 librosa 的 `util/example_data/registry.txt` 比较一致。模型只读取波形，不读取曲名、说明、期望标签或本表。
- 模型与原始报告留在 `/tmp/easel-ast-validation-model`、`/tmp/easel-acoustic-check`，没有加入 Git 或设为生产模型路径；没有读取、更新或继续现有 Creation。

## 样本来源与署名

| 样本 | 来源与许可 | 下载原文件 SHA-256 |
|---|---|---|
| trumpet | Mihai Sorohan，Jazz Trumpet Loops Pack in F 90 bpm；[Freesound 77711](https://freesound.org/s/77711/)，[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | `8374466fd3951d24509da6e799b132a0db0bdeda69d99c69d989a6888d3d727d` |
| vibeace | Kevin MacLeod，Vibe Ace；[Free Music Archive](https://freemusicarchive.org/music/Kevin_MacLeod/Jazz_Sampler/Vibe_Ace)，[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | `6c23aed3dd5aa57f2b1652ecab68d15d9b82ad257f54e639eb2880ca09bc118a` |
| fishin | Karissa Hobbs，Let's Go Fishin'；[Free Music Archive](https://freemusicarchive.org/music/Karissa_Hobbs/Age_of_Flowers/09_Lets_Go_Fishin)，[CC BY 3.0](https://creativecommons.org/licenses/by/3.0/) | `27b3667c396c1831511aa3c415fcf582b6e8be560cafb844c5b67b76b72c1cb3` |
| libri1 | Ashiel Mystery 第 2 章，Garth Comira 朗读；[LibriSpeech SLR12](https://www.openslr.org/12/)，[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | `a284612b46af0535f7e1873758c4387bb8369f6dbbe192ffdec1f171108f98dd` |

以上许可来自随示例提供且已核对摘要的 `.txt` 来源记录；本次只用于本地检查，没有发布媒体或导入用户内容库。

## 实际输出

Music 最低值取所有窗口，Vocal 最高值取所有窗口的声明人声标签最大值。它们是多标签 sigmoid 模型分数，不是校准概率。

| 样本 | 实际秒数 | Music 最低值 | Vocal 最高值 | 当前程序结论 |
|---|---:|---:|---:|---|
| trumpet | 5.3334375 | 0.643509 | 0.005402 | unknown |
| vibeace | 29.995 | 0.867861 | 0.002260 | instrumental_music |
| fishin | 30.000 | 0.851370 | 0.205030 | vocals_detected |
| libri1 | 14.840 | 0.000823 | 0.852921 | vocals_detected |

trumpet 的最高标签是 Trumpet（0.846862），但 Music 不足当前 0.8 路由要求，保留 unknown。它说明已知乐器片段可能被保守策略排除；没有为通过这一样本而降低阈值。vibeace 的首窗口次高风格标签不足 0.2，不能因分类为音乐就宣称已验证其情绪、乐器或曲风。

用于分类的 WAV 摘要依次为：

- trumpet：`d8938c51e26973fae1d69f193882a149cd96cc3911c1e4c11dcf3b74a952fd14`
- vibeace：`c6e6f0ab61fa2d32030fa09c14031baf341e7344041ed42f0099234739df250a`
- fishin：`3e3edbd55320f5e05a7298e71092a64143eb948e350575164801525da6b5b1fa`
- libri1：`1baff38d94ba3c02826aec7fe26aba8353f684b4ce20f24481684f6c786f34b6`

另取 vibeace 和 libri1 的共同前 14.84 秒，各自归一至 RMS 0.1，然后按指定相对 RMS 混合，无动态压缩或降噪。其来源与署名保持不变：

| 朗读相对音乐 RMS | Music 最低值 | Vocal 最高值 | 程序结论 | 混合 WAV SHA-256 |
|---|---:|---:|---|---|
| 0 dB | 0.728666 | 0.649250 | vocals_detected | `f9d1e50565fe62e1b3e57833f854a296de0b2083812a4716ad50cc2799e4f61a` |
| −12 dB | 0.632621 | 0.465077 | vocals_detected | `8858648c36040fdb60cdd7c9c1766cf097c0e23fbc0229bea98ba2a44d6a872b` |
| −24 dB | 0.614477 | 0.429394 | vocals_detected | `258fae8d1b441a6a02a7015c937a7cdbe05483d895b27a2069fb30b296009d35` |

四个原片段分类分别耗时约 3.92 / 1.58 / 1.60 / 0.76 秒；同一进程依次调用，每次重新加载模型。特征提取保留官方实现的零 mel filter 提示，没有静默修改模型预处理。本轮没有建立性能 SLA。

## 结论与后续边界

模型实际路径可执行，至少有一个独立公开配乐片段通过；歌曲、朗读以及三档受控语音混入没有被作为 instrumental_music 放行。此前纯音 negative smoke 与本轮结果共同支持继续局部集成，无依据调整阈值。

这些样本数量少，未构成人工标注的盲测集；不能推算召回率、误拒率，也不证明中文弱人声、合唱、无词吟唱、密集音乐、整首长曲或情绪/音色判断可靠。短乐器片段的 unknown 仍是已知覆盖限制。软件的省确认路径已接通，真实音乐校准、旁白表达质量及内容缺陷恢复仍未完成；总体 Goal 保持 active / NOT_READY，真人 E2E 尚未启动。
