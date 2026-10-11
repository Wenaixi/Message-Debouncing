"""
代码审查后的修复验证测试。

覆盖两项 HIGH：
1. ``handle_message`` 中 ``flush_event.wait()`` 被取消时，必须从 ``_sessions`` 摘除
   会话并取消计时器，避免内存/句柄泄漏。
2. ``_session_key`` 在 ``session_id`` 和 ``message_info`` 三段都为 None 时
   不应退化成空字符串或 ``"||"``，必须返回 ``None`` 让外层短路。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

PACKAGE_NAME = "local_message_debounce_cn"
PLUGIN_DIR = Path(__file__).parent.parent
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))


def _import_plugin():
    from local_message_debounce_cn import plugin as plugin_module
    return plugin_module


def _make_group_message(text: str = "hello", *, session_id: str = "s-1", user_id: str = "u-1", group_id: str = "g-1", platform: str = "qq") -> dict:
    return {
        "session_id": session_id,
        "platform": platform,
        "raw_message": [{"type": "text", "data": text}],
        "processed_plain_text": text,
        "message_id": f"m-{text}",
        "message_info": {
            "user_info": {"user_id": user_id},
            "group_info": {"group_id": group_id},
        },
    }


# ============================================================================
# HIGH 2: _session_key 退化为 "||" / 空字符串
# ============================================================================

class TestSessionKeyFallback:
    def test_all_components_missing_returns_none(self):
        """trigger 退化路径：session_id / platform / group_id / user_id 全 None，
        ``_session_key`` 不应产出 ``"||"`` 或空字符串。"""
        plugin_mod = _import_plugin()
        plugin = plugin_mod.MessageDebouncePlugin()
        message = {
            "session_id": None,
            "platform": None,
            "message_info": {
                "group_info": {"group_id": None},
                "user_info": {"user_id": None},
            },
        }
        assert plugin._session_key(message) is None

    def test_all_components_missing_no_user_returns_none(self):
        """merge_same_user_only=True 时，user_id 为空也不会让空 key 漏网。"""
        plugin_mod = _import_plugin()
        plugin = plugin_mod.MessageDebouncePlugin()
        message = {
            "session_id": None,
            "platform": "",
            "message_info": {
                "group_info": {"group_id": ""},
                "user_info": {"user_id": ""},
            },
        }
        assert plugin._session_key(message) is None

    def test_valid_session_id_unchanged(self):
        """正常 session_id 路径必须保持可用，避免修一处坏一处。"""
        plugin_mod = _import_plugin()
        plugin = plugin_mod.MessageDebouncePlugin()
        message = {
            "session_id": "real-session-42",
            "platform": "qq",
            "message_info": {
                "user_info": {"user_id": "u-1"},
                "group_info": {"group_id": "g-1"},
            },
        }
        # merge_same_user_only=True (default): f"{sid}::{user_id}"
        assert plugin._session_key(message) == "real-session-42::u-1"

    def test_valid_components_no_session_id_returns_key(self):
        """无 session_id 但三段都有值时应正确拼出 key（不返 None）。"""
        plugin_mod = _import_plugin()
        plugin = plugin_mod.MessageDebouncePlugin()
        message = {
            "session_id": None,
            "platform": "qq",
            "message_info": {
                "user_info": {"user_id": "u-9"},
                "group_info": {"group_id": "g-9"},
            },
        }
        key = plugin._session_key(message)
        assert key is not None
        assert "u-9" in key
        assert "g-9" in key
        assert "qq" in key


# ============================================================================
# HIGH 1: flush_event.wait() 被取消时清理 _sessions / timer
# ============================================================================

class TestFlushWaitCancellationCleanup:
    @pytest.mark.asyncio
    async def test_cancellation_at_wait_cleans_session(self):
        """在 ``await flush_event.wait()`` 阶段被取消，必须把 session 从
        ``_sessions`` 摘除，并把挂起的 timer 取消。"""
        plugin_mod = _import_plugin()
        plugin = plugin_mod.MessageDebouncePlugin()
        message = _make_group_message(text="hello", session_id="sess-cancel", user_id="u-cancel")

        # 用一个超长 max_wait_seconds 让 wait 不会自然结束，确保一定卡在 wait
        plugin.config.plugin.max_wait_seconds = 60.0
        plugin.config.plugin.debounce_seconds = 60.0

        task = asyncio.create_task(plugin.handle_message(message))
        # 等协程进入 flush_event.wait()
        for _ in range(50):
            await asyncio.sleep(0.01)
            if "sess-cancel::u-cancel" in plugin._sessions:
                break
        assert "sess-cancel::u-cancel" in plugin._sessions, (
            "handle_message 还没建好 session 就被中断，无法验证清理逻辑"
        )
        timer = plugin._sessions["sess-cancel::u-cancel"]["timer_task"]
        assert timer is not None

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # 关键断言：cancel 后 _sessions 必须清空，timer 必须结束
        assert "sess-cancel::u-cancel" not in plugin._sessions, (
            "CancelledError 后 _sessions 仍残留 session，会泄漏"
        )
        assert timer.cancelled() or timer.done(), (
            "CancelledError 后 timer 仍在活动，会持续 set flush_event"
        )

    @pytest.mark.asyncio
    async def test_cancellation_does_not_propagate_orphan_timer(self):
        """回归保护：即使取消多次或 race，``_sessions`` 也必须保持空。"""
        plugin_mod = _import_plugin()
        plugin = plugin_mod.MessageDebouncePlugin()
        message = _make_group_message(text="hi", session_id="sess-race", user_id="u-race")
        plugin.config.plugin.max_wait_seconds = 60.0
        plugin.config.plugin.debounce_seconds = 60.0

        task = asyncio.create_task(plugin.handle_message(message))
        for _ in range(50):
            await asyncio.sleep(0.01)
            if "sess-race::u-race" in plugin._sessions:
                break
        timer = plugin._sessions["sess-race::u-race"]["timer_task"]

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        # 再 sleep 一点，确保 timer 没有在 cancel 后又自动 set flush_event
        await asyncio.sleep(0.05)
        assert "sess-race::u-race" not in plugin._sessions
        assert timer.cancelled() or timer.done()
