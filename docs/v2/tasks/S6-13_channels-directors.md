# S6-13 · 频道管理、参考拆解与导演版本

状态：**NOT_STARTED**；代码/测试目标尚待实现或接入。

- **依赖**：S6-02、S6-08、S6-10、S6-12。
- **需求主/协作覆盖**：V2-EXP-002, V2-EXP-003, V2-EXP-019, V2-EXP-020, V2-EXP-010。
- **目标与合同**：[可执行设计](../15_IMPLEMENTATION_DESIGN.md)；[任务包共同约定](S6_IMPLEMENTATION_PLAN.md#2-每张卡开始与完成的共同约定)。
- **预计落点**：production/channel/director服务；ProfilePage/BreakdownPage/新频道导演组件；tests/production/test_channels_directors.py；tests/frontend/directorLifecycle.test.mjs。
- **执行分支建议**：`codex/s6-13-channels-directors`。

## 实施步骤

1. 频道/导演命名编辑归档，一画像多频道、多对多导演版本；默认与单片覆盖可见，临时作品不强制选择。导演PATCH归档后不供新作默认推荐，频道可清除默认；失效时提示选择，不静默替代，已确认作品仍固定旧版本。
2. 参考真实媒体/片段→带时间证据的观察与推测→风格确认→本片试片→接受保存；多个参考主次可讨论，无法访问不猜测。
3. 风格包含叙事/视听但不固化脚本模板；跨频道不复制题材经历。已有Breakdown文本模板功能不得改名冒充视频拆解。
4. 正式首版可作为试片；双接受各有记录。导演更新明确另存版本，不自动升级频道默认；草稿不可自动成为全局默认。
5. 画像删除/归档影响明确，既有快照不漂移；音色字幕长期保存使用S6-10同一服务，不自建第二套默认规则。

## 通过标准与负例

新建频道不新建人设；共享导演不借经历；无频道正常创作；未接受导演草稿可本片试用但不可默认；接受作品不等于接受导演；参考证据有时间范围；新导演版本不替换旧作品/default；默认导演归档后新作提示而不自动替换，历史/在途引用保持。

## 验证入口（本卡实现相应文件后执行）

```bash
python -m pytest -q tests/production/test_channels_directors.py tests/test_persona_security.py
node --test tests/frontend/directorLifecycle.test.mjs tests/frontend/personaSession.test.mjs
npm --prefix web/frontend run lint
npm --prefix web/frontend run build
```

**交付要求**：完整导演形成与频道管理上线为功能而非只有CRUD表；不把这部分推迟成可省略的体验优化。

## 执行记录

**验证：NOT_TESTED。** 实施时记录受测提交、实际命令/结果及未覆盖项。
