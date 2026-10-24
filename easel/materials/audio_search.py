"""Local bilingual audio metadata ranking; never claims to hear the recording."""
import re

# Phrase vocabulary, deliberately limited to recorded objects/actions. Unknown
# words retain lexical matching rather than being guessed by a model.
CONCEPTS = {
    'cup': (r'杯', r'\b(?:cups?|mugs?|glass(?:es)?)\b'),
    'door': (r'门', r'\bdoors?\b'),
    'keyboard': (r'键盘|打字', r'\bkeyboard\b|\btyping\b'),
    'air': (r'空调', r'\bair conditioner\b'),
    'ambience': (r'环境声|环境音|背景声', r'\bambien(?:ce|t)\b|\broom ?tone\b'),
    'place': (r'放下|轻放|放杯|放在|放到', r'\bset(?:ting)? down\b|\bput(?:ting)? down\b|\bplac(?:e|ed|ing)\b'),
    'open': (r'开门|打开|开启', r'\bopen(?:s|ed|ing)?\b'),
    'close': (r'关门|关闭|关上', r'\bclos(?:e|es|ed|ing)\b|\bshut\b'),
    'type': (r'打字|连续敲|连续按', r'\btyp(?:e|es|ed|ing)\b'),
    'single': (r'单键|单次按', r'\bsingle (?:hit|key)\b|\bspace bar\b'),
    'break': (r'破碎|打碎|碎玻璃', r'\bbreak(?:s|ing)?\b|\bbroken\b|\bshatter\w*\b'),
}
OBJECTS = {'cup', 'door', 'keyboard', 'air', 'ambience'}
ACTIONS = {'place', 'open', 'close', 'type', 'single', 'break'}

def concepts(text):
    text = re.sub(r'[_-]', ' ', text.casefold())
    return {key for key, patterns in CONCEPTS.items() if any(re.search(p, text) for p in patterns)}

def score_audio(query, caption, metadata):
    """Return None to use generic matching; zero explicitly rejects a mismatch."""
    requested = concepts(query)
    if not requested:
        return None
    # Prefer source caption for action identity: broad imported tags must not
    # turn a single keystroke into continuous typing.
    actual = concepts(caption or '')
    actual |= concepts(metadata) & OBJECTS
    if not actual:
        actual = concepts(metadata)
    if re.search(r'\b(?:bottles?|fragments?|debris)\b', caption.casefold()) and not re.search(r'\b(?:cups?|mugs?)\b', caption.casefold()):
        actual.discard('cup')
    objects, actions = requested & OBJECTS, requested & ACTIONS
    if objects and not objects.intersection(actual):
        return 0.0
    if actions and not actions.intersection(actual):
        return 0.0
    if 'break' in actions and re.search(r"does(?:n['’]t| not) break|not broken|不破|未破", caption.casefold()):
        return 0.0
    if 'type' in actions and 'single' in actual and 'type' not in actual:
        return 0.0
    # Exact action and object dominate generic shared words.
    base = 3 * len(objects & actual) + 5 * len(actions & actual)
    # A specific object name beats a multi-object recording; contextual words
    # improve ordering without claiming unrecorded acoustic properties.
    if 'cup' in objects and re.search(r'\b(?:box|crate|bottles?)\b', caption.casefold()):
        base -= 2
    context_words = {'卧室': 'bedroom', '房间': 'room', '木': 'wood', '笔记本': 'laptop'}
    base += sum(1 for cn, en in context_words.items() if cn in query and en in caption.casefold())
    words = set(re.findall(r'[a-z]+', query.casefold()))
    terms = set(re.findall(r'[a-z]+', caption.casefold()))
    return float(base) + len(words & terms) / max(1, len(words))
