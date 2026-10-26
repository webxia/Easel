"""Explicit custom cover upload shared by the existing browser publishers.

A requested cover must never silently fall back to a platform recommendation.
All selectors are scoped to cover editing, never the main media upload input.
"""
from pathlib import Path


def apply_custom_cover(page, platform, path):
    if not path:return
    if not Path(path).is_file():raise ValueError('所选封面文件不可用，尚未提交')
    labels={
        'douyin': ('编辑封面','设置封面'),
        'xiaohongshu': ('设置封面','编辑封面'),
        'kuaishou': ('编辑封面','设置封面'),
        'weixin-channels': ('选择封面','修改封面','编辑封面'),
    }
    opened=False
    for label in labels.get(platform, ()):
        button=page.get_by_text(label,exact=True)
        if button.count() and button.first.is_visible():
            button.first.click();opened=True;break
    if not opened:raise RuntimeError('未找到本平台的封面编辑入口，尚未提交；请核对页面')
    dialog=page.locator('[role="dialog"]:visible, .semi-modal:visible, .ant-modal:visible, [class*="cover-modal"]:visible').last
    dialog.wait_for(state='visible',timeout=10000)
    for text in ('上传封面','本地上传','自定义封面'):
        tab=dialog.get_by_text(text,exact=True)
        if tab.count() and tab.first.is_visible():tab.first.click();break
    upload=dialog.locator('input[type="file"][accept*="image"], input[type="file"][accept*=".jpg"], input[type="file"][accept*=".png"]').first
    upload.set_input_files(str(Path(path).resolve()),timeout=15000)
    # Wait for the editor's actual image preview, not just an accepted argument.
    dialog.locator('img[src^="blob:"], img[src^="data:image"], img[src^="https:"]').first.wait_for(state='visible',timeout=30000)
    clicked=False
    for text in ('确认','确定','完成'):
        button=dialog.get_by_role('button',name=text,exact=True)
        if button.count() and button.first.is_visible():button.first.click();clicked=True;break
    if not clicked:raise RuntimeError('封面尚未确认，尚未提交')
    dialog.wait_for(state='hidden',timeout=15000)
