#!/usr/bin/env python3
"""
s15 permission layer: the auth/authorization gate in front of every tool call.

Loaded by s15_integrated_harness/code.py through importlib (by path, not
through sys.path), the same way config.py is, so it must not assume the
caller's sys.path and it cannot reach host names at import time. It owns
exactly three things:

    DENY_LIST            -> the destructive shell patterns
    the workspace boundary -> file tools may not leave WORKDIR
    both approval gates  -> shell commands and MCP tools ask the console

The host services it needs are injected once code.py has built them:

    PERMISSION_RUNTIME = load_permission_module()
    DENY_LIST = PERMISSION_RUNTIME.DENY_LIST
    PERMISSION_LAYER = PERMISSION_RUNTIME.PermissionLayer().bind(
        workdir=WORKDIR,
        console=CONSOLE,
        printer=terminal_print,
        policies=lambda: mcp_tool_policies,
    )
    register_hook("PreToolUse", permission_hook)   # unchanged hook path

The MCP policy table is read through that getter on purpose: code.py rebinds
mcp_tool_policies inside assemble_tool_pool(), so caching the dict here would
leave the layer looking at a stale table. The hook contract itself is
unchanged -- check() returns None to allow a call, or a string whose text
starts with "Permission denied" to block it with a reason.

Everything else (loop, tools, teams, scheduling) stays in code.py.
"""

import threading

DENY_LIST = ["rm -rf /", "sudo", "shutdown", "reboot", "mkfs", "dd if="]

FILE_TOOLS = ("read_file", "write_file", "edit_file")


class PermissionLayer:
    """Decide whether one tool_use block may run.

    The layer sees the raw tool_use before dispatch, so it can deny, ask the
    user, or let execution continue.
    """

    def __init__(self, *, workdir=None, console=None, printer=print,
                 policies=None):
        self.workdir = workdir
        self.console = console
        self.printer = printer
        self._policies = policies

    def bind(self, *, workdir, console, printer, policies):
        """Attach the host services this layer speaks through."""
        self.workdir = workdir
        self.console = console
        self.printer = printer
        self._policies = policies
        return self

    @property
    def mcp_tool_policies(self):
        """Read the live MCP policy table instead of a cached reference."""
        policies = self._policies() if self._policies is not None else None
        return policies or {}

    def check(self, block):
        """PreToolUse 总入口：按工具类别委派检查，返回拒绝原因或 None 放行。"""
        if block.name == "bash":
            return self._check_bash(block)
        if block.name in FILE_TOOLS:
            return self._check_path(block)
        if block.name.startswith("mcp__"):
            return self._check_mcp(block)
        return None

    def _check_bash(self, block):
        """先拦截 deny-list，再要求主线程经 ConsoleBroker 获得人工确认。"""
        command = block.input.get("command", "")
        if not isinstance(command, str):
            return "Permission denied: shell command must be a string"
        for pattern in DENY_LIST:
            if pattern in command:
                return f"Permission denied: '{pattern}' is on the deny list"
        if not self._approval_channel_available():
            return ("Permission denied: interactive shell approval is "
                    "unavailable during an asynchronous turn")
        self.printer("\n\033[33m[permission] shell command\033[0m")
        self.printer(f"  {command}")
        if not self._user_approved():
            return "Permission denied by user"
        return None

    def _check_path(self, block):
        """将文件工具路径解析后限制在 workdir 内，阻止路径越界访问。"""
        path = block.input.get("path", "")
        if not isinstance(path, str):
            return "Permission denied: path must be a string"
        if not (self.workdir / path).resolve().is_relative_to(self.workdir):
            return "Permission denied: path is outside the workspace"
        return None

    def _check_mcp(self, block):
        """读取 host policy；allow 直接放行，其余策略需要主线程确认。"""
        if self.mcp_tool_policies.get(block.name, "confirm") == "allow":
            return None
        if not self._approval_channel_available():
            return ("Permission denied: interactive MCP approval is "
                    "unavailable during an asynchronous turn")
        self.printer(f"\n\033[33m[permission] MCP tool: {block.name}\033[0m")
        if not self._user_approved():
            return "Permission denied by user"
        return None

    def _approval_channel_available(self) -> bool:
        # Worker threads cannot safely own stdin, so asynchronous turns have
        # no way to ask; those calls are denied instead of silently allowed.
        return threading.current_thread() is threading.main_thread()

    def _user_approved(self) -> bool:
        if self.console is not None:
            choice = self.console.ask("  Allow? [y/N] ").strip().lower()
        else:
            choice = input("  Allow? [y/N] ").strip().lower()
        return choice in ("y", "yes")
