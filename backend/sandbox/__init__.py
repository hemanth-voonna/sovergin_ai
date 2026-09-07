"""Secure sandbox for AI-generated task/code execution."""

from .executor import SandboxResult, run_code

__all__ = ["SandboxResult", "run_code"]