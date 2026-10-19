# S6-09 · 可编辑工程合同与渲染接入
> **调度状态：CLOSED · 2026-10-19**。用户决定关闭本卡独立研发排程：既有实现和软件验收结果保持原样，仅作为历史交付与回归依据；不再从旧实施步骤重新派发任务。后续确有实证缺陷时，仅纳入[当前三项主线](../04_CURRENT_STATE.md#唯一研发下一动作)做局部修复。CLOSED 不代表全部真实模型、音画质量、完整规格或 Creator 接受已通过。

状态：**LOCAL_BACKEND_IMPLEMENTED / INTEGRATED**；真实本地编辑后端及主线接入已实现，正式作品质量和未跑平台仍待对应真实验收。

- **依赖**：S6-01、S6-06。
- **需求主/协作覆盖**：V2-EXP-009, V2-EXP-015, V2-EXP-022, V2-EXP-025。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：easel/production/editors/base.py、hypit.py或ffmpeg.py；media.py；tests/production/test_editor_contract.py、test_render_local.py。
- **执行分支建议**：`codex/s6-09-editor-adapter`。

## 实施步骤

1. 定义EditProject/manifest和capabilities/check/build/observe/cancel/collect，使用稳定素材句柄、场景到原生节点映射；不再造完整通用媒体DSL。
2. 核查目标Hypit版本/公开协议/分发许可与平台支持；禁止直接复制V1锁0.2.7/内部摘要/darwin-arm64 parser。先判断可用接口，再实现一个受支持适配器。
3. 独立无真实凭证环境用许可本地媒体验证纯编辑/渲染；HOME/Runtime凭证不能靠env白名单假设隔离，外部素材/代码URI要拒绝或受控。
4. 若Hypit无法满足纯制作边界，记录其unsupported并在受限时间线FFmpeg或公共Remotion接口中选择符合需求的替代；不得原样搬SDK审批/品牌/风格规则。若替代仍不能满足则只阻塞此任务，其他独立任务继续。
5. 复用assemble.py需显式规范duration/audio/pad/subtitle/音量0，不沿用静默替换/漏音效/补帧行为；渲染中断复用输入资产。
6. 交付具名编辑器决策ADR：精确版本/平台/许可条件、公开接口、已测能力与缺口，回写14/15的具体选择；目标范围不能由一个简单样片替代。该决定在本卡内完成，不是独立任务的开工前置。

## 通过标准与负例

用本地许可媒体实际覆盖原声、静音（无音轨）、音乐/旁白及混音、字幕/裁切局部修改、两画幅/1080级MP4、显式时长，且不产生新生成调用；有工程/handle/结果hash；越界文件/任意URI拒绝；取消/重启明确处理。1/900秒边界具名登记，缺口返回对应实现任务，完整真实样片归S6-14。无后端不能以fake或弱化要求完成本卡。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_editor_contract.py tests/production/test_render_local.py
```

**交付要求**：至少一个真实本地编辑后端接通且记录精确版本/能力；对未跑平台/规格不报PASS。安装或Runtime变更需在本卡明确范围，不能动用户生产配置。

## 执行记录

实施基线：`4525b09da8bfc30ba556dba2198872a23b35a0ae` 上的 `codex/s6-production` 工作区。新增 `editors/base.py`、`ffmpeg.py`、`render_worker.py`、`media.py` 及两个测试文件；具体取舍、版本/许可证和能力范围见 [ADR-S6-009](../decisions/ADR-S6-009-local-editor.md)。未安装依赖、未调用 Hypit 或媒体生成服务、未触碰用户 Runtime/素材。

本机 FFmpeg/ffprobe 8.1、Pillow 12.3.0、Python 3.12.13，macOS arm64。执行 `python -m pytest -q tests/production/test_editor_contract.py tests/production/test_render_local.py` 验证合同与真实短片；另以 `EASEL_RUN_LONG_MEDIA=1` 启用真实 900 秒编码，长片用具名独立用例，不借短片宣称全部组合通过。

启用长片的编辑器整组实际结果为 **20 passed（45.05 秒）**。加入声音/设置 HTTP、真实 worker 和字幕底片保护后，以隔离测试环境执行：

```bash
EASEL_RUN_LONG_MEDIA=1 /tmp/easel-s6-worker-venv/bin/python -m pytest -q tests/production/test_editor_contract.py tests/production/test_render_local.py tests/production/test_voice_subtitles.py tests/production/test_voice_settings_api.py
```

当时联合结果 **33 passed（46.32 秒）**，包含真实 900 秒编码。随后新增的固定声音+字幕主线实际导出用例与具体结果见 S6-10；不把其后增加用例伪装成这次联合运行已覆盖。

独立边界用例为 `test_900_second_boundary_real_encode`：实际生成 1920×1080、24fps、900秒、无音轨 MP4，输入是合成静态图片，实测时长误差小于0.1秒。可单独复现：

```bash
EASEL_RUN_LONG_MEDIA=1 /tmp/easel-s6-worker-venv/bin/python -m pytest -q tests/production/test_render_local.py::test_900_second_boundary_real_encode
```

最后独立复验实际结果：**1 passed（38.85秒）**。

已覆盖：原声、静音无音轨、音乐/混音、两种 1080 画幅、1 秒/900 秒、视频溶解、明确图片推拉、字幕/裁切修订、幂等、取消、重建 adapter 观察/恢复、坏引用/摘要、伪装播放列表和零音量；字幕修改前后导出 AAC 字节相同。实际导出视频的中文/英文字幕帧人工查看未发现裁切或缺字。输出 receipt 另保存同版无字幕合成底片路径与摘要，供修改字幕预览，防止把新字幕叠在旧烤录字幕上。

真实模型生产、自然声音、跨题材导演效果、Ubuntu/Windows、完整时长/模式组合仍 **NOT_TESTED**。渲染完成不写首版合格或用户接受状态。S6-10/11 已连接素材句柄、音轨设置、编辑工程及结果登记；后续验证应覆盖对应实际题材与平台，不重复实施本后端。
