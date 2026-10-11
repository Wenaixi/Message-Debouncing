"""MaiBot 消息防抖合并插件。"""

from __future__ import annotations

import asyncio
from time import monotonic
from typing import Any

from maibot_sdk import HookHandler, MaiBotPlugin
from maibot_sdk.types import ErrorPolicy, HookMode, HookOrder

from .config_models import MessageDebounceConfig
from .schema_i18n import apply_config_schema_i18n


class MessageDebouncePlugin(MaiBotPlugin):
    """把短时间内同一会话同一用户的连续消息合并成一条再处理。"""

    config_model = MessageDebounceConfig

    def __init__(self) -> None:
        super().__init__()
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def on_load(self) -> None:
        self.ctx.logger.info("消息防抖合并插件已加载")

    async def on_unload(self) -> None:
        async with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            timer = session.get("timer_task")
            if timer:
                timer.cancel()
            flush_event = session.get("flush_event")
            if flush_event:
                flush_event.set()
        self.ctx.logger.info("消息防抖合并插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict[str, object], version: str) -> None:
        del scope, config_data, version
        self.ctx.logger.info("消息防抖合并配置已更新")

    @classmethod
    def build_config_schema(
        cls,
        *,
        plugin_id: str = "",
        plugin_name: str = "",
        plugin_version: str = "",
        plugin_description: str = "",
        plugin_author: str = "",
    ) -> dict[str, object]:
        """构造带中文标题、标签和提示的 WebUI 配置 Schema。"""

        schema = super().build_config_schema(
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            plugin_version=plugin_version,
            plugin_description=plugin_description,
            plugin_author=plugin_author,
        )
        return apply_config_schema_i18n(schema)

    @HookHandler(
        "chat.receive.before_process",
        name="message_debounce_before_process",
        description="合并短时间内连续发来的消息",
        mode=HookMode.BLOCKING,
        order=HookOrder.NORMAL,
        timeout_ms=35000,
        error_policy=ErrorPolicy.SKIP,
    )
    async def handle_message(self, message: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any] | None:
        del kwargs

        cfg = self.config.plugin
        if not cfg.enabled or not isinstance(message, dict):
            return None
        if not self._should_debounce(message):
            return None

        key = self._session_key(message)
        if not key:
            return None

        item = self._build_item(message)
        if cfg.ignore_empty_message and not item["plain_text"] and not self._has_body_component(item["raw_message"]):
            return None

        async with self._lock:
            existing = self._sessions.get(key)
            if existing is not None:
                existing["items"].append(item)
                existing["last_at"] = monotonic()
                self._reset_timer_locked(key, existing)
                if cfg.log_detail:
                    self.ctx.logger.info(
                        "消息防抖追加: key=%s count=%d text=%s",
                        self._short_key(key),
                        len(existing["items"]),
                        self._preview(item["plain_text"]),
                    )
                return {"action": "abort"}

            flush_event = asyncio.Event()
            session = {
                "items": [item],
                "flush_event": flush_event,
                "first_at": monotonic(),
                "last_at": monotonic(),
                "timer_task": None,
            }
            self._sessions[key] = session
            self._reset_timer_locked(key, session)
            if cfg.log_detail:
                self.ctx.logger.info("消息防抖开始: key=%s text=%s", self._short_key(key), self._preview(item["plain_text"]))

        try:
            await flush_event.wait()
        finally:
            # 无论是否被取消都必须清掉 session/timer，避免 CancelledError 时泄漏
            async with self._lock:
                session = self._sessions.pop(key, session)
                timer = session.get("timer_task")
                if timer:
                    timer.cancel()

        items = session.get("items") or [item]
        if len(items) <= 1:
            if cfg.log_detail:
                self.ctx.logger.debug("消息防抖放行单条: key=%s", self._short_key(key))
            return None

        merged_message = self._merge_message(message, items)
        if cfg.log_detail:
            self.ctx.logger.info(
                "消息防抖结算: key=%s count=%d merged=%s",
                self._short_key(key),
                len(items),
                self._preview(merged_message.get("processed_plain_text", "")),
            )
        return {"action": "continue", "modified_kwargs": {"message": merged_message}}

    def _reset_timer_locked(self, key: str, session: dict[str, Any]) -> None:
        timer = session.get("timer_task")
        if timer:
            timer.cancel()
        elapsed = monotonic() - float(session.get("first_at") or monotonic())
        delay = min(float(self.config.plugin.debounce_seconds), max(0.0, float(self.config.plugin.max_wait_seconds) - elapsed))
        session["timer_task"] = asyncio.create_task(self._flush_later(key, delay))

    async def _flush_later(self, key: str, delay: float) -> None:
        try:
            await asyncio.sleep(max(0.0, delay))
            async with self._lock:
                session = self._sessions.get(key)
                if session:
                    session["flush_event"].set()
        except asyncio.CancelledError:
            return

    def _should_debounce(self, message: dict[str, Any]) -> bool:
        cfg = self.config.plugin
        if bool(message.get("is_notify")):
            return False
        if bool(message.get("is_command")):
            return False
        plain_text = self._message_text(message)
        if cfg.ignore_commands and self._is_command_text(plain_text):
            return False

        info = message.get("message_info") if isinstance(message.get("message_info"), dict) else {}
        is_group = isinstance(info.get("group_info"), dict) and bool(info.get("group_info", {}).get("group_id"))
        if is_group and not cfg.enable_group:
            return False
        if not is_group and not cfg.enable_private:
            return False
        return True

    def _session_key(self, message: dict[str, Any]) -> str:
        session_id = str(message.get("session_id") or "").strip()
        if not session_id:
            info = message.get("message_info") if isinstance(message.get("message_info"), dict) else {}
            group_info = info.get("group_info") if isinstance(info.get("group_info"), dict) else {}
            user_info = info.get("user_info") if isinstance(info.get("user_info"), dict) else {}
            session_id = "|".join(
                [
                    str(message.get("platform") or ""),
                    str(group_info.get("group_id") or ""),
                    str(user_info.get("user_id") or ""),
                ]
            )

        if not self.config.plugin.merge_same_user_only:
            return session_id

        info = message.get("message_info") if isinstance(message.get("message_info"), dict) else {}
        user_info = info.get("user_info") if isinstance(info.get("user_info"), dict) else {}
        user_id = str(user_info.get("user_id") or "").strip()
        key = f"{session_id}::{user_id}" if user_id else session_id

        # 防御：全空输入拼出来是 "||" / ""，不能让 "||" 落进 _sessions
        if not key.strip("|"):
            return None
        return key

    def _build_item(self, message: dict[str, Any]) -> dict[str, Any]:
        raw_message = message.get("raw_message")
        return {
            "message_id": str(message.get("message_id") or ""),
            "plain_text": self._message_text(message),
            "raw_message": list(raw_message) if isinstance(raw_message, list) else [],
        }

    def _merge_message(self, first_message: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
        merged = dict(first_message)
        separator = str(self.config.plugin.merge_separator)
        merged_text = separator.join(item["plain_text"] for item in items if item.get("plain_text")).strip()
        merged_raw: list[dict[str, Any]] = []
        for index, item in enumerate(items):
            if index > 0 and separator:
                merged_raw.append({"type": "text", "data": separator})
            raw_parts = item.get("raw_message") or []
            if raw_parts:
                merged_raw.extend(dict(part) for part in raw_parts if isinstance(part, dict))
            elif item.get("plain_text"):
                merged_raw.append({"type": "text", "data": item["plain_text"]})

        if not merged_raw:
            merged_raw = [{"type": "text", "data": merged_text}]

        merged["raw_message"] = merged_raw
        merged["processed_plain_text"] = merged_text
        merged["is_emoji"] = all(self._is_emoji_only(item.get("raw_message") or []) for item in items)
        merged["is_picture"] = any(self._has_type(item.get("raw_message") or [], "image") for item in items)
        merged["is_command"] = False
        return merged

    def _message_text(self, message: dict[str, Any]) -> str:
        processed = message.get("processed_plain_text")
        if isinstance(processed, str) and processed.strip():
            return processed.strip()

        raw_message = message.get("raw_message")
        if not isinstance(raw_message, list):
            return ""
        texts: list[str] = []
        for part in raw_message:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            data = part.get("data")
            if isinstance(data, str):
                texts.append(data)
        return "".join(texts).strip()

    def _is_command_text(self, text: str) -> bool:
        stripped = text.strip()
        if not stripped:
            return False
        return any(stripped.startswith(str(prefix)) for prefix in self.config.plugin.command_prefixes)

    @staticmethod
    def _has_body_component(raw_message: list[dict[str, Any]]) -> bool:
        body_types = {"text", "image", "emoji", "voice", "forward"}
        return any(isinstance(part, dict) and str(part.get("type") or "") in body_types for part in raw_message)

    @staticmethod
    def _has_type(raw_message: list[dict[str, Any]], part_type: str) -> bool:
        return any(isinstance(part, dict) and part.get("type") == part_type for part in raw_message)

    @staticmethod
    def _is_emoji_only(raw_message: list[dict[str, Any]]) -> bool:
        return bool(raw_message) and all(isinstance(part, dict) and part.get("type") == "emoji" for part in raw_message)

    @staticmethod
    def _preview(text: object, limit: int = 80) -> str:
        value = " ".join(str(text or "").split())
        return value if len(value) <= limit else value[:limit] + "..."

    @staticmethod
    def _short_key(key: str) -> str:
        return key if len(key) <= 24 else key[:10] + "..." + key[-10:]


def create_plugin() -> MessageDebouncePlugin:
    return MessageDebouncePlugin()
