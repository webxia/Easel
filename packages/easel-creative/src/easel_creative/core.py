"""Atomic project revisions, content-addressed assets and explicit operation facts."""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import time


class CreativeError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def require(condition, code, message):
    if not condition:
        raise CreativeError(code, message)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False, separators=(",", ":")).encode()).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def lock(path, blocking=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as f:
        if os.name == 'nt':
            import msvcrt
            f.seek(0)
            if not f.read(1):
                f.write(b'0'); f.flush()
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        try:
            yield
        finally:
            if os.name == 'nt':
                f.seek(0); msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def token(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', value),
            'invalid_id', 'IDs must contain only letters, numbers, _ and -')
    return value


def number(value, minimum=0, maximum=900):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and minimum <= value <= maximum,
            'invalid_number', f'Expected finite number in [{minimum}, {maximum}]')
    return value


class Project:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()

    def path(self, relative):
        require(isinstance(relative, str) and not Path(relative).is_absolute(), 'invalid_path', 'Relative path required')
        p = (self.root / relative).resolve()
        require(p.is_relative_to(self.root), 'path_escape', 'Path outside project')
        return p

    def head(self):
        data = read(self.root / 'project.json')
        require(data.get('schema_version') == 1, 'unsupported_schema', 'Unsupported project schema')
        return data

    def revision(self, revision=None):
        revision = self.head()['revision'] if revision is None else revision
        require(type(revision) is int and revision > 0, 'invalid_revision', 'Positive revision required')
        return read(self.root / 'revisions' / f'{revision:06}.json')

    def create(self, title, script='', topic='', context=None):
        require(isinstance(title, str) and title.strip(), 'invalid_title', 'Title required')
        require(isinstance(script, str) and isinstance(topic, str) and (script.strip() or topic.strip()),
                'missing_input', 'Provide a real script or topic')
        self.root.mkdir(parents=True, exist_ok=True)
        with lock(self.root / '.project.lock'):
            require(not (self.root / 'project.json').exists(), 'already_exists', 'Project already exists')
            data = {'schema_version': 1, 'revision': 1, 'title': title, 'script': script, 'topic': topic,
                    'context': context or {}, 'plan': None, 'confirmed': None, 'change': 'created'}
            self._write(data)
        return data

    def _write(self, data):
        revpath = self.root / 'revisions' / f'{data["revision"]:06}.json'
        require(not revpath.exists(), 'revision_exists', 'Revision already saved; preserve and inspect it')
        atomic(revpath, data)
        atomic(self.root / 'project.json', {'schema_version': 1, 'revision': data['revision'],
                                          'title': data['title']})

    def save(self, base_revision, mutate, change):
        with lock(self.root / '.project.lock'):
            old = self.revision()
            require(old['revision'] == base_revision, 'stale_revision', 'Project changed; reopen before editing')
            new = json.loads(json.dumps(old))
            mutate(new)
            new['revision'] = max([old['revision']] + [int(p.stem) for p in (self.root / 'revisions').glob('*.json')]) + 1
            new['change'] = change
            self._write(new)
        return new

    def asset(self, asset_id):
        data = read(self.root / 'assets' / f'{token(asset_id)}.json')
        p = self.path(data['path'])
        require(p.is_file() and sha(p) == data['sha256'], 'asset_changed', f'Asset bytes changed: {asset_id}')
        return data, p

    def import_asset(self, source, kind, rights, provenance):
        require(kind in {'image', 'video', 'audio', 'font'}, 'invalid_kind', 'Unsupported asset kind')
        require(isinstance(rights, dict) and rights.get('status') == 'KNOWN' and rights.get('basis'),
                'rights_required', 'Explicit KNOWN rights and basis required; tool does not infer permission')
        require(isinstance(provenance, str) and provenance.strip(), 'source_required', 'Source/provenance required')
        src = Path(source).expanduser().resolve()
        require(src.is_file(), 'missing_asset', 'Asset file not found')
        file_hash = sha(src)
        suffix = src.suffix.lower()
        require(suffix in {'.png','.jpg','.jpeg','.webp','.mp4','.mov','.mkv','.webm','.wav','.mp3','.m4a','.aac','.flac','.ogg','.aiff','.ttf','.otf','.ttc'},
                'unsupported_file', 'Unsupported file extension')
        from .media import probe
        properties = probe(src) if kind != 'font' else {}
        if kind in {'video', 'image'}:
            require(any(s['codec_type']=='video' for s in properties['streams']), 'wrong_media', 'Visual stream required')
        elif kind == 'audio':
            require(any(s['codec_type']=='audio' for s in properties['streams']), 'wrong_media', 'Audio stream required')
        asset_id = digest({'bytes': file_hash, 'kind': kind, 'rights': rights, 'source': provenance})
        relative = f'assets/{file_hash}{suffix}'
        with lock(self.root / '.project.lock'):
            dst = self.path(relative); dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                temp = dst.with_suffix(dst.suffix+'.part')
                shutil.copyfile(src, temp)
                require(sha(temp)==file_hash, 'asset_changed', 'Source changed during import')
                os.replace(temp, dst)
            data = {'id': asset_id, 'path': relative, 'sha256': file_hash, 'kind': kind,
                    'rights': rights, 'source': provenance, 'media': properties}
            atomic(self.root / 'assets' / f'{asset_id}.json', data)
        return data

    def plan(self, base_revision, script, plan):
        from .media import validate_plan
        require(isinstance(script,str) and script.strip(), 'missing_script', 'Script required')
        validate_plan(self, plan)
        def update(data):
            data.update(script=script, plan=plan, confirmed=None)
        return self.save(base_revision, update, 'plan_saved')

    def confirm(self, base_revision):
        def update(data):
            require(data['plan'] is not None, 'missing_plan', 'Save plan first')
            data['confirmed'] = digest({'script': data['script'], 'plan': data['plan'], 'context': data['context']})
        return self.save(base_revision, update, 'confirmed_by_caller')

    def patch(self, base_revision, changes, note):
        """Only addressed scene/track/caption entries change; confirmation is invalidated."""
        require(isinstance(changes,list) and changes and isinstance(note,str) and note.strip(),
                'invalid_patch', 'Explicit changes and explanation required')
        def update(data):
            require(data['plan'] is not None, 'missing_plan', 'Save plan first')
            seen=set()
            for change in changes:
                group=change['group']; identity=change['id']
                require(group in {'scenes','tracks','captions'}, 'invalid_patch', 'Unsupported patch group')
                require((group,identity) not in seen, 'invalid_patch', 'Duplicate target')
                seen.add((group,identity))
                items=data['plan'].get(group,[])
                matches=[x for x in items if x['id']==identity]
                require(len(matches)==1, 'unknown_target', f'Unknown target {identity}')
                fields=change.get('set',{})
                require(isinstance(fields,dict) and 'id' not in fields, 'invalid_patch', 'Cannot change identity')
                matches[0].update(fields)
            from .media import validate_plan
            validate_plan(self,data['plan'])
            data['confirmed']=None
        return self.save(base_revision,update,note)

    def status(self):
        data=self.revision()
        outputs=[read(p) for p in sorted((self.root/'renders').glob('*/receipt.json'))]
        return {'project':str(self.root),'current':data,'outputs':outputs,
                'history':[int(p.stem) for p in sorted((self.root/'revisions').glob('*.json'))]}
