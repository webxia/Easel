"""Thin boundary around Easel's existing biliup and platform_readback support."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import os
import json
import re
import time
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from easel.production.service import fail
from skills.shared.scripts import platform_readback as readback


def biliup_command(cookie_file, video, content, cover_path=None):
    # Reuse the native skill's pure command builder, not its CLI side effects
    # (calendar writes and content precheck belong to that independent entry).
    from types import SimpleNamespace
    builder = _native_builder()
    command=builder(SimpleNamespace(cookie=str(cookie_file),video=str(video),
        title=content['title'],partition=None,tid=content['tid'],
        desc='\n\n'.join(s for s in (content['body'],content.get('credits','')) if s),
        tag=','.join(content['tags']),cover=str(cover_path) if cover_path else None,copyright=content['copyright'],
        source=content['source']))
    return upload_route(command)


def upload_route(command):
    # Use the installed CLI's existing route override when the deployment has
    # diagnosed an unavailable automatic route. Never disable TLS verification.
    line=os.environ.get('EASEL_BILIBILI_UPLOAD_LINE','').strip()
    if line and '--line' not in command and '-l' not in command:
        if line not in {'bldsa','cnbldsa','andsa','atdsa','bda2','cnbd','anbd','atbd','tx','cntx','antx','attx','txa','alia','estx','akbd'}:
            fail('invalid_upload_line','B站上传线路配置无效，尚未上传',503)
        command.extend(['--line',line])
    return command


def cli_evidence(tail):
    """Allowlisted CLI evidence; never return raw errors, URLs or credentials."""
    clean=re.sub(r'\x1b\[[0-9;]*[A-Za-z]','',tail)
    result={}
    stages=(('number of concurrent futures:','upload_preparing'),
            ('pre_upload:','pre_upload'),('Upload completed:','upload_complete'),
            ('All files uploaded successfully','upload_complete'),
            ('APP接口投稿成功','submit_acknowledged'),('Web 接口投稿成功','submit_acknowledged'))
    found=[(clean.rfind(marker),stage) for marker,stage in stages if marker in clean]
    if found:result['last_stage']=max(found)[1]
    categories={'tls_error':('certificate verify failed','invalid peer certificate','certificate error','tls handshake'),
                'certificate_expired':('证书已过期','certificate has expired','certificate expired'),
                'network_timeout':('timed out','operation timeout'),
                'connection_error':('connection refused','connection reset','error sending request'),
                'dns_error':('dns error','failed to lookup address')}
    errors=[name for name,markers in categories.items() if any(m in clean.lower() for m in markers)]
    if errors:result['error_kinds']=errors
    codes=[]
    decoder=json.JSONDecoder()
    for line in clean.splitlines():
        # The installed CLI serializes ResponseData using Rust Debug, not JSON.
        if 'ResponseData {' in line:
            code=re.search(r'\bcode:\s*(-?\d+)\b',line)
            if code:codes.append(int(code[1]))
            remote=re.search(r'"bvid":\s*(?:String\()?"(BV[0-9A-Za-z]{10})"',line)
            if code and int(code[1])==0 and remote:result['remote_id']=remote[1]
        # tracing prefixes its JSON response with timestamp/level/module.
        offset=line.find('{')
        if offset<0:continue
        try:payload,_=decoder.raw_decode(line[offset:])
        except ValueError:continue
        if not isinstance(payload,dict):continue
        code=payload.get('code')
        if type(code) is int:codes.append(code)
        data=payload.get('data')
        remote=data.get('bvid') if isinstance(data,dict) else None
        if code==0 and isinstance(remote,str) and re.fullmatch(r'BV[0-9A-Za-z]{10}',remote):result['remote_id']=remote
    if codes:result['response_codes']=list(dict.fromkeys(codes))
    return result


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
def publishing_lock(root, platform="bilibili"):
    folder=Path(root)/'outputs'/'_publish'
    folder.mkdir(parents=True,exist_ok=True)
    if platform not in {'bilibili','xiaohongshu','douyin','kuaishou','weixin-channels','zhihu','wechat-oa'}:
        fail('invalid_platform','未知发布平台')
    with (folder/(platform+'.lock')).open('a+b') as lock:
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
        except OSError:fail('publication_busy','该平台有正在执行的操作，请查看原记录',409)
        try:yield
        finally:release()


def legacy_bilibili_run(root, cmd, **kwargs):
    with publishing_lock(root):
        if cmd and cmd[0]=='biliup':cmd=[BilibiliSession.publisher(),*cmd[1:]]
        if 'upload' in cmd:cmd=upload_route(list(cmd))
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
    def __init__(self,root,cookie):
        self.root,self.cookie=root,cookie
        self.executable=None

    @staticmethod
    def publisher():
        # LaunchAgent's PATH need not include the active virtual environment.
        # Prefer its installed console script before consulting global PATH.
        local=Path(sys.executable).parent/('biliup.exe' if os.name=='nt' else 'biliup')
        if local.is_file() and os.access(local,os.X_OK):return str(local)
        found=shutil.which('biliup')
        if not found:fail('publisher_unavailable','当前运行环境找不到已安装的 biliup 投稿工具，尚未投稿',503)
        return found

    def account(self):
        try:
            account=readback.read_bilibili_account(self.cookie)
            if not account.get('uid'):raise ValueError('missing uid')
            return {'platform':'bilibili','uid':str(account['uid']),'name':str(account.get('name') or '')}
        except readback.LoginRequiredError:fail('login_required','B站登录已失效，请重新登录',409)
        except Exception:fail('account_unavailable','无法核实B站账号，尚未投稿',503)

    def snapshot(self):
        self.executable=self.publisher()
        # Unlike the legacy helper, errors cannot be converted to an empty list.
        try:return [w.platform_content_id for w in readback.read_bilibili_works(self.cookie,limit=50)]
        except Exception:fail('readback_unavailable','无法读取投稿前稿件列表，尚未投稿',503)

    def stage_video(self,path,expected_digest):
        return self._stage_file(path,expected_digest,'video.mp4')

    def stage_cover(self,path,expected_digest):
        self.cover_path=self._stage_file(path,expected_digest,'cover.jpg')
        return self.cover_path

    def _stage_file(self,path,expected_digest,name):
        import hashlib
        staged=self.cookie.parent/name
        checksum=hashlib.sha256()
        with Path(path).open('rb') as source, staged.open('xb') as target:
            for chunk in iter(lambda:source.read(1024*1024),b''):
                checksum.update(chunk);target.write(chunk)
        if checksum.hexdigest()!=expected_digest:fail('media_changed','复制时成片内容变化，尚未投稿',409)
        return staged

    def upload(self,path,content):
        env=dict(os.environ)
        for key in ('http_proxy','https_proxy','all_proxy','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY'):env.pop(key,None)
        env['RUST_LOG']='info'
        # No raw stdout/stderr (potential credentials) is returned or persisted.
        command=biliup_command(self.cookie,path,content)
        if content.get('cover') is not None:
            if not getattr(self,'cover_path',None):fail('cover_changed','封面尚未准备，未投稿',409)
            command=biliup_command(self.cookie,path,content,self.cover_path)
        command[0]=self.executable or self.publisher()
        started=time.monotonic()
        # Keep raw CLI output only in an anonymous temporary file. Persist a
        # small allowlisted receipt, never command arguments, cookies or logs.
        with tempfile.TemporaryFile() as log:
            try:
                # biliup also writes download.log into cwd. Keep it inside the
                # credential session's private temporary directory, not the repo.
                process=subprocess.run(command,cwd=self.cookie.parent,env=env,
                    stdout=log,stderr=subprocess.STDOUT,timeout=600,check=False)
                result={'returncode':process.returncode,'timed_out':False}
            except subprocess.TimeoutExpired:
                result={'returncode':None,'timed_out':True}
            log.seek(0,2);size=log.tell();log.seek(max(0,size-65536))
            tail=log.read().decode('utf-8',errors='replace')
        result.update(duration_ms=round((time.monotonic()-started)*1000),
                      phase='process_finished',output_captured=True)
        result.update(cli_evidence(tail))
        # Exit success is NOT proof of remote submission; readback owns that.
        return result

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
