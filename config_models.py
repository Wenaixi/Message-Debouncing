"""消息防抖合并插件配置。"""

from __future__ import annotations

from typing import List

from maibot_sdk import Field, PluginConfigBase


class PluginSectionConfig(PluginConfigBase):
    """插件基础配置。"""

    __ui_label__ = "消息防抖"
    __ui_icon__ = "message-square"
    __ui_order__ = 0

    enabled: bool = Field(
        default=True,
        description="是否启用消息防抖合并",
        json_schema_extra={"label": "启用插件"},
    )
    config_version: str = Field(
        default="1.0.0",
        description="配置文件版本",
        json_schema_extra={"label": "配置版本", "disabled": True},
    )
    debounce_seconds: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="收到消息后等待多久再结算，期间同一用户的新消息会继续合并",
        json_schema_extra={
            "label": "防抖等待秒数",
            "hint": "推荐 1.5 到 3 秒。越大越会等人把话说完，但回复也会更慢。",
            "x-widget": "slider",
            "min": 0.1,
            "max": 10.0,
            "step": 0.1,
        },
    )
    max_wait_seconds: float = Field(
        default=8.0,
        ge=1.0,
        le=30.0,
        description="单轮合并最多等待多久，防止用户一直连发导致 MaiBot 一直不处理",
        json_schema_extra={
            "label": "最长等待秒数",
            "hint": "推荐 6 到 12 秒。",
            "x-widget": "slider",
            "min": 1.0,
            "max": 30.0,
            "step": 0.5,
        },
    )
    merge_separator: str = Field(
        default="\n",
        description="多条文本合并时使用的分隔符",
        json_schema_extra={"label": "合并分隔符"},
    )
    enable_private: bool = Field(
        default=True,
        description="是否在私聊中启用防抖",
        json_schema_extra={"label": "私聊启用"},
    )
    enable_group: bool = Field(
        default=True,
        description="是否在群聊中启用防抖",
        json_schema_extra={"label": "群聊启用"},
    )
    merge_same_user_only: bool = Field(
        default=True,
        description="群聊中是否只合并同一个人的连续消息",
        json_schema_extra={
            "label": "只合并同一用户",
            "hint": "强烈建议开启，避免把群里不同人的话合成一个人说的。",
        },
    )
    ignore_commands: bool = Field(
        default=True,
        description="命令消息不参与防抖，直接放行",
        json_schema_extra={"label": "命令直接放行"},
    )
    command_prefixes: List[str] = Field(
        default_factory=lambda: ["/", "!", "！"],
        description="命令前缀列表",
        json_schema_extra={"label": "命令前缀"},
    )
    ignore_empty_message: bool = Field(
        default=True,
        description="没有文本、图片、表情、语音等主体内容的消息不参与防抖",
        json_schema_extra={"label": "忽略空消息"},
    )
    log_detail: bool = Field(
        default=True,
        description="是否在日志中记录开始收集、追加、结算等信息",
        json_schema_extra={"label": "记录详细日志"},
    )


class MessageDebounceConfig(PluginConfigBase):
    plugin: PluginSectionConfig = Field(default_factory=PluginSectionConfig)
