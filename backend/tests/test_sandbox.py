"""Sandbox tests."""
from __future__ import annotations

from sandbox.executor import run_code


def test_python_execution():
    result = run_code("print('hello')\nprint(6 * 7)", timeout=5)
    assert result.status == "completed"
    assert result.stdout.replace("\r\n", "\n").strip() == "hello\n42"
    assert result.exit_code == 0


def test_python_error_captured():
    result = run_code("raise ValueError('boom')", timeout=5)
    assert result.exit_code != 0
    assert "boom" in result.stderr


def test_blocked_import_rejected():
    result = run_code("import os\nprint(os.getcwd())", timeout=5)
    assert result.exit_code != 0
    assert "blocked" in result.stderr.lower() or "blocked" in result.stdout.lower()


def test_timeout_kills_execution():
    result = run_code("import time\ntime.sleep(30)", timeout=2)
    assert result.status == "timed_out"
    assert "timed out" in result.stderr.lower()


def test_bash_execution():
    result = run_code('echo "sandbox says hi"', language="bash", timeout=5)
    assert result.status == "completed"
    assert "sandbox says hi" in result.stdout


def test_unsupported_language():
    result = run_code("x", language="cobol", timeout=5)
    assert result.status == "error"
    assert "Unsupported language" in result.stderr


def test_infinite_loop_killed_by_cpu_limit_or_timeout():
    result = run_code("while True: pass", timeout=3)
    assert result.status in ("timed_out", "killed")