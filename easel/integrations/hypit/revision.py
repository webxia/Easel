"""Protect accepted sound and copy during composition-only authoring."""

from __future__ import annotations

import re
import math
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

from easel.integrations.hypit.errors import HypitIntegrationError


def _markup(source: Path):
    text = source.read_text(encoding="utf-8")
    # SVML uses typed, unquoted references and package-qualified element names.
    text = re.sub(r'=\{([^}]+)\}', lambda m: '="{' + m[1] + '}"', text)
    text = re.sub(r'(<\/?)([\w.-]+):([\w.-]+)', r'\1\2__\3', text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise HypitIntegrationError("局部修改产物无法读取；未改变已保留的成片") from exc
    return root


def _recipe_properties(sheet: Path, selector: str) -> dict[str, str]:
    """Read top-level SVS properties without confusing JSON or strings for trims.

    Hypit's static checker still owns the language and consumer vocabulary.
    """
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|[{};]|[^"\'{};/]+|.',
                        sheet.read_text(), re.DOTALL)
    depth, rule, statement, properties = 0, '', '', {}
    for token in tokens:
        if token.startswith(('/*', '//')):
            statement += ' '
            continue
        if token == '{':
            if depth == 0:
                name = re.search(r'([\w.-]+)\s*$', statement)
                rule, statement, properties = name[1] if name else '', '', {}
            else:
                statement += token
            depth += 1
        elif token == '}':
            depth -= 1
            if depth == 0:
                if rule == selector:
                    return properties
                statement = ''
            else:
                statement += token
        elif token == ';' and depth == 1:
            pair = re.fullmatch(r'\s*([\w-]+)\s*:\s*(.*?)\s*', statement, re.DOTALL)
            if pair:
                if pair[1] in properties:
                    raise HypitIntegrationError('编排样式属性重复，无法核对取片或受保护部分')
                properties[pair[1]] = pair[2]
            statement = ''
        else:
            statement += token
    raise HypitIntegrationError('受保护的本地样式无法读取')


def _protected_graph(source: Path) -> tuple:
    root = _markup(source)
    packages = {e.get("as"): e.get("from", "").split("@")[1]
                for e in root.findall("import") if e.get("from", "").startswith("@hypit/")}
    nodes = {e.get("id"): e for e in root.iter() if e.get("id")}

    def kind(e):
        prefix, _, name = e.tag.partition("__")
        return packages.get(prefix, prefix), name

    def canonical(e):
        return (kind(e), tuple(sorted(e.attrib.items())), (e.text or "").strip(),
                tuple(canonical(c) for c in e))

    # Sound includes its source, normalization and timeline dependencies. Copy
    # includes text, placement and schedule. Visual media items remain editable.
    seeds = [e for e in root if kind(e)[0] in {
        "hypit/audio-track", "hypit/text", "hypit/typography-track",
    }]
    protected = {}

    def visit(e):
        key = e.get("id") or repr(kind(e))
        if key in protected:
            return
        protected[key] = canonical(e)
        for child in e.iter():
            for value in child.attrib.values():
                for ref in re.findall(r'\{([\w-]+)(?:\.[\w.-]+)?\}', value):
                    if ref in nodes:
                        visit(nodes[ref])

    for seed in seeds:
        visit(seed)
    return tuple(sorted(protected.items()))


def assert_composition_preserves_sound_and_copy(base: Path, authored: Path) -> None:
    """Fail closed before promotion; changing IDs is not a composition edit."""
    if _protected_graph(base) != _protected_graph(authored):
        raise HypitIntegrationError(
            "局部画面修改改变了已确认的声音、字幕或时序；请保留原组件及引用，"
            "只修改反馈涉及的画面取景与转场，不重写其他内容"
        )


def _quality_protected_dependencies(base: Path) -> set[str]:
    base_root = _markup(base)
    base_nodes = {e.get('id'): e for e in base_root.iter() if e.get('id')}
    # A Video can feed sound as well as pictures. Even an admitted visual
    # alternative may not replace any source on the protected sound/copy graph.
    sound_copy_ids = set(dict(_protected_graph(base)))
    packages = {e.get('as'): e.get('from', '').rsplit('@', 1)[0] for e in base_root.findall('import')}
    def protect_sources(element):
        for child in element.iter():
            for value in child.attrib.values():
                for ref in re.findall(r'\{([\w.-]+)\}', value):
                    identity = next((key for key in sorted(base_nodes, key=len, reverse=True)
                                     if ref == key or ref.startswith(key + '.')), None)
                    if identity is not None and identity not in sound_copy_ids:
                        sound_copy_ids.add(identity)
                        protect_sources(base_nodes[identity])
    for element in base_root.iter():
        prefix, _, name = element.tag.partition('__')
        if (packages.get(prefix) == '@hypit/media-track'
                and (element.get('source-audio') is not None or name == 'Sound')):
            protect_sources(element)
    return sound_copy_ids


def quality_protected_sources(base: Path) -> set[str]:
    dependencies = _quality_protected_dependencies(base)
    return {e.get('src') for e in _markup(base).iter() if e.get('id') in dependencies and e.get('src')}


def assert_quality_revision(base: Path, authored: Path, allowed: set[str], *,
                            replacements: dict[str, dict[str, dict]] | None = None) -> None:
    """Permit scoped visual alternatives; preserve sound, copy and schedule."""
    if not allowed or not allowed <= {'visual', 'visual_material', 'captions', 'audio'}:
        raise HypitIntegrationError('系统质量修正范围无效')
    if 'visual_material' in allowed and 'visual' not in allowed:
        raise HypitIntegrationError('系统视觉素材修正需要对应画面缺陷')
    if expression_uses(base) != expression_uses(authored):
        raise HypitIntegrationError('系统质量修正改变了未授权部分：必要表达承担项或时间窗')
    base_root = _markup(base)
    base_nodes = {e.get('id'): e for e in base_root.iter() if e.get('id')}
    sound_copy_ids = _quality_protected_dependencies(base) if 'visual_material' in allowed else set()

    def graph(path: Path):
        root = _markup(path)
        packages = {e.get('as'): e.get('from', '').rsplit('@', 1)[0] for e in root.findall('import')}
        sheets = {e.get('as'): e.get('source') for e in root.findall('import') if e.get('source')}
        nodes = {e.get('id'): e for e in root.iter() if e.get('id')}
        protected = {'imports': tuple(sorted(tuple(sorted(e.attrib.items())) for e in root.findall('import')))}

        def kind(e):
            prefix, _, name = e.tag.partition('__')
            return packages.get(prefix, prefix), name

        changed, extents = {}, {}
        if 'visual_material' in allowed:
            for identity, node in nodes.items():
                old = base_nodes.get(identity)
                if (old is None or identity in sound_copy_ids or kind(node) != kind(old)
                        or kind(node) not in {('@hypit/media', 'Image'), ('@hypit/media', 'Video')}
                        or old.get('src') == node.get('src')):
                    continue
                candidate = (replacements or {}).get(old.get('src'), {}).get(node.get('src'))
                if candidate and candidate.get('media_type') == kind(node)[1].lower():
                    changed[identity] = candidate
            for identity, node in nodes.items():
                if kind(node) != ('@hypit/spatial', 'Extent') or identity in sound_copy_ids:
                    continue
                old = base_nodes.get(identity)
                users = [e for e in base_root.iter() if e.get('extent') == '{' + identity + '}']
                image_users = {('@hypit/media-track', name) for name in ('Item', 'Member', 'Layer')}
                images = {e.get('image', '')[1:-1] for e in users
                          if kind(e) in image_users}
                if old is None or not users or len(users) != sum(
                        kind(e) in image_users for e in users) or not images <= changed.keys():
                    continue
                if all(node.get('width') == str(changed[i]['width'])
                       and node.get('height') == str(changed[i]['height']) for i in images):
                    extents[identity] = old

        def filtered(e):
            package, name = kind(e)
            omitted = set()
            if 'audio' in allowed and (package, name) == ('@hypit/audio-track', 'Item'):
                omitted = {'gain', 'fade-in', 'fade-out'}
            if 'captions' in allowed and (package, name) == ('@hypit/typography-track', 'Area'):
                omitted = {'placement', 'style'}
            if 'visual' in allowed and package == '@hypit/media-track':
                omitted = {'frame', 'appearance', 'transition'}
            if 'visual' in allowed and (package, name) == ('@hypit/film', 'Film'):
                omitted = {'appearance'}
            children = [c for c in e if not ('visual' in allowed and kind(c) == ('@hypit/media-track', 'Sampling'))]
            attrs = {k: v for k, v in e.attrib.items() if k not in omitted}
            if e.get('id') in changed:
                attrs['src'] = base_nodes[e.get('id')].get('src')
            if e.get('id') in extents:
                for dimension in ('width', 'height'):
                    attrs[dimension] = extents[e.get('id')].get(dimension)
            return attrs, children

        def canonical(e):
            attrs, children = filtered(e)
            return kind(e), tuple(sorted(attrs.items())), (e.text or '').strip(), tuple(canonical(c) for c in children)

        def visit(e):
            key = e.get('id') or repr(kind(e))
            if key in protected:
                return
            protected[key] = canonical(e)

            def references(item):
                attrs, children = filtered(item)
                for value in attrs.values():
                    for ref in re.findall(r'\{([\w.-]+)\}', value):
                        identity = next((key for key in sorted(nodes, key=len, reverse=True)
                                         if ref == key or ref.startswith(key + '.')), None)
                        node = nodes.get(identity)
                        if node is not None:
                            visit(node)
                            continue
                        alias, _, selector = ref.partition('.')
                        if alias in sheets:
                            sheet = path.parent / sheets[alias]
                            if sheet.is_symlink() or sheet.resolve().parent != path.parent.resolve():
                                raise HypitIntegrationError('局部修正样式引用越界')
                            protected['recipe:' + ref] = tuple(sorted(_recipe_properties(sheet, selector).items()))
                for child in children:
                    references(child)

            references(e)

        roots = {'@hypit/media', '@hypit/media-pipeline', '@hypit/timeline-author', '@hypit/text',
                 '@hypit/audio-track', '@hypit/media-track', '@hypit/film', '@hypit/render-hyperframes', '@easel/audio-mix'}
        for element in root:
            package, name = kind(element)
            if package in roots or (package, name) in {('@hypit/spatial', 'Canvas'), ('@hypit/typography-track', 'Track')}:
                visit(element)
        return protected

    if graph(base) != graph(authored):
        raise HypitIntegrationError('系统局部修正改变了脚本、素材身份、播放时序或未授权部分；只修正审片指出的表现层缺陷')


def assert_observed_video_uses(authored: Path, assets: list[dict]) -> None:
    """Bind per-Need sampled evidence to the source range actually put in Film."""
    bounded = {a['src']: a for a in assets if a.get('observed_video_uses')}
    if not bounded:
        return
    root = _markup(authored)
    packages = {e.get('as'): e.get('from', '').rsplit('@', 1)[0] for e in root.findall('import')}
    sheets = {e.get('as'): e.get('source') for e in root.findall('import') if e.get('source')}
    nodes = {e.get('id'): e for e in root.iter() if e.get('id')}
    parents = {child: parent for parent in root.iter() for child in parent}
    if len(nodes) != sum(bool(e.get('id')) for e in root.iter()):
        raise HypitIntegrationError('镜头标识重复，无法核对场景与取片范围')

    def kind(e):
        prefix, _, name = e.tag.partition('__')
        return packages.get(prefix, prefix), name

    def reference(value):
        match = re.fullmatch(r'\{([\w.-]+)\}', value or '')
        if match:
            key = next((k for k in sorted(nodes, key=len, reverse=True)
                        if match[1] == k or match[1].startswith(k + '.')), None)
            return nodes.get(key)
        return None

    films = [e for e in root if kind(e) == ('@hypit/film', 'Film')]
    if len(films) != 1:
        raise HypitIntegrationError('当前区间编排需要唯一 Film，不能从未使用的镜头认领场景')
    film = films[0]
    if not any(kind(e) == ('@hypit/render-hyperframes', 'Video')
               and reference(e.get('composition')) is film for e in root):
        raise HypitIntegrationError('场景区间未关联到原生视频输出')
    film_tracks = {reference(e.get('source')) for e in film if kind(e) == ('@hypit/film', 'Track')}

    def uses_bounded_source(node, seen=None):
        if node is None:
            return False
        seen = set() if seen is None else seen
        if node in seen:
            return False
        seen.add(node)
        return node.get('src') in bounded or any(
            uses_bounded_source(reference(value), seen)
            for child in node.iter() for value in child.attrib.values())

    for track in film_tracks:
        if track is not None and kind(track)[0] not in {'@hypit/media-track', '@hypit/audio-track', '@easel/audio-mix'} and uses_bounded_source(track):
            raise HypitIntegrationError('已观察的视频区间需通过原生 media-track 使用，当前轨道无法核对源区间')
    covered = set()
    for sample in root.iter():
        if kind(sample) not in {('@hypit/media-track', k) for k in ('Item', 'Member', 'Layer')}:
            continue
        item = sample
        while kind(item) == ('@hypit/media-track', 'Layer'):
            item = parents[item]
        track = item
        while track in parents and kind(track) != ('@hypit/media-track', 'Track'):
            track = parents[track]
        if track not in film_tracks:
            continue
        normalized = reference(sample.get('media'))
        if normalized is None or kind(normalized) != ('@hypit/media-pipeline', 'Normalize'):
            if uses_bounded_source(normalized):
                raise HypitIntegrationError('观察区间不能经过未核对的中间变换；请直接使用素材 Normalize 并在镜头 recipe 中取片')
            continue
        media = reference(normalized.get('source'))
        if media is None or media.get('src') not in bounded:
            if uses_bounded_source(media):
                raise HypitIntegrationError('观察区间不能经过未核对的中间变换；请直接使用原素材 Normalize')
            continue
        asset = bounded[media.get('src')]
        uses = [u for u in asset['observed_video_uses'] if item.get('id', '').startswith(u['element_id_prefix'])]
        if len(uses) != 1:
            raise HypitIntegrationError('视频镜头必须使用提供的场景标识前缀，不能借另一场景的素材证据')
        clock = reference(normalized.get('clock'))
        if clock is None:
            raise HypitIntegrationError('取片范围缺少实际 Normalize 的 Clock')
        rate = Fraction(clock.get('frame-rate', '0'))
        if rate <= 0:
            raise HypitIntegrationError('取片帧率无效')
        recipe_owner = sample
        while not recipe_owner.get('appearance') and recipe_owner in parents:
            recipe_owner = parents[recipe_owner]
        recipe = re.fullmatch(r'\{([\w-]+)\.([\w.-]+)\}', recipe_owner.get('appearance', ''))
        if not recipe or recipe[1] not in sheets:
            raise HypitIntegrationError('视频区间必须使用可核验的本地 appearance recipe')
        sheet = authored.parent / sheets[recipe[1]]
        if sheet.is_symlink() or sheet.resolve().parent != authored.parent.resolve():
            raise HypitIntegrationError('视频区间样式引用越界')
        props = _recipe_properties(sheet, recipe[2])
        duration = Fraction(str(asset['source_duration_seconds']))
        total = math.floor(duration * rate + Fraction(1, 2))
        try:
            start, end = int(props.get('trim-start', '0')), int(props.get('trim-end', str(total)))
        except ValueError as exc:
            raise HypitIntegrationError('取片起止必须使用当前 Clock 下的整数帧') from exc
        left, right = map(lambda v: Fraction(str(v)), uses[0]['source_interval_seconds'])
        limit = total if right == duration else math.floor(right * rate)
        first = math.ceil(left * rate)
        if not (first <= start < end <= limit):
            raise HypitIntegrationError(
                '实际取片越过该场景已观察的相关区间；保留素材，修正该镜头截取。'
                f'场景 {uses[0]["need_id"]}，镜头 {item.get("id")}，'
                f'appearance={recipe[1]}.{recipe[2]}，Normalize Clock={rate} fps；'
                f'允许整数帧 {first} <= trim-start < trim-end <= {limit}，'
                f'实际 trim-start={start} / trim-end={end}。只修正该镜头 recipe。'
            )
        covered.add(uses[0]['need_id'])
    required = {u['need_id'] for a in bounded.values() for u in a['observed_video_uses'] if u['required']}
    if required - covered:
        raise HypitIntegrationError('必要视频场景尚未使用其已观察区间，不能只声明素材而不放入成片')


def assert_video_trim_ranges(authored: Path, assets: dict[str, float]) -> None:
    """Preflight literal media-track trims against the admitted video duration.

    Hypit 0.2.7 NormalizationPlan rounds video span * target Clock rate; trims
    index that normalized source, not the original codec rate or the Film end.
    Hypit still owns static validation and exact execution-time media admission.
    """
    root = _markup(authored)
    aliases = {e.get("as"): e.get("from", "").split("@")[1]
               for e in root.findall("import") if e.get("from", "").startswith("@hypit/")}
    nodes = {e.get("id"): e for e in root.iter() if e.get("id")}
    sheets = {e.get("as"): e.get("source") for e in root.findall("import") if e.get("source")}

    def kind(e):
        prefix, _, name = e.tag.partition("__")
        return aliases.get(prefix), name

    def reference(value):
        match = re.fullmatch(r'\{([\w-]+)(?:\.[\w.-]+)?\}', value or "")
        return nodes.get(match[1]) if match else None

    for item in root.iter():
        if kind(item) != ("hypit/media-track", "Item"):
            continue
        recipe = re.fullmatch(r'\{([\w-]+)\.([\w.-]+)\}', item.get("appearance", ""))
        if not recipe or recipe[1] not in sheets:
            continue
        sheet = authored.parent / sheets[recipe[1]]
        if sheet.is_symlink() or sheet.resolve().parent != authored.parent.resolve():
            raise HypitIntegrationError("画面截取样式必须来自当前已核验的本地编排文件")
        properties = _recipe_properties(sheet, recipe[2])
        if not any(key in properties for key in ("trim-start", "trim-end")):
            continue
        try:
            start, end = (int(properties[key]) for key in ("trim-start", "trim-end"))
        except (KeyError, ValueError) as exc:
            raise HypitIntegrationError("画面截取起止必须成对使用整数帧；请按当前 Clock 换算") from exc
        normalized = reference(item.get("media"))
        if normalized is None or kind(normalized) != ("hypit/media-pipeline", "Normalize"):
            raise HypitIntegrationError("画面截取缺少可核验的标准化视频来源")
        video = reference(normalized.get("source"))
        clock = reference(normalized.get("clock"))
        if video is None or clock is None or video.get("src") not in assets:
            raise HypitIntegrationError("画面截取缺少已检查的原片时长或 Clock")
        try:
            rate = float(Fraction(clock.get("frame-rate", "")))
            duration = assets[video.get("src")]
            frames = math.floor(duration * rate + 0.5)
        except (ValueError, ZeroDivisionError, OverflowError) as exc:
            raise HypitIntegrationError("画面截取的时长或帧率无法核验") from exc
        if not (math.isfinite(rate) and rate > 0 and 0 <= start < end <= frames):
            raise HypitIntegrationError(
                f"画面截取 {start}～{end} 帧超出原片范围（约 {duration:g} 秒，"
                f"标准化帧率 {rate:g} fps，{frames} 帧）。"
                "秒转帧必须使用该 Normalize 的 Clock；只修正此镜头截取，保留声音、字幕和素材"
            )


def expression_uses(source: Path, *, required_need_ids: set[str] | None = None) -> list[dict]:
    """Bind directing commitments to visible native graph nodes and windows.

    This establishes authored coverage, not semantic correctness of the picture;
    the encoded output still has to be reviewed against the frozen intent.
    """
    import json
    text = source.read_text(encoding='utf-8')
    rows = []
    for raw in re.findall(r'<!-- Easel expression: (.*?) -->', text):
        try:
            row = json.loads(raw)
        except ValueError as exc:
            raise HypitIntegrationError('必要表达编排记录不是有效 JSON') from exc
        if (not isinstance(row, dict) or set(row) != {'need_id', 'element_ids', 'at_seconds', 'end_seconds', 'responsibility'}
                or not isinstance(row['need_id'], str) or not row['need_id']
                or not isinstance(row['element_ids'], list) or not row['element_ids']
                or any(not isinstance(v, str) or not v for v in row['element_ids'])
                or row['responsibility'] not in {'material', 'graphic', 'combined'}
                or any(type(row[k]) not in (int, float) or not math.isfinite(row[k]) for k in ('at_seconds', 'end_seconds'))
                or not 0 <= row['at_seconds'] < row['end_seconds']):
            raise HypitIntegrationError('必要表达须明确 Need、实际元素、承担方式和有效时间窗')
        rows.append(row)
    if not rows and required_need_ids is None:
        return []
    if len({r['need_id'] for r in rows}) != len(rows):
        raise HypitIntegrationError('必要表达记录存在重复 Need')
    if required_need_ids is not None and {r['need_id'] for r in rows} != required_need_ids:
        raise HypitIntegrationError('必要表达编排未完整覆盖当前 required 视觉 Need')
    root = _markup(source)
    packages = {e.get('as'): e.get('from', '').rsplit('@', 1)[0] for e in root.findall('import')}
    nodes = {e.get('id'): e for e in root.iter() if e.get('id')}
    film = next((e for e in root.iter() if packages.get(e.tag.partition('__')[0]) == '@hypit/film'
                 and e.tag.endswith('__Film')), None)
    reachable = set()
    def visit(e):
        for child in e.iter():
            if child.get('id'):
                reachable.add(child.get('id'))
            for value in child.attrib.values():
                for ref in re.findall(r'\{([\w.-]+)\}', value):
                    identity = next((v for v in sorted(nodes, key=len, reverse=True)
                                     if ref == v or ref.startswith(v + '.')), None)
                    if identity and identity not in reachable:
                        reachable.add(identity)
                        visit(nodes[identity])
    if film is None:
        raise HypitIntegrationError('必要表达缺少实际 Film')
    visit(film)
    from .narration import _frames
    timeline = next((e for e in root.iter() if e.tag.endswith('__Timeline')), None)
    clock = nodes.get((timeline.get('clock', '') if timeline is not None else '').strip('{}'))
    if timeline is None or clock is None:
        raise HypitIntegrationError('必要表达缺少有效时间线与 Clock')
    fps = Fraction(clock.get('frame-rate', '0'))
    duration = float(_frames(timeline.get('end', ''), fps) / fps)
    parents = {child: parent for parent in root.iter() for child in parent}
    for row in rows:
        if row['end_seconds'] > duration:
            raise HypitIntegrationError('必要表达时间窗越过实际 Timeline')
        if any(v not in reachable for v in row['element_ids']):
            raise HypitIntegrationError(f"必要表达 {row['need_id']} 引用的元素未进入 Film")
        visible = [nodes[v] for v in row['element_ids']]
        for e in visible:
            if e.get('during') == 'program':
                left, right = 0., duration
            else:
                left = float(_frames(e.get('at', '0f'), fps) / fps)
                if e.get('for'):
                    right = left + float(_frames(e.get('for'), fps) / fps)
                elif e.tag.endswith('__Member'):
                    parent = parents[e]
                    siblings = list(parent)
                    next_member = next((v for v in siblings[siblings.index(e) + 1:] if v.tag.endswith('__Member')), None)
                    end_value = next_member.get('at') if next_member is not None else parent.get('until')
                    if end_value is None:
                        raise HypitIntegrationError('必要表达 Member 缺少可核对的结束窗')
                    right = float(_frames(end_value, fps) / fps)
                else:
                    raise HypitIntegrationError('必要表达元素需要明确 at/for 或 Member 窗口')
            if row['at_seconds'] < left - 1e-6 or row['end_seconds'] > right + 1e-6:
                raise HypitIntegrationError('必要表达记录与实际图层播放窗口不一致')
        if row['responsibility'] in {'graphic', 'combined'} and not any(
                packages.get(e.tag.partition('__')[0]) == '@hypit/typography-track' and e.tag.endswith('__Area')
                and not e.get('id', '').startswith('easel-caption-') for e in visible):
            raise HypitIntegrationError('文字/图形承担的表达需要实际独立文字 Area，普通旁白字幕不能代替')
        if any((packages.get(e.tag.partition('__')[0]), e.tag.partition('__')[2]) not in
               {('@hypit/media-track', 'Item'), ('@hypit/media-track', 'Member'), ('@hypit/typography-track', 'Area')}
               for e in visible):
            raise HypitIntegrationError('必要表达应绑定实际画面 Item/Member 或文字 Area')
    return rows
