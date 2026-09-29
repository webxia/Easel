"""Narrow JSON subprocess adapter for the installed Hypit CLI."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from easel.integrations.hypit.errors import HypitCLIError, HypitIntegrationError
from easel.integrations.hypit.secrets import SecretRedactor


class HypitCLI:
    """Call Hypit without importing its private Node implementation."""

    def __init__(self, executable: str | None = None, timeout: int = 180) -> None:
        self.executable = executable or os.environ.get("HYPIT_BIN") or self._discover_executable()
        self.timeout = timeout
        if not self.executable:
            raise HypitIntegrationError("找不到 Hypit CLI；请安装 Hypit 或设置 HYPIT_BIN")

    @staticmethod
    def _discover_executable() -> str | None:
        """Find a user-level Hypit install when launchd has a minimal PATH."""
        found = shutil.which("hypit")
        if found:
            return found
        local = Path.home() / ".local" / "bin" / "hypit"
        if local.is_file() and os.access(local, os.X_OK):
            return str(local)
        return None

    def _environment(self) -> dict[str, str]:
        # Hypit credentials belong to its Runtime Profile/CredentialStore, not
        # Easel's .env. Keep only process and locale variables needed to start it.
        allowed = ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE")
        env = {key: os.environ[key] for key in allowed if key in os.environ}
        # User-level Node installs commonly expose Hypit through an
        # `#!/usr/bin/env node` shim.  launchd's PATH is intentionally small,
        # so include only the resolved Hypit bin directory needed by that shim.
        try:
            hypit_bin = Path(str(self.executable)).resolve().parent
            previous = env.get("PATH", "")
            env["PATH"] = str(hypit_bin) + (os.pathsep + previous if previous else "")
        except OSError:
            pass
        return env

    def _run(self, args: list[str], workspace: Path, *, timeout: int | None = None) -> dict[str, Any]:
        cwd = workspace.resolve()
        if not cwd.is_dir():
            raise HypitIntegrationError("Hypit workspace 不存在")
        command = [str(self.executable), *args, "--json"]
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                env=self._environment(),
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            partial = exc.stdout
            if isinstance(partial, bytes):
                partial = partial.decode("utf-8", errors="replace")
            try:
                partial_payload = json.loads(partial) if partial else None
            except (json.JSONDecodeError, TypeError):
                partial_payload = None
            raise HypitCLIError(
                f"Hypit 命令超时：{args[0]}", payload=SecretRedactor.redact(partial_payload)) from exc
        except OSError as exc:
            raise HypitIntegrationError(f"无法启动 Hypit CLI：{exc}") from exc

        try:
            payload = json.loads(completed.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            detail = SecretRedactor.redact_text(
                (completed.stderr or completed.stdout or "无 JSON 输出").strip()[-1200:])
            raise HypitCLIError(f"Hypit 返回了无法解析的结果：{detail}",
                                returncode=completed.returncode) from exc
        if not isinstance(payload, dict):
            raise HypitCLIError("Hypit JSON 响应格式无效", returncode=completed.returncode)
        payload = SecretRedactor.redact(payload)
        if completed.returncode:
            if args[0] == "status" and payload.get("format") == "hypit.cli-status@1":
                build = payload.get("build")
                if isinstance(build, dict):
                    work = build.get("work")
                    result = build.get("result")
                    outcome = ((work.get("outcome") if isinstance(work, dict) else None)
                               or (result.get("state") if isinstance(result, dict) else None))
                    if outcome == "failed":
                        return payload
            if args[0] == "build" and payload.get("format") == "hypit.cli-build@1":
                build = payload.get("build")
                if isinstance(build, dict) and isinstance(build.get("id"), str):
                    return payload
            detail = payload.get("error") or payload.get("message") or completed.stderr.strip()
            detail = SecretRedactor.redact_text(str(detail or "未知错误")[-1200:])
            raise HypitCLIError(f"Hypit {args[0]} 失败：{detail}", payload=payload,
                                returncode=completed.returncode)
        return payload

    @staticmethod
    def _workspace_args(workspace: Path) -> list[str]:
        return ["--workspace", str(workspace.resolve())]

    @staticmethod
    def _runtime_args(runtime_profile: str | None) -> list[str]:
        return ["--runtime", runtime_profile] if runtime_profile else []

    def check(self, workspace: Path, run_source: Path) -> dict[str, Any]:
        return self._run(["check", str(run_source), *self._workspace_args(workspace)], workspace)

    def plan(self, workspace: Path, run_source: Path, *,
             runtime_profile: str | None = None) -> dict[str, Any]:
        return self._run(["plan", str(run_source), *self._runtime_args(runtime_profile),
                          *self._workspace_args(workspace)], workspace)

    def pricing(self, workspace: Path, run_source: Path, *,
                runtime_profile: str | None = None) -> dict[str, Any]:
        return self._run(["pricing", str(run_source), *self._runtime_args(runtime_profile),
                          *self._workspace_args(workspace)], workspace)

    def build(self, workspace: Path, run_source: Path, *, title: str,
              runtime_profile: str | None = None) -> dict[str, Any]:
        return self._run(
            ["build", str(run_source), "--title", title, *self._runtime_args(runtime_profile),
             *self._workspace_args(workspace)],
            workspace,
            timeout=max(self.timeout, 300),
        )

    def status(self, workspace: Path, build_id: str, *,
               runtime_profile: str | None = None) -> dict[str, Any]:
        return self._run(["status", build_id, *self._runtime_args(runtime_profile),
                          *self._workspace_args(workspace)], workspace)

    def inspect(self, workspace: Path, build_id: str) -> dict[str, Any]:
        return self._run(["inspect", build_id, *self._workspace_args(workspace)], workspace)

    def get(self, workspace: Path, build_id: str, output: str, destination: Path) -> dict[str, Any]:
        return self._run(
            ["get", build_id, "--output", output, "--to", str(destination),
             *self._workspace_args(workspace)],
            workspace,
        )

    def cancel(self, workspace: Path, build_id: str) -> dict[str, Any]:
        return self._run(["cancel", build_id, *self._workspace_args(workspace)], workspace)

    def builds(self, workspace: Path, *, limit: int = 100) -> dict[str, Any]:
        return self._run(["builds", "--limit", str(limit), *self._workspace_args(workspace)], workspace)

    def history(self, workspace: Path, output_name: str, *, source: Path | None = None,
                limit: int = 100) -> dict[str, Any]:
        args = ["history", output_name, "--limit", str(limit)]
        if source is not None:
            args.extend(["--source", str(source.resolve())])
        return self._run([*args, *self._workspace_args(workspace)], workspace)
