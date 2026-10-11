"""消息防抖合并插件 WebUI 配置文案。"""

from __future__ import annotations

from typing import Any


SECTION_TITLES: dict[str, str] = {
    "plugin": "消息防抖",
}

SECTION_DESCRIPTIONS: dict[str, str] = {
    "plugin": "把短时间内同一会话、同一用户连续发送的消息合并后再交给 MaiBot 处理。",
}

FIELD_LABELS: dict[tuple[str, str], str] = {
    ("plugin", "enabled"): "启用插件",
    ("plugin", "config_version"): "配置版本",
    ("plugin", "debounce_seconds"): "防抖等待秒数",
    ("plugin", "max_wait_seconds"): "最长等待秒数",
    ("plugin", "merge_separator"): "合并分隔符",
    ("plugin", "enable_private"): "私聊启用",
    ("plugin", "enable_group"): "群聊启用",
    ("plugin", "merge_same_user_only"): "只合并同一用户",
    ("plugin", "ignore_commands"): "命令直接放行",
    ("plugin", "command_prefixes"): "命令前缀",
    ("plugin", "ignore_empty_message"): "忽略空消息",
    ("plugin", "log_detail"): "记录详细日志",
}

FIELD_HINTS: dict[tuple[str, str], str] = {
    ("plugin", "debounce_seconds"): "推荐 1.5 到 3 秒。越大越会等人把话说完，但回复也会更慢。",
    ("plugin", "max_wait_seconds"): "推荐 6 到 12 秒。用于防止用户一直连发导致 MaiBot 一直不处理。",
    ("plugin", "merge_separator"): "默认换行。多条文本合并时会用这个分隔。",
    ("plugin", "enable_private"): "开启后，私聊里的连续消息会参与防抖合并。",
    ("plugin", "enable_group"): "开启后，群聊里的连续消息会参与防抖合并。",
    ("plugin", "merge_same_user_only"): "强烈建议开启，避免把群里不同人的话合成一个人说的。",
    ("plugin", "ignore_commands"): "开启后，以命令前缀开头的消息不会等待，直接交给命令系统处理。",
    ("plugin", "command_prefixes"): "用于识别命令消息，例如 /、!、！。",
    ("plugin", "ignore_empty_message"): "开启后，没有文本、图片、表情、语音等主体内容的消息不参与防抖。",
    ("plugin", "log_detail"): "开启后，日志会记录防抖开始、追加、结算等信息，方便观察效果。",
}

HIDDEN_FIELDS: set[tuple[str, str]] = {
    ("plugin", "config_version"),
}

FLOAT_FIELDS: set[tuple[str, str]] = {
    ("plugin", "debounce_seconds"),
    ("plugin", "max_wait_seconds"),
}


def apply_config_schema_i18n(schema: dict[str, Any]) -> dict[str, Any]:
    """给插件 WebUI 配置 Schema 注入中文标题、标签和提示。"""

    sections = schema.get("sections")
    if not isinstance(sections, dict):
        return schema

    for section_name, section in sections.items():
        if not isinstance(section, dict):
            continue
        section_key = str(section_name)
        if section_key in SECTION_TITLES:
            section["title"] = SECTION_TITLES[section_key]
        if section_key in SECTION_DESCRIPTIONS:
            section["description"] = SECTION_DESCRIPTIONS[section_key]

        fields = section.get("fields")
        if not isinstance(fields, dict):
            continue
        for field_name, field in fields.items():
            if not isinstance(field, dict):
                continue
            key = (section_key, str(field_name))
            if key in FIELD_LABELS:
                field["label"] = FIELD_LABELS[key]
            if key in FIELD_HINTS:
                field["hint"] = FIELD_HINTS[key]
            if key in HIDDEN_FIELDS:
                field["hidden"] = True
            if key in FLOAT_FIELDS:
                field.setdefault("step", 0.1)
    return schema
