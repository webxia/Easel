"""Bilibili upload categories, read-only; no browsing tid_v2 translation."""
from pathlib import Path
import threading
import time
from easel.publication_bilibili import _native_builder
from skills.shared.scripts import platform_readback

_lock=threading.Lock()
_cache={}


def normalize_partitions(items):
    groups=[]
    if not isinstance(items,list):return groups
    for item in items:
        if not isinstance(item,dict) or item.get('show') is False:continue
        identity=item.get('id');name=item.get('name')
        if type(identity) is not int or identity<=0 or not isinstance(name,str) or not name.strip():continue
        groups.append({'id':identity,'name':name.strip(),
                       'children':normalize_partitions(item.get('children',[]))})
    return groups


def partitions(root, *, refresh=False):
    cookie=Path(root)/'cookies.json'
    try:stat=cookie.stat();version=(stat.st_mtime_ns,stat.st_size)
    except OSError:version=None
    key=(str(cookie.resolve()),version)
    with _lock:
        hit=_cache.get(key)
        if hit and not refresh and time.monotonic()-hit[0]<hit[1]:return hit[2]
        try:
            if version is None:raise OSError('no local login')
            result=platform_readback._bilibili_api(cookie,
                'https://member.bilibili.com/x/vupre/web/archive/pre',timeout_s=5)
            if result.get('code')!=0:raise ValueError('categories unavailable')
            groups=normalize_partitions((result.get('data') or {}).get('typelist'))
            if not groups:raise ValueError('empty categories')
            catalog={'groups':groups,'source':'bilibili','message':'来自B站当前投稿分区'}
            ttl=600
        except Exception:
            # Reuse Easel's native CLI list; never silently change a stored tid.
            common=_native_builder().__globals__['PARTITIONS']
            catalog={'groups':[{'id':v,'name':k,'children':[]} for k,v in common.items()],
                     'source':'local','message':'暂未同步B站，显示Easel本机常用分区；原选择保留，可刷新或手动填写。'}
            ttl=30
        _cache.clear()  # Do not retain catalogs for old login sessions.
        _cache[key]=(time.monotonic(),ttl,catalog)
        return catalog
