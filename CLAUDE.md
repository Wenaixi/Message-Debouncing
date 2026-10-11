# 消息防抖合并（local.message-debounce-cn）

## 官方上游与版本溯源
- 官方仓库（Upstream Repository）：https://github.com/tackyeel/Message-Debouncing
- 官方作者（Author / Maintainer）：tackyeel
- 功能定位：短时间内合并同用户连续消息防抖插件
- 本地演进定位：基于官方上游最新版本，融入本地生产环境兼容性定制与稳定性加固。
- 本地专属定制：本地完成 host max_version 放宽适配与严格 schema 分段重构。


源: GitHub `tackyeel/Message-Debouncing`  
插件 ID: `local.message-debounce-cn` v1.0.1  
路径: `/root/MaiBot/data/MaiMBot/plugins/local_message-debounce-cn/`

## 主人改过的关键文件

`_manifest.json`：`host_application.max_version` 从 `"1.0.0"` 改成 `"1.99.99"`。

## 配置要点

- upstream 锁死 `max_version=1.0.0`；MaiBot commit `efb0366` 收紧规则后，
  host 升级到 1.1.x 就被 manifest 校验拒载（"Host 版本不兼容: 版本 1.1.0
  高于最大支持 1.0.0"）。
- `sdk.min_version: "2.4.0"`，MaiBot 1.1.x SDK 实际 ≥ 2.4.0，正常。
- `config.toml` 已有 `[plugin].config_version = "1.0.0"`，MaiBot SDK 校验通过。

## 接入 & 依赖

- 纯本地 hook（chat.receive.before_process 等），无外部服务。

## 关键日志

- 启动：`消息防抖合并插件已加载`
- 运行时：每条消息触发 `消息防抖开始: key=... text=...`，到 `max_wait_seconds` 后结算。

## 用法

- 无命令，纯被动合并同一用户在防抖窗口内的连续消息。
- 配置：`[plugin].debounce_seconds` / `[plugin].max_wait_seconds`（详见 upstream README）。

## 踩坑

- `max_version` 不要锁小版本；跨次版本在 MaiBot 1.1.x 直接拒绝。
- `__pycache__` / `*.bak.*` 已 gitignore；`config.toml` 主人段保留。

## 历史脚本

本机：`legacy-0x-backup/from-server/check_plugins.py`（manifest 批量校验）

## 历史脚注

- 2026-07-29: 从 server 同步到本地仓库（baseline head=`212d564` "Update debounce hook order"）；补 `_manifest.json.max_version` 修复、`chore: 主人本地副本`。
