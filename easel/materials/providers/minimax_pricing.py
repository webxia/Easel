"""Public domestic pay-as-you-go quotes; no credentials or generation calls."""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from urllib.request import Request, urlopen

PRICE_URL = "https://platform.minimaxi.com/docs/guides/pricing-paygo.md"
VOICE_URL = "https://platform.minimaxi.com/docs/faq/system-voice-id.md"


class GenerationQuoteUnavailable(ValueError):
    pass


class GenerationQuoteReadFailed(GenerationQuoteUnavailable):
    """A temporary public-document read failure; no paid request was submitted."""


def read_public_contract(url: str) -> str:
    if url not in {PRICE_URL, VOICE_URL}:
        raise GenerationQuoteUnavailable("费用依据地址不受支持")
    try:
        with urlopen(Request(url, headers={"User-Agent": "Easel/1"}), timeout=15) as response:
            if response.geturl() not in {url, url.replace('platform.minimaxi.com', 'platform.minimax.cn')}:
                raise GenerationQuoteUnavailable("费用依据地址已变化，不能自动认领报价")
            data = response.read(1_000_001)
        if len(data) > 1_000_000:
            raise GenerationQuoteUnavailable("费用依据内容超出可核验范围")
        return data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise GenerationQuoteReadFailed("暂时无法核实公开价格；未提交生成") from exc


def quote_generation(settings, *, modality: str, text: str = "", seconds: int = 0,
                     resolution: str = "", read=None) -> dict:
    """A conservative request estimate, never an account spending hard cap."""
    if settings.base_url.rstrip("/") not in {"https://api.minimax.cn", "https://api.minimaxi.com"}:
        raise GenerationQuoteUnavailable("当前账户区域没有已核实的人民币价格，不能自动换算")
    read = read or read_public_contract
    model = getattr(settings, {"voice": "speech_model", "image": "image_model", "video": "video_model"}[modality])
    document = read(PRICE_URL)
    section_name = {'voice': '语音', 'image': '图像', 'video': '视频'}[modality]
    section_text = re.search(r'^## ' + section_name + r'\s*\n(.*?)(?=^## |\Z)', document, re.M | re.S)
    unit_label = {'voice': '元/万字符', 'image': '元/张', 'video': '元/秒'}[modality]
    if not section_text or unit_label not in section_text[1]:
        raise GenerationQuoteUnavailable('当前币种或计价单位无法核实；未提交生成')
    section, subsection, prices = "", "", set()
    for line in document.splitlines():
        if line.startswith("## "):
            section, subsection = line[3:].strip(), ""
        elif line.startswith("**"):
            subsection = line.strip("*")
        if not line.startswith("|"):
            continue
        cells = [re.sub(r"[*`]", "", re.sub(r"<[^>]+>", " ", c)).strip() for c in line.strip("|").split("|")]
        if modality == "voice" and section == "语音" and len(cells) >= 3 and cells[0].startswith('同步'):
            if any(model in re.split(r"\s*/\s*", c) for c in cells):
                value = cells[-1]
            else:
                continue
        elif modality == "image" and section == "图像" and cells and model in cells[0].split():
            value = cells[-1]
        elif (modality == "video" and section == "视频" and subsection == "视频生成-输出价格"
              and len(cells) == 4 and cells[0] == model and cells[1] == resolution
              and cells[2] == "按秒计费"):
            value = cells[-1].removesuffix(" 元/秒")
        else:
            continue
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
            prices.add(Decimal(value))
    if len(prices) != 1 or next(iter(prices)) <= 0:
        raise GenerationQuoteUnavailable("当前模型/规格没有唯一可核实单价；未提交生成")
    unit = prices.pop()
    evidence = [{"url": PRICE_URL, "sha256": hashlib.sha256(document.encode()).hexdigest()}]
    if modality == "voice":
        if "1 个汉字算 2 个字符" not in document or not text:
            raise GenerationQuoteUnavailable("当前语音字符计费规则尚未核实")
        voices = read(VOICE_URL)
        if not any(f"`{settings.speech_voice_id}`" in line and line.startswith("|") for line in voices.splitlines()):
            raise GenerationQuoteUnavailable("当前音色未核实为系统音色，可能含首次使用费用；未提交生成")
        evidence.append({"url": VOICE_URL, "sha256": hashlib.sha256(voices.encode()).hexdigest()})
        # Each Unicode scalar is charged at most two characters under this
        # contract; counting every scalar twice deliberately overestimates.
        quantity, divisor, basis = 2 * len(text), Decimal(10000), "计费字符上界（每个字符按 2 计）"
    elif modality == "video":
        if not 5 <= seconds <= 15:
            raise GenerationQuoteUnavailable("视频时长不在已核实的请求规格内")
        quantity, divisor, basis = seconds, Decimal(1), "输出秒数；纯文本输入"
    else:
        quantity, divisor, basis = 1, Decimal(1), "图片张数"
    amount = (unit * quantity / divisor).quantize(Decimal("0.000001"), rounding=ROUND_CEILING)
    return {"currency": "CNY", "upper_estimate": str(amount), "unit_price": str(unit),
            "quantity": quantity, "basis": basis, "provider": "minimax", "model": model,
            "quoted_at": datetime.now(timezone.utc).isoformat(), "evidence": evidence}
