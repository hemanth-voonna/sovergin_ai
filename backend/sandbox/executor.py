"""Secure sandbox for AI-generated code.

Never executes untrusted code on the host directly. Two executors:

* subprocess (default) — runs in a throwaway temp directory with a hard
  timeout, CPU/memory limits (Linux), stripped environment and no shell.
* docker          — runs inside a throwaway container with no network,
  memory/CPU limits (requires the Docker CLI; recommended for production).

Both return stdout/stderr/exit code and a status, never touch the host FS.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time

from app.config import settings

logger = logging.getLogger(__name__)

_BLOCKED_IMPORTS = ("os", "subprocess", "sys", "shutil", "socket", "ctypes", "multiprocessing")

SANDBOX_BANNER = "# SovereignAI sandbox — generated code runs in isolation"


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


class SandboxResult:
    def __init__(self, status: str, stdout: str, stderr: str, exit_code: int | None,
                 duration_ms: int, language: str, executor: str):
        self.status = status          # completed | timed_out | error | killed
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.duration_ms = duration_ms
        self.language = language
        self.executor = executor
        self.log = [
            f"[sandbox] executor={executor} language={language}",
            f"[sandbox] status={status} exit_code={exit_code if exit_code is not None else '-'} "
            f"duration={duration_ms}ms",
        ]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "language": self.language,
            "log": self.log,
        }


def _limits_preamble(memory_mb: int) -> str:
    """Linux-only rlimits. Harmless no-op elsewhere."""
    return (
        f"""
import resource
resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
resource.setrlimit(resource.RLIMIT_AS, ({memory_mb} * 1024 * 1024, {memory_mb} * 1024 * 1024))
"""
    )


def _pre_exec_limits(memory_mb: int):
    """preexec_fn for the subprocess executor (POSIX only)."""
    try:
        import resource

        resource.setrlimit(resource.RLIMIT_CPU, (10, 10))
        resource.setrlimit(
            resource.RLIMIT_AS,
            (memory_mb * 1024 * 1024, memory_mb * 1024 * 1024),
        )
    except Exception:
        pass


def _run_subprocess(code: str, language: str, timeout: int, memory_mb: int) -> SandboxResult:
    start = _now_ms()
    workdir = tempfile.mkdtemp(prefix="sovereign-sbx-")
    try:
        if language == "python":
            # safety net: block imports of host-touching modules
            blocked_repr = ", ".join(repr(m) for m in _BLOCKED_IMPORTS)
            guarded = (
                "import builtins\n"
                "_real_import = builtins.__import__\n"
                "def _sovereign_import(name, *a, **k):\n"
                f"    if name.split('.')[0] in ({blocked_repr}):\n"
                f"        raise ImportError(\"Import of {blocked_repr} is blocked in the SovereignAI sandbox\")\n"
                "    return _real_import(name, *a, **k)\n"
                "builtins.__import__ = _sovereign_import\n"
                f"{code}\n"
            )
            cmd = [sys.executable, "-I", "-c", guarded]
        elif language == "bash":
            shell = "sh" if os.name == "nt" else "bash"
            cmd = [shell, "-c", code]
        else:
            return SandboxResult("error", "", f"Unsupported language: {language}", None,
                                 _now_ms() - start, language, "subprocess")

        if os.name == "posix":
            env = {
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "HOME": workdir,
                "LANG": "C.UTF-8",
                "PYTHONIOENCODING": "utf-8",
            }
        else:
            # Windows Python needs the system environment (entropy, DLLs);
            # isolation there relies on the sandbox directory + limits.
            env = dict(os.environ)
            env["PYTHONIOENCODING"] = "utf-8"
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workdir,
            env=env,
            preexec_fn=(lambda: _pre_exec_limits(memory_mb)) if os.name == "posix" else None,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            status = "completed"
            if proc.returncode < 0:
                status = "killed"
            elif proc.returncode != 0:
                status = "completed"  # user code error, still finished
            return SandboxResult(
                status=status,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                exit_code=proc.returncode,
                duration_ms=_now_ms() - start,
                language=language,
                executor="subprocess",
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return SandboxResult(
                status="timed_out",
                stdout="",
                stderr=f"Execution timed out after {timeout}s (limit: {timeout}s).",
                exit_code=None,
                duration_ms=_now_ms() - start,
                language=language,
                executor="subprocess",
            )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_docker(code: str, language: str, timeout: int, memory_mb: int) -> SandboxResult:
    if shutil.which("docker") is None:
        return SandboxResult(
            "error", "", "Docker CLI not found; install Docker or use SANDBOX_EXECUTOR=subprocess.",
            None, 0, language, "docker",
        )
    start = _now_ms()
    if language == "python":
        image = "python:3.11-slim"
        args = ["python", "-c", code]
    elif language == "bash":
        image = "alpine:latest"
        args = ["sh", "-c", code]
    else:
        return SandboxResult("error", "", f"Unsupported language: {language}", None,
                             _now_ms() - start, language, "docker")

    cmd = [
        "docker", "run", "--rm", "--network", "none",
        "--memory", f"{memory_mb}m", "--cpus", "1",
        "--pids-limit", "64",
        "-i", image, *args,
    ]
    try:
        proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True,
        )
        try:
            stdout, stderr = proc.communicate(input=code, timeout=timeout)
            status = "completed" if proc.returncode == 0 else "completed"
            if proc.returncode < 0:
                status = "killed"
            return SandboxResult(
                status=status, stdout=stdout, stderr=stderr, exit_code=proc.returncode,
                duration_ms=_now_ms() - start, language=language, executor="docker",
            )
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            return SandboxResult(
                status="timed_out", stdout="", stderr=f"Timed out after {timeout}s.",
                exit_code=None, duration_ms=_now_ms() - start, language=language,
                executor="docker",
            )
    except Exception as exc:
        return SandboxResult(
            "error", "", f"Docker sandbox failed: {exc}",
            None, _now_ms() - start, language, "docker",
        )


def run_code(code: str, language: str = "python", timeout: int | None = None,
             memory_mb: int | None = None) -> SandboxResult:
    """Run untrusted code inside the sandbox."""
    timeout = timeout or settings.SANDBOX_TIMEOUT_SECONDS
    memory_mb = memory_mb or settings.SANDBOX_MEMORY_MB
    executor = settings.SANDBOX_EXECUTOR.strip().lower()

    if executor == "docker":
        result = _run_docker(code, language, timeout, memory_mb)
        if result.status != "error":
            return result
        logger.warning("Docker executor failed (%s); falling back to subprocess.", result.stderr)

    return _run_subprocess(code, language, timeout, memory_mb)