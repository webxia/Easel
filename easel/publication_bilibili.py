"""Thin boundary around Easel's existing biliup and platform_readback support."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from easel.production.service import fail
from skills.shared.scripts import platform_readback as readback


def biliup_command(cookie_file, video, content):
    # Reuse the native skill's pure command builder, not its CLI side effects
    # (calendar writes and content precheck belong to that independent entry).
    from types import SimpleNamespace
    builder = _native_builder()
    return builder(SimpleNamespace(cookie=str(cookie_file),video=str(video),
        title=content['title'],partition=None,tid=content['tid'],
        desc='\n\n'.join(s for s in (content['body'],content.get('credits','')) if s),
        tag=','.join(content['tags']),cover=None,copyright=content['copyright'],
        source=content['source']))


from functools import lru_cache
@lru_cache(maxsize=1)
def _native_builder():
    import importlib.util
    path=Path(__file__).resolve().parents[1]/'skills/builtin/skill-bilibili-upload/scripts/bili_upload.py'
    spec=importlib.util.spec_from_file_location('easel_native_bili_upload',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_cmd


@contextmanager
def publishing_lock(root):
    folder=Path(root)/'outputs'/'_publish'
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/'bilibili.lock').open('a+b') as lock:
        if os.name=='nt':
            import msvcrt
            if lock.tell()==0:lock.write(b'0');lock.flush()
            lock.seek(0)
            acquire=lambda:msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            release=lambda:msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            acquire=lambda:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            release=lambda:fcntl.flock(lock,fcntl.LOCK_UN)
        try:acquire()
        except OSError:fail('publication_busy','B站有正在执行的操作，请查看原记录',409)
        try:yield
        finally:release()


def legacy_bilibili_run(root, cmd, **kwargs):
    with publishing_lock(root):
        return subprocess.run(cmd,**kwargs)


class BilibiliAdapter:
    def __init__(self, root):
        self.root=Path(root)

    @staticmethod
    def validate(content, final=False):
        # These are existing CLI fields, not another content-review policy.
        if not isinstance(content.get('title'),str) or not 1<=len(content['title'].strip())<=80:
            fail('invalid_title','B站标题须为1～80字')
        if not isinstance(content.get('body'),str) or not isinstance(content.get('credits'),str) or len('\n\n'.join(s for s in (content['body'],content['credits']) if s))>2000:
            fail('invalid_description','正文与必须保留的素材署名合计不能超过2000字')
        tags=content.get('tags')
        if not isinstance(tags,list) or any(not isinstance(t,str) or not t.strip() or ',' in t for t in tags):
            fail('invalid_tags','请填写不含逗号的非空标签')
        if type(content.get('tid')) is not int or content['tid']<=0 or content.get('copyright') not in (1,2):
            fail('invalid_category','请确认投稿分区与自制/转载类型')
        if not isinstance(content.get('source'),str) or content['copyright']==2 and not content['source'].strip():
            fail('invalid_source','转载稿件必须填写来源')
        if content.get('action')!='submit':fail('invalid_action','本批仅支持B站投稿')
        account=content.get('account')
        if account is not None and (not isinstance(account,dict) or set(account)!={'platform','uid','name'} or account.get('platform')!='bilibili' or not isinstance(account.get('uid'),str) or not account['uid'] or not isinstance(account.get('name'),str)):
            fail('invalid_account','请选择实际登录的B站账号')
        if final and (not account or not tags):fail('missing_publication_fields','请读取实际登录账号并填写投稿标签')

    @contextmanager
    def session(self):
        with publishing_lock(self.root):
            # Snapshot credentials privately: login/logout during dispatch cannot
            # silently change the account used by the CLI. Never expose to API.
            with tempfile.TemporaryDirectory(prefix='easel-bili-') as temp:
                cookie=Path(temp)/'cookies.json'
                try:
                    data=(self.root/'cookies.json').read_bytes()
                    cookie.touch(mode=0o600)
                    cookie.write_bytes(data)
                except OSError:fail('login_required','请在账号页登录B站',409)
                yield BilibiliSession(self.root,cookie)

    def account(self):
        with self.session() as session:return session.account()


class BilibiliSession:
    def __init__(self,root,cookie):self.root,self.cookie=root,cookie

    def account(self):
        try:
            account=readback.read_bilibili_account(self.cookie)
            if not account.get('uid'):raise ValueError('missing uid')
            return {'platform':'bilibili','uid':str(account['uid']),'name':str(account.get('name') or '')}
        except readback.LoginRequiredError:fail('login_required','B站登录已失效，请重新登录',409)
        except Exception:fail('account_unavailable','无法核实B站账号，尚未投稿',503)

    def snapshot(self):
        if not shutil.which('biliup'):fail('publisher_unavailable','本机未安装原生 biliup 投稿工具，尚未投稿',503)
        # Unlike the legacy helper, errors cannot be converted to an empty list.
        try:return [w.platform_content_id for w in readback.read_bilibili_works(self.cookie,limit=50)]
        except Exception:fail('readback_unavailable','无法读取投稿前稿件列表，尚未投稿',503)

    def stage_video(self,path,expected_digest):
        import hashlib
        staged=self.cookie.parent/'video.mp4'
        checksum=hashlib.sha256()
        with Path(path).open('rb') as source, staged.open('xb') as target:
            for chunk in iter(lambda:source.read(1024*1024),b''):
                checksum.update(chunk);target.write(chunk)
        if checksum.hexdigest()!=expected_digest:fail('media_changed','复制时成片内容变化，尚未投稿',409)
        return staged

    def upload(self,path,content):
        env=dict(os.environ)
        for key in ('http_proxy','https_proxy','all_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'):env.pop(key,None)
        # No raw stdout/stderr (potential credentials) is returned or persisted.
        subprocess.run(biliup_command(self.cookie,path,content),cwd=self.root,env=env,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=600,check=False)

    def readback(self,content,snapshot,submitted_at,known_id=None):
        account=self.account()
        try:works=readback.read_bilibili_works(self.cookie,limit=50)
        except readback.LoginRequiredError:return {'outcome':'login_required','account':account}
        except Exception:return {'outcome':'readback_error','account':account}
        since=int(datetime.fromisoformat(submitted_at.replace('Z','+00:00')).timestamp()*1000)
        # Reuse the native records, but never accept prefix-only/ambiguous matches.
        matches=[w for w in works if w.platform_content_id not in snapshot and w.title==content['title']
                 and w.published_at_ms is not None and since-2000<=w.published_at_ms<=since+600_000]
        if known_id:matches=[w for w in works if w.platform_content_id==known_id]
        if len(matches)!=1:return {'outcome':'unverified','account':account,'candidate_count':len(matches)}
        item=matches[0]
        return {'outcome':'verified','account':account,'matched':item.as_dict(),
                'url':'https://www.bilibili.com/video/'+item.platform_content_id,
                'evidence':{'method':'unique_exact_title_time_and_snapshot','remote_bytes_verified':False}}
