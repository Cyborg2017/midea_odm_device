# Midea ODM Device

[![GitHub release](https://img.shields.io/github/release/Cyborg2017/midea_odm_device.svg)](https://github.com/Cyborg2017/midea_odm_device/releases)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Home Assistant 自定义集成，通过美的美居云 API 控制美的慧选系列智能设备。

## 为什么创建这个集成？

美的除了自有智能设备外，还有一类被称为「美的慧选」的产品（如智能鱼缸、空气检测仪等）。这类设备与传统的 v1 LuaGet 设备存在本质区别：

- **不走 v1 LuaGet 协议**：无法通过传统的 v1 lua get API 获取状态更新或控制属性，也没有官方 lua 文件可供下载解析。
- **采用 v2 Thing Model + 设备独有 API**：属性状态查询、控制下发都通过 v2 thing model 协议以及设备专用 REST 端点完成。
- **局域网受限**：部分设备虽然可以通过局域网搜索发现并建立握手，但由于：
  - 没有可下载的 lua 文件，无法解析协议；
  - 抓不到通信数据包，无法逆向局域网通信格式。
  因此即使设备在线，也无法进行局域网控制。

由于上述原因，现有的第三方集成（如 `midea_auto_cloud`、`midea_smart_home` 等）**无法支持这类慧选设备**。本集成专为解决该问题而生：

- 针对慧选设备，通过 v2 Thing Model 协议 + 设备专用 API 实现完整的状态查询与控制能力；
- 同时保留对**传统 v1 LuaGet 协议设备**的支持（仅状态轮询，无控制能力），以兼容第三方传感器等只读设备。

> 简言之：把「美的慧选」中既无 lua 文件、又无局域网可控协议的设备纳入 Home Assistant 管理。

> ⚠️ **重要提示**：本集成需要使用美的美居账号登录获取云端 token，**不能与 `midea_auto_cloud` 等同样使用美居账号的云端集成同时登录同一账号**。美居云对同一账号的并发登录会相互踢出 token，导致其中一个集成掉线。如需同时使用，请使用不同的美居账号。

## 功能特性

- 支持美的美居云账号登录
- 自动发现家庭和设备
- 支持设备插件自动下载
- 可配置数据刷新间隔
- 支持中英文双语界面

### 支持的设备类型

| 设备类型 | 设备 | 协议 |
|---------|------|------|
| T0x14 | 智能开合帘 | V2 Thing Model |
| T0x58 | 智能鱼缸 | V2 Thing Model |
| T0xBC | 空气检测仪 | V1 Lua |

### 支持的平台

- 传感器 (sensor)
- 二进制传感器 (binary_sensor)
- 开关 (switch)
- 灯光 (light)
- 数值 (number)
- 选择 (select)
- 时间 (time)
- 按钮 (button)
- 窗帘 (cover)

## 安装

### HACS 安装

1. 确保已安装 [HACS](https://hacs.xyz/)（Home Assistant Community Store）。如未安装，按 [HACS 官方文档](https://hacs.xyz/docs/use/download/download/) 完成安装并重启 Home Assistant。
2. 进入 Home Assistant 左侧菜单 **HACS** → 右上角三个点 **自定义仓库**（Custom repositories）。
3. 在 **仓库地址** 中填入: `https://github.com/Cyborg2017/midea_odm_device`，**类别** 选择 **集成**（Integration），点击 **添加**。
4. 在 HACS 搜索框中输入 `Midea ODM Device`，找到本集成后点击进入。
5. 点击右下角 **下载**（Download），等待下载完成提示出现。
6. 重启 Home Assistant（**设置** → **系统** → 右上角电源图标 → **重新启动**）。
7. 重启完成后继续按下方 [配置](#配置) 步骤添加集成。

> 如果下载后未重启，集成将无法在「添加集成」列表中搜索到。

### 手动安装

1. 前往 [Releases 页面](https://github.com/Cyborg2017/midea_odm_device/releases) 下载最新版本的 `midea_odm_device.zip` 并解压。
2. 将解压出的 `midea_odm_device` 文件夹复制到 Home Assistant 配置目录下的 `custom_components/` 中，最终路径应为:
   ```
   <HA 配置目录>/
   └── custom_components/
       └── midea_odm_device/
           ├── __init__.py
           ├── manifest.json
           └── ...
   ```
3. 重启 Home Assistant。
4. 重启完成后继续按下方 [配置](#配置) 步骤添加集成。

## 配置

1. 进入 **设置** -> **设备与服务** -> **添加集成**
2. 搜索 "美的慧选设备"
3. 输入美的美居账号和密码
4. 选择家庭和设备
5. 完成配置

## 新增设备支持

新增设备只需在 `device_mapping/` 目录下创建 `T0xXX.py` 文件，定义 `DEVICE_MAPPING`，无需修改其他代码。

## 致谢

- [midea_auto_cloud](https://github.com/sususweet/midea_auto_cloud) — 美的设备云端集成，本集成的 v1 LuaGet 设备轮询部分参考了其云端协议实现
- [midea_smart_home](https://github.com/Cyborg2017/midea_smart_home) — 美的设备局域网集成，本集成在账号登录、设备发现流程上有所参考

## License

Apache License 2.0
