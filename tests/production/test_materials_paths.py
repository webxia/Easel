"""Windows resolve-prefix regression without weakening material path boundaries."""
import os
from pathlib import PurePosixPath, PureWindowsPath
import stat
import subprocess
from types import SimpleNamespace

import pytest

from easel.materials.store import MaterialFileStore, MaterialStoreError, _comparison_path, reject_symlinks


def windows_paths(resolved, *, root=r'C:\library', link=None, tag=0):
    """Run the real guard with Windows path semantics on every CI platform.

    lstat/resolve are the only OS observations supplied by this fixture. The
    missing sidecar models SQLite deleting it before non-strict resolve ends.
    """
    class WindowsObservation(PureWindowsPath):
        def lstat(self):
            if self.name == 'catalog.db-shm':
                raise FileNotFoundError
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_reparse_tag=tag if self == link else 0)

        def resolve(self, *, strict=False):
            assert strict is False
            return PureWindowsPath(resolved)

    base = WindowsObservation(root)
    return base, base / 'catalog.db-shm'


@pytest.mark.parametrize('root,resolved', [
    (r'C:\library', r'\\?\C:\library\catalog.db-shm'),
    (r'C:\library', r'\\?\c:\LIBRARY\catalog.db-shm'),
    (r'\\?\C:\library', r'C:\library\catalog.db-shm'),
])
def test_disappearing_windows_sidecar_extended_local_drive_is_same_root(root,resolved):
    base, path = windows_paths(resolved, root=root)
    reject_symlinks(base, path)
    # Comparison never rewrites the input that actual filesystem operations use.
    assert str(path) == str(PureWindowsPath(root) / 'catalog.db-shm')


@pytest.mark.parametrize('resolved', [
    r'\\?\D:\library\catalog.db-shm',
    r'\\?\C:\library-other\catalog.db-shm',
    r'\\?\C:\outside\catalog.db-shm',
    r'\\?\C:\library\..\outside\catalog.db-shm',
    r'\\server\share\library\catalog.db-shm',
    r'\\?\UNC\server\share\library\catalog.db-shm',
    r'\\.\C:\library\catalog.db-shm',
    r'\\?\GLOBALROOT\Device\HarddiskVolume1\library\catalog.db-shm',
])
def test_resolved_windows_escape_or_namespace_still_rejected(resolved):
    with pytest.raises(MaterialStoreError, match='escapes'):
        reject_symlinks(*windows_paths(resolved))


@pytest.mark.parametrize('target', [r'C:\outside\catalog.db-shm', r'\\?\C:\library\catalog.db-shm'])
def test_raw_path_must_still_be_lexically_inside_same_root(target):
    base,path=windows_paths(r'\\?\C:\library\catalog.db-shm')
    with pytest.raises(MaterialStoreError, match='escapes'):
        reject_symlinks(base,type(path)(target))


def test_unc_share_boundaries_are_not_mapped_to_local_drives():
    root=r'\\server\share\library'
    reject_symlinks(*windows_paths(root+r'\catalog.db-shm',root=root))
    for resolved in [r'\\server\other-share\library\catalog.db-shm',
                     r'\\other-server\share\library\catalog.db-shm',
                     r'\\?\UNC\server\share\library\catalog.db-shm']:
        with pytest.raises(MaterialStoreError,match='escapes'):
            reject_symlinks(*windows_paths(resolved,root=root))


def test_posix_windows_looking_filename_does_not_get_windows_normalization():
    path=PurePosixPath('/library') / r'\\?\C:\asset'
    assert _comparison_path(path) is path


def test_windows_junction_tag_is_rejected_even_with_in_root_target(monkeypatch):
    # The Windows-only stat constant is provided to exercise the real fallback
    # on hosts without junctions; the native Windows test below also runs in CI.
    tag=0xA0000003
    monkeypatch.setattr(stat,'IO_REPARSE_TAG_MOUNT_POINT',tag,raising=False)
    base,path=windows_paths(r'\\?\C:\library\catalog.db-shm',link=PureWindowsPath(r'C:\library'),tag=tag)
    with pytest.raises(MaterialStoreError,match='junctions'):
        reject_symlinks(base,path)


def test_in_root_symlink_directory_is_rejected_before_resolution(tmp_path):
    root=tmp_path.resolve();target=root/'real';target.mkdir()
    (target/'asset').write_bytes(b'fixture')
    alias=root/'alias'
    try:
        alias.symlink_to(target,target_is_directory=True)
    except OSError as exc:
        pytest.skip('Native symlink creation unavailable: '+str(exc))
    with pytest.raises(MaterialStoreError,match='Symlinks'):
        MaterialFileStore(root).resolve_asset_locator('alias/asset')
    with pytest.raises(MaterialStoreError,match='Symlinks'):
        MaterialFileStore(alias)


@pytest.mark.skipif(os.name!='nt',reason='Native Windows junction test runs on Windows CI')
@pytest.mark.parametrize('target_inside',[True,False])
def test_native_windows_junction_component_and_root_are_rejected(tmp_path,target_inside):
    root=tmp_path/'library';root.mkdir()
    target=(root if target_inside else tmp_path)/'target';target.mkdir()
    (target/'asset').write_bytes(b'fixture')
    alias=root/'alias'
    subprocess.run(['cmd','/d','/c','mklink','/J',str(alias),str(target)],capture_output=True,check=True,timeout=10)
    try:
        with pytest.raises(MaterialStoreError,match='junctions'):
            MaterialFileStore(root).resolve_asset_locator('alias/asset')
        with pytest.raises(MaterialStoreError,match='junctions'):
            MaterialFileStore(alias)
        with pytest.raises(MaterialStoreError,match='junctions'):
            MaterialFileStore(alias/'nested')
        assert (target/'asset').read_bytes()==b'fixture'
    finally:
        alias.rmdir()  # Removes only the junction, never its target directory.
