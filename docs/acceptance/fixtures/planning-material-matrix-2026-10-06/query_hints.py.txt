"""Interpret known discovery transports without altering a Need or hard filters."""
import re

LEGACY_QUERY_FIELDS = tuple('search_query_variants_' + name for name in ('primary', 'alternate', 'relaxed'))
QUERY_FIELDS = frozenset({'search_query_en', 'search_query_variants_en', *LEGACY_QUERY_FIELDS})


def _query(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 100
            or not re.fullmatch(r'[\x20-\x7e]+', value) or not re.search(r'[a-zA-Z]', value)):
        raise ValueError('检索提示须为不超过100字符的英文短查询')
    return re.sub(r'\s+', ' ', value).strip()


def query_hints(constraints):
    single = _query(constraints['search_query_en']) if 'search_query_en' in constraints else None
    legacy = [_query(constraints[key]) for key in LEGACY_QUERY_FIELDS if key in constraints]
    if 'search_query_variants_en' in constraints:
        raw = constraints['search_query_variants_en']
        if not isinstance(raw, dict) or set(raw) != {'primary', 'alternate', 'relaxed'}:
            raise ValueError('英文查询变体须为primary/alternate/relaxed三项')
        variants = tuple(_query(raw[name]) for name in ('primary', 'alternate', 'relaxed'))
        if len({q.casefold() for q in variants}) != 3: raise ValueError('英文查询变体须为三个不同的短查询')
        return variants
    if legacy:
        seen, result = set(), []
        for query in legacy:
            if query.casefold() not in seen:
                seen.add(query.casefold()); result.append(query)
        return tuple(result)
    return (single,) if single else ()
