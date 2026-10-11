"""
测试辅助：在不依赖 MaiBot SDK 的环境下导入 plugin / config_models / schema_i18n。
把 maibot_sdk 桩模块塞进 sys.modules，并把插件目录注册成可导入的包。
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import types
from pathlib import Path
from typing import Any, Callable, Optional

import pytest


PLUGIN_DIR = Path(__file__).parent.parent
PACKAGE_NAME = "local_message_debounce_cn"


# ---------- maibot_sdk 桩 ----------

class _Field:
    def __init__(
        self,
        default: Any = None,
        default_factory: Optional[Callable[[], Any]] = None,
        **metadata: Any,
    ) -> None:
        self.default = default
        self.default_factory = default_factory
        self.metadata = metadata

    def __set_name__(self, owner, name: str) -> None:
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        if self.name not in instance.__dict__:
            if self.default_factory is not None:
                instance.__dict__[self.name] = self.default_factory()
            else:
                instance.__dict__[self.name] = self.default
        return instance.__dict__[self.name]


def Field(
    default: Any = None,
    default_factory: Optional[Callable[[], Any]] = None,
    **metadata: Any,
) -> _Field:
    return _Field(default=default, default_factory=default_factory, **metadata)


class PluginConfigBase:
    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)


class _Context:
    def __init__(self) -> None:
        self.logger = logging.getLogger("local_message_debounce_cn.test")


class MaiBotPlugin:
    config_model: Optional[type] = None

    def __init__(self) -> None:
        self.ctx = _Context()
        if self.config_model is not None:
            self.config = self.config_model()
        else:
            self.config = None


class _HookHandler:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.args = args
        self.kwargs = kwargs

    def __call__(self, func: Callable) -> Callable:
        func.__hook_args__ = self.args
        func.__hook_kwargs__ = self.kwargs
        return func


HookHandler = _HookHandler


class _EnumLike:
    def __init__(self, value: str) -> None:
        self.value = value

    def __repr__(self) -> str:  # pragma: no cover - debug only
        return f"EnumLike({self.value!r})"


class ErrorPolicy:
    SKIP = _EnumLike("skip")


class HookMode:
    BLOCKING = _EnumLike("blocking")


class HookOrder:
    NORMAL = _EnumLike("normal")


# ---------- 安装桩 ----------

def _install_sdk_stub() -> None:
    if "maibot_sdk" in sys.modules:
        return
    mod = types.ModuleType("maibot_sdk")
    mod.Field = Field
    mod.PluginConfigBase = PluginConfigBase
    mod.MaiBotPlugin = MaiBotPlugin
    mod.HookHandler = HookHandler

    types_mod = types.ModuleType("maibot_sdk.types")
    types_mod.ErrorPolicy = ErrorPolicy
    types_mod.HookMode = HookMode
    types_mod.HookOrder = HookOrder
    mod.types = types_mod

    sys.modules["maibot_sdk"] = mod
    sys.modules["maibot_sdk.types"] = types_mod


def _import_plugin_package() -> None:
    if PACKAGE_NAME in sys.modules:
        return
    init_file = PLUGIN_DIR / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        PACKAGE_NAME,
        init_file,
        submodule_search_locations=[str(PLUGIN_DIR)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("无法为插件包构造 spec")
    pkg = importlib.util.module_from_spec(spec)
    sys.modules[PACKAGE_NAME] = pkg
    spec.loader.exec_module(pkg)


@pytest.fixture(autouse=True)
def _patch_sdk():
    _install_sdk_stub()
    _import_plugin_package()
    yield
