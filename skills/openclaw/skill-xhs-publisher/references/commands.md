# xhs-publisher 命令样例

> 统一走 `../../shared/scripts/xhs_publish.py`。小红书默认使用 BitBrowser，脚本会按账号映射名
> 自动查找或创建环境，再通过 Playwright CDP 接管；无需提供 Profile ID。

## 环境检查

```bash
python skills/shared/scripts/xhs_publish.py check
# ✅ playwright 已安装 / ✅ BitBrowser Local API 可用
```

## 登录（headless：抠二维码成图片扫码）

```bash
python skills/shared/scripts/xhs_publish.py login
# 把登录二维码抠成 PNG → 默认 outputs/_login/xhs-login-qrcode.png（可在 Easel Web UI 的 outputs 查看）
# 用小红书 App 扫这张图 → 脚本轮询到登录成功后持久化 cookie（下次免登）
#   --qr-out <path>   自定义二维码输出路径
#   --timeout <秒>    等待扫码超时（默认 180）
#   --headed          本地有桌面时用窗口内扫
# 登录态保存在当前账号对应的 BitBrowser 环境
```

> ⚠️ **风险 IP 拦截**：小红书会把机房/公司代理出口判为风险 IP（报「安全限制 300012 · IP存在风险」），
> 此时二维码可能不弹。使用正常、稳定的网络环境后重试；遇到平台验证时交给用户处理。

## 发布前预检（dry-run，离线不启浏览器）

```bash
python skills/shared/scripts/xhs_publish.py plan \
  --title "500元改造出租屋の神仙好物" \
  --content "分享几个平价好物……" \
  --images /abs/a.jpg,/abs/b.jpg \
  --tags "出租屋改造,好物分享"
# 打印：标题长度校验 / 媒体 / 话题 / 7 步流程
```

## 图文发布

```bash
# dry-run（默认，不加 --exec 不会真发）
python skills/shared/scripts/xhs_publish.py publish \
  --title "标题" --content "正文" --images /abs/a.jpg,/abs/b.jpg --tags "AI,教程"

# 真正发布（首次建议 --headed 观察选择器，OK 后去掉转 headless）
python skills/shared/scripts/xhs_publish.py publish --exec --headed \
  --title "标题" --content "正文" --images /abs/a.jpg,/abs/b.jpg --tags "AI,教程"

# 真实填充验收：上传、输入并从平台 DOM 读回图片/标题/正文，但绝不点击发布
python skills/shared/scripts/xhs_publish.py publish --verify-only --headed \
  --title "标题" --content "正文" --images /abs/a.jpg,/abs/b.jpg --tags "AI,教程"
```

## 视频发布

```bash
python skills/shared/scripts/xhs_publish.py publish-video --exec --headed \
  --title "标题" --content "正文" --video /abs/clip.mp4 --tags "vlog"
# 视频上传后脚本等发布按钮可点击（最长 10min = 平台处理完成）再提交
```

## BitBrowser 与账号映射

```bash
XHS_BROWSER_BACKEND=bitbrowser  # 默认值，仅小红书使用
XHS_BITBROWSER_ACCOUNT=main     # 账号映射名；自动查找/创建环境
BITBROWSER_API_URL=http://127.0.0.1:54345
--bitbrowser-account NAME       # 临时覆盖账号映射名
--browser-backend playwright    # 仅用于兼容/排障，不会自动回退
--keep-open                  # 发布后不关闭浏览器（调试用）
```

## 参数速查

| 参数 | 说明 |
|------|------|
| `--title` | 标题，≤20 全角字（脚本按小红书口径 `calc_title_length` 校验） |
| `--content` | 正文 |
| `--images` | 图片路径，逗号分隔（图文发布；绝对路径） |
| `--video` | 视频路径（视频发布；绝对路径） |
| `--tags` | 话题，逗号分隔（如 `AI,教程`；脚本走话题联想真绑定） |
| `--exec` | 真正发布（缺省为 dry-run） |
| `--verify-only` | 真实填写后读回验收，但不点击发布 |
| `--headed` | 有头模式（首次校验选择器） |

## 排障

- **未登录**：先 `login` 扫码。
- **步骤超时 / 找不到元素**：小红书改版了——改 `xhs_publish.py` 顶部 `SELECTORS` 字典（单点维护，每条标了参考源），先 `--headed` 观察定位。
- **发布未确认成功**：只有 URL 跳转或平台明确成功提示才算成功；若卡在发布页说明平台校验未过（标题/正文超限、内容违规等），按提示排查。
- **自检**：`python skills/shared/scripts/xhs_publish.py selftest`（离线，验选择器字典/标题算法/参数解析）。
