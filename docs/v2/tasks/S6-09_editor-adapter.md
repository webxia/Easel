# S6-09 · 可编辑工程合同与渲染接入

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

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

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
