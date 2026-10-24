"""Connect accepted media to Easel's existing platform scripts.

No upload implementation or synthetic platform readback lives here.
"""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import subprocess
import tempfile
from easel.production.service import fail
from easel.publication_bilibili import publishing_lock

VIDEO_PLATFORMS = {'xiaohongshu', 'douyin', 'kuaishou', 'weixin-channels'}


class NativeAdapter:
    def __init__(self, root, platform, command, account, env):
        if platform not in VIDEO_PLATFORMS:
            fail('invalid_platform', '该平台不能通过此入口接收视频')
        self.root, self.platform = Path(root), platform
        self.command, self.read_account, self.env = command, account, env

    def validate(self, content, final=False):
        if not isinstance(content.get('title'), str) or not content['title'].strip():
            fail('invalid_title', '请填写标题')
        # Reuse the script's existing title semantics before reserving a send.
        if self.platform == 'xiaohongshu':
            from skills.shared.scripts.xhs_publish import calc_title_length, TITLE_MAX
            if calc_title_length(content['title']) > TITLE_MAX:fail('invalid_title','小红书标题超过原发布器20全角字上限')
        elif self.platform == 'douyin':
            from skills.shared.scripts.douyin_publish import TITLE_MAX
            if len(content['title']) > TITLE_MAX:fail('invalid_title','抖音标题超过原发布器30字上限')
        if not isinstance(content.get('body'), str) or not isinstance(content.get('credits'), str):
            fail('invalid_description', '正文和署名格式不正确')
        if not isinstance(content.get('tags'), list) or any(not isinstance(t,str) for t in content['tags']):
            fail('invalid_tags', '标签格式不正确')
        if content.get('action') != 'submit':fail('invalid_action','投稿动作不正确')
        account = content.get('account')
        if account is not None and (not isinstance(account,dict) or account.get('platform') != self.platform or not account.get('uid')):
            fail('invalid_account', '请选择此平台实际登录的账号')
        if final and not account:fail('login_required', '请读取实际登录账号')

    def account(self):
        result = self.read_account(self.platform)
        if not result.get('loggedIn') or not result.get('name'):
            fail('account_unavailable', '未能核实此平台登录账号，请到账号页核实',409)
        # Existing whoami scripts expose a profile name, not always a platform UID.
        # Keep that distinction explicit; never present this binding as a real UID.
        key = str(result.get('uid') or 'profile-name:' + result['name'])
        return {'platform': self.platform, 'uid': key, 'name': result['name']}

    @contextmanager
    def session(self):
        with publishing_lock(self.root, self.platform):
            with tempfile.TemporaryDirectory(prefix='easel-publish-') as temp:
                yield NativeSession(self, Path(temp))


class NativeSession:
    # No snapshot/readback methods: a missing capability must remain unknown.
    def __init__(self, adapter, folder):
        self.adapter, self.folder, self.cover_path = adapter, folder, None

    def account(self):return self.adapter.account()

    def _stage(self, path, checksum, name):
        target = self.folder/name
        h = hashlib.sha256()
        with Path(path).open('rb') as src, target.open('xb') as dst:
            for block in iter(lambda:src.read(1024*1024), b''):
                h.update(block); dst.write(block)
        if h.hexdigest() != checksum:fail('media_changed','发送文件已变化，尚未投稿',409)
        return target

    def stage_video(self,path,checksum):return self._stage(path,checksum,'video.mp4')
    def stage_cover(self,path,checksum):
        self.cover_path=self._stage(path,checksum,'cover.jpg')
        return self.cover_path

    def upload(self,path,content):
        cmd = self.adapter.command(self.adapter.platform, path, content, self.cover_path)
        with tempfile.TemporaryFile() as log:
            try:
                proc=subprocess.run(cmd,cwd=self.adapter.root,env=self.adapter.env(),
                    stdout=log,stderr=subprocess.STDOUT,timeout=900,check=False)
                result={'returncode':proc.returncode,'timed_out':False}
                log.seek(0,2);size=log.tell();log.seek(max(0,size-65536))
                for line in log.read().decode('utf-8',errors='replace').splitlines():
                    try:data=json.loads(line)
                    except ValueError:continue
                    if isinstance(data,dict) and data.get('easel_publication')==1 and data.get('platform')==self.adapter.platform and data.get('outcome')=='verified':
                        matched=data.get('matched')
                        if isinstance(matched,dict) and isinstance(matched.get('platform_content_id'),str) and len(matched['platform_content_id'])<150:
                            result['platform_receipt']={'matched':{k:str(matched.get(k,''))[:150] for k in ('platform_content_id','status')},'account_name':str(data.get('account_name',''))[:200]}
                return result
            except subprocess.TimeoutExpired:
                return {'returncode':None,'timed_out':True}
