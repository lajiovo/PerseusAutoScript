# Perseus AutoTools - 珀尔修斯 AT

<p align="center">
  <img src="QBot/suoha.png" alt="PerseusAT" width="200">
</p>

<p align="center">
  <a href="https://deepwiki.com/lajiovo/PerseusAutoScript"><img src="https://deepwiki.com/badge.svg" alt="Ask DeepWiki"></a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/github/license/lajiovo/PerseusAutoScript?style=flat-square&label=License&color=2ea44f" alt="License">
  <img src="https://img.shields.io/github/stars/lajiovo/PerseusAutoScript?style=flat-square&label=Stars&color=ffcc00" alt="Stars">
  <img src="https://img.shields.io/github/forks/lajiovo/PerseusAutoScript?style=flat-square&label=Forks&color=58a6ff" alt="Forks">
  <img src="https://img.shields.io/github/issues/lajiovo/PerseusAutoScript?style=flat-square&label=Issues&color=f85149" alt="Issues">
</p>

<p align="center">
  <img src="https://img.shields.io/github/last-commit/lajiovo/PerseusAutoScript?style=flat-square&label=Last%20Commit&color=8b949e" alt="Last Commit">
  <img src="https://img.shields.io/github/commit-activity/m/lajiovo/PerseusAutoScript?style=flat-square&label=Commit%20Activity&color=8957e5" alt="Commit Activity">
  <img src="https://img.shields.io/github/repo-size/lajiovo/PerseusAutoScript?style=flat-square&label=Repo%20Size&color=orange" alt="Repo Size">
  <img src="https://img.shields.io/github/languages/top/lajiovo/PerseusAutoScript?style=flat-square&label=Top%20Language&color=3776AB" alt="Top Language">
</p>

<p align="center">
  <img src="https://img.shields.io/github/contributors/lajiovo/PerseusAutoScript?style=flat-square&label=Contributors&color=00b4d8" alt="Contributors">
  <img src="https://img.shields.io/github/issues-pr/lajiovo/PerseusAutoScript?style=flat-square&label=Pull%20Requests&color=ffb703" alt="Pull Requests">
  <img src="https://img.shields.io/github/issues-pr-closed/lajiovo/PerseusAutoScript?style=flat-square&label=PRs%20Closed&color=2ea44f" alt="Closed Pull Requests">
</p>

---

## ⚙️ 核心功能详解

### 1. 🎮 游戏运维大本营 (AzurPilot & MuMu)
针对《碧蓝航线》自动化工具 AzurPilot (Alas) 与 MuMu 模拟器深度定制的监控系统：
*   🙈 **后台静默控制**：利用 Win32 API 强制隐藏模拟器与 Alas 窗口，通过 [`zAlas.py`](zAlas.py) 和 [`zMumu.py`](zMumu.py) 实现完全后台化运行。
*   🔄 **闭环自愈流程**：[`zMainHandler.py`](zMainHandler.py) 实现了 `check -> start -> wait -> check -> update` 的完整检查链。若检测到 `0026`（运行错误）、`0016/0017`（页面超时），会自动执行软重启或清理进程硬重启。
*   🌐 **网页自动化**：基于 Playwright 实现 AzurPilot 的自动化启动与更新。
*   📲 **智能消息解析**：
    *   **红尖尖委托**：自动解析“顶级奖励”消息，统计并通知获得的钻石数量。
    *   **行动力监控**：实时更新 AP 变化，并在低于最低保留值时发送预警。
    *   **经验报告**：汇总舰队舰船等级进度，预测经验满额剩余时间。
    *   **异常拦截**：捕捉 `EmulatorNotRunningError` 等关键错误并自动触发修复。
    *   **多端推送**：同步推送到手机 Bark App 及 QQ 群。

### 2. 🤖 QBot 智能管家 (QQ Bot)
基于 `botpy` 实现的深度交互机器人，集成在 [`QBot/`](QBot/) 目录下：
*   💬 **多场景交互与昵称支持**：支持群聊与私聊模式，允许用户昵称自定义。
*   📜 **OP 级远程控制**：
    *   系统监控：实时查看 CPU、内存、磁盘占用（`#op sys`）。
    *   进程管理：远程启动/终止云崽 (Yunzai-bot) 及其关联插件。
    *   服务操控：控制后端 25566 端口的开启与关闭，管理 Cpolar 穿透隧道。
*   🖼️ **日志/截图可视化**：
    *   支持远程查看本地四路预设日志，具备上翻、下翻、刷新及页码跳转功能。
    *   **报错溯源**：当 Alas 报错时，可远程调取错误时刻的屏幕截图（`#op log goto 0`）。
*   🔌 **云崽 Bot 协议接入与扩展**：支持基于 `WebSocket` 与 `OneBot v11` 协议链接云崽 Bot（Yunzai-bot），可通过虚构 ID 转发消息，并支持 `phi-plugin` 等插件扩展。
*   🎮 **港区养成小游戏**：内置打捞（单抽/十连）、钓鱼、拆弹专家、21 点、算术 24 点、战力排行榜等丰富的养成与互动玩法。
*   🖥️ **WebUI 后台管理**：提供带密码验证的 WebUI 管理后台，支持群聊和私信，支持加载昵称。

### 3. 📚 LK 电子书神器与轻小说中心 (LightNovel Crawler & ziNovel)
基于 Playwright 与 Flask 后端开发的轻之国度 (LK) 及轻小说自动化抓取与转换工具：
*   🕵️ **全仿真抓取**：模拟移动端 Safari 行为，绕过检测，支持 `book_id` 在线抓取。
*   💾 **智能持久化**：
    *   支持断点续传，缓存精确到卷/章级别（JSON 格式）。
    *   **插图处理**：自动建立图片 Hash 映射，支持补齐/重载图片，并在生成的 EPUB 中自动嵌入。
    *   **繁简转换**：内置 OpenCC/zhconv 转换，生成符合阅读习惯的简体 EPUB。
*   💻 **双端入口**：既支持 Web API 触发后台异步任务，也提供独立的 Tkinter GUI 桌面程序进行可视化管理。

### 4. 🛠️ 百宝箱工具集 (More)
*   🌐 **网络穿透 (Cpolar)**：集成 [`zCpolar.py`](zCpolar.py)，支持一键启动 HTTP 隧道，30 分钟自动关停保护，自动提取并分发公网地址。
*   🎵 **音乐分享 (MusicDL)**：
    *   利用 [`zMusicDL.py`](zMusicDL.py) 实现端口重用与双向流量透传。
    *   自动将本地 MusicDL 服务广播至局域网，并具备 Webview 窗口自动隐藏逻辑。
*   🎬 **多媒体处理 (FFmpeg)**：通过 [`zFfmpeg.py`](zFfmpeg.py) 监控目录，自动将 MP3 转换为 64k 低比特率版本，支持抹除冗余元数据标签。
*   🍎 **自动化签到**：[`zPGRJZ.py`](zPGRJZ.py) 实现了针对特定软件站的 Playwright 模拟登录与每日签到任务，具备二次验证逻辑。
*   🌐 **滚木浏览器**：[`zBrowser.py`](zBrowser.py) 提供了一个预设好缩放比例、地理位置伪装及剪切板穿透的自动化浏览器环境。
*   🛡️ **安全权限与防重复运行**：严格校验管理员权限，并构建防重复启动屏障，防止多进程冲突。
*   🛟 **进程守护与开机自启**：具备完善的异常捕获机制，即便遭遇报错也会守护进程挂机运行；支持配置系统开机自动启动（需手动在系统中完成配置）。
*   🌐 **可视化导航与控制面板**：自带导航网页 [`index.html`](webassets/index.html) 与控制面板网页 [`dash.html`](webassets/dash.html)，方便集中管理各服务状态与快捷跳转。

---

## 📁 项目目录结构

```text
Perseus/
├── QBot/                     # QBot 机器人独立服务目录
│   ├── assets/               # 静态资源文件
│   │    ├── index.html       # 主页面
│   │    └── chat.html        # 聊天页面
│   ├── temp_images/          # 云崽图片消息缓存
│   ├── botdata/              # 机器人数据
│   │    ├── c2chistory/      # 私聊聊天记录
│   │    ├── grouphistory/    # 群聊聊天记录
│   │    ├── groupinfo/       # 群聊信息
│   │    ├── userdata/        # 用户的游戏数据
│   │    ├── userinfo/        # 用户信息
│   │    ├── extra.json       # 其他信息
│   │    └── opsetting.json   # 管理员设置
│   ├── log/                  # 机器人板块日志
│   ├── config.py             # QBot 配置脚本
│   ├── game.py               # 简易互动小游戏逻辑
│   ├── gameconfig.json       # 游戏配置文件
│   ├── key.example.json      # Web 密钥示例文件
│   ├── main.py               # QBot 启动入口
│   ├── opcmd.py              # OP 指令集与富媒体卡片处理
│   ├── server.py             # WebUI 及服务控制端
│   ├── morecmd.py            # 额外免管理员指令
│   ├── suoha.png             # 示例图片
│   ├── botpy.log             # botpy 的日志文件
│   └── yz.py                 # 云崽 Bot 接入
├── brocache/                 # [`zBrowser.py`](zBrowser.py) 缓存文件
├── servercache/              # 大本营的缓存文件
│   ├── clipboard/            # clipboard 缓存
│   ├── ap/                   # ap 状态暂存
│   ├── pushlog/              # push 消息日志
│   └── stats.json            # 大本营统计信息
├── browser_downloads/        # [`zBrowser.py`](zBrowser.py) 下载文件
├── lkcache/                  # LK 板块的缓存文件
│   └── <book-name>/          # 单书籍缓存
│        ├── .../             # 分卷和分章节的文本与插图
│        ├── images_mapped    # 封面映射
│        └── metadata.json    # 书籍信息
├── logs/                     # 大本营的日志文件
├── temp_images/              # 临时图片消息缓存
├── webassets/                # Web 后台/控制面板前端静态资源
│   ├── index.html            # 导航页
│   ├── dash.html             # 控制页
│   ├── clipboard.html        # 在线剪切板
│   └── status.html           # 仪表盘暨统计信息
├── begin.vbs                 # 一级启动入口 (VBS 无窗口防闪退)
├── Begin.example.bat         # 二级启动入口 示例 (CMD 批处理)
├── begin.pyw                 # 三级启动入口 (Python 后端静默挂载)
├── zOnepush.py               # 主控大本营中心调度与状态监控 (主 Flask 应用入口)
├── LICENSE                   # 项目开源许可证 (GPL v3)
├── README.md                 # 项目说明文档
├── auth.example.json         # AzurpilotWebui 认证信息配置示例
├── config.example.yaml       # 主配置文件示例
├── zAlas.py                  # AzurPilot 自动化控制与更新逻辑
├── zBanMumu.py               # MuMu 模拟器广告弹窗处理
├── zBark.py                  # Bark 消息推送核心模块
├── zBarkCustom.py            # 自定义消息推送接口
├── zBrowser.py               # 滚木浏览器一键启动
├── zConfig.py                # 全局配置读取与解析模块
├── zCpolar.py                # Cpolar 内网穿透隧道管理
├── zFfmpeg.py                # FFmpeg 音频压缩
├── zLK.py                    # 轻之国度电子书抓取、解析与 EPUB 打包核心
├── zLKapi.py                 # LK 接口逻辑
├── zLKserver.py              # LK 后端蓝图路由服务 (`/lkapi`)
├── zLKCacheViewerServer.py   # LK 缓存查看蓝图路由服务 (`/lkvapi`)
├── zInovelServer.py          # 轻小说后端蓝图路由服务 (`/inovelapi`)
├── ziNovel.py                # 轻小说核心爬虫与导出逻辑
├── zWatchApi.py              # 智能手表同步与状态统计蓝图路由 (`/vela`)
├── zWatchServer.py           # 智能手表服务端蓝图兼容层
├── zMainHandler.py           # 消息转发和多任务轮询调度
├── zMumu.py                  # MuMu 模拟器进程管理与提权
├── zMusicDL.py               # MusicDL 音乐服务启动与局域网广播
├── zPGRJZ.py                 # 苹果软件站签到等扩展自动化任务
├── zPerseusLogger.py         # 全局日志轮转与格式化处理
├── zPgrjzLogin.py            # 苹果软件站网页登录入口
├── zPlaywright.py            # 旧版 Playwright 控制逻辑
├── zPlaywrighNew.py          # 新版 Playwright 控制核心
├── pgrjzauth.json            # 苹果软件站登录信息 (运行时生成)
└── last_checkin.txt          # 签到日期记录
```

---

## 🌐 精确后端路由清单 (`zOnepush.py` 与蓝图注册)

本项目后端以 [`zOnepush.py`](zOnepush.py) 为核心 Flask 调度枢纽，通过蓝图 (Blueprint) 机制聚合了多个子服务模块：

### 1. 主控大本营 (`zOnepush.py`) 核心路由
*   `GET /main/` / `GET /main/<path:filename>`：托管 Web 后台控制面板静态资源（[`webassets/`](webassets/)）。
*   `GET/POST /push`：外部消息接收与分发推送核心接口。
*   `GET/POST /start`、`/stop`、`/restart`、`/shutdown`：主控及子服务生命周期管理。
*   `GET/POST /bot/start`、`/bot/shutdown`：QBot 机器人进程的快捷启停。
*   `GET/POST /music/start`、`/music/stop`、`/music/ffm`：音乐服务与 FFmpeg 压缩任务调控。
*   `GET/POST /cp/start`、`/cp/stop`、`/cp/get`：Cpolar 内网穿透隧道控制与公网地址获取。
*   `GET/POST /lk`、`/lk/<book_id>` 等：轻之国度电子书抓取异步任务触发。
*   `GET /ping`、`GET /help`：健康检查与帮助指令返回。

### 2. LK 电子书服务蓝图 (`zLKserver.py`，前缀 `/lkapi`)
*   `GET /lkapi/status`：获取电子书爬虫运行状态。
*   `GET /lkapi/tasks`：列出当前异步爬虫任务队列。
*   `POST /lkapi/book/<book_id>/crawl`：触发指定书籍全本抓取。
*   `POST /lkapi/book/<book_id>/epub`：将抓取缓存打包生成 EPUB 电子书。
*   `GET /lkapi/books/all`：获取所有已缓存书籍清单。

### 3. LK 缓存查看蓝图 (`zLKCacheViewerServer.py`，前缀 `/lkvapi`)
*   `GET /lkvapi/viewer`：查看本地已缓存书籍章节与插图的网页端。
*   `GET /lkvapi/books/all`：拉取本地缓存统计概览。

### 4. 轻小说服务端蓝图 (`zInovelServer.py`，前缀 `/inovelapi`)
*   `GET /inovelapi/status`：轻小说抓取状态查询。
*   `GET /inovelapi/books`：获取已下载轻小说书单。
*   `POST /inovelapi/export`：触发轻小说导出为 EPUB/TXT 任务。

### 5. 智能手表与状态同步蓝图 (`zWatchApi.py`，前缀挂载于 `/vela` 等)
*   `POST/GET /vela/sync`：手表同步与数据交互。
*   `GET /vela/api/stats`：手表应用统计状态返回。

---

## 🚀 启动流程与多级入口说明

### 1. 依赖包安装说明
本项目基于 Python 3.10+ 开发，核心依赖包括 `Flask`, `playwright`, `requests`, `pyyaml`, `botpy` (腾讯频道机器人 SDK) 等。
```bash
# 安装 Python 依赖包
pip install -r requirements.txt

# 安装 Playwright 浏览器内核
playwright install chromium
```

### 2. 配置文件初始化
*   将 [`config.example.yaml`](config.example.yaml) 复制并重命名为 `config.yaml`，按需填入模拟器路径、Bark Key、Token 等。
*   将 [`auth.example.json`](auth.example.json) 复制并重命名为 `auth.json`（若需自动化登录功能）。
*   在 [`QBot/`](QBot/) 目录下配置对应的密钥文件（如 [`key.example.json`](QBot/key.example.json) 对应 `key.json`）。

### 3. 多级启动入口 (`Windows`)
Perseus 提供了优雅的多级防闪退、静默挂载启动链：
1.  **一级启动入口 [`begin.vbs`](begin.vbs)**：推荐日常双击使用的无窗口 VBS 脚本。它会自动检测后端 25566 端口，若未运行则自动调用权限提权并拉起批处理脚本。
2.  **二级启动入口 [`Begin.example.bat`](Begin.example.bat)**（可复制为 `Begin.bat`）：带工作路径校验的批处理脚本，负责初始化环境变量并调用 Python 后端。
3.  **三级启动入口 [`begin.pyw`](begin.pyw)**：Python 纯静默挂载入口，直接在后台加载 [`zOnepush.py`](zOnepush.py) 的 `main()` 调度逻辑，实现无黑窗口常驻挂机。

---

## 📖 使用说明与访问地址

### 1. 本地控制台与 WebUI
*   **主控大本营面板**：`http://localhost:25566/main/`（可集中控制各项自动化服务的开启、关闭、状态查看）
*   **QBot 机器人后台**：`http://localhost:25567/bot`（需配置密码，查看聊天记录及机器人管理）

---

## ⚖️ 开源/个人项目免责声明 (Disclaimer)

1.  **仅供学习交流**：本仓库所提供的所有自动化脚本、爬虫工具、模拟器控制插件及 QBot 互动功能，**仅供计算机技术爱好者进行学习、研究与交流使用**。
2.  **遵守服务条款**：使用者必须严格遵守目标软件、游戏（如《碧蓝航线》）、网站（如轻之国度等）的服务条款、用户协议及相关法律法规。**严禁**将本工具用于任何商业营利、恶意破坏、刷量作弊或违反服务商规定的非法用途。
3.  **风险自负原则**：使用本工具所产生的一切后果（包括但不限于账号封禁、数据丢失、设备异常、服务商追责等）均由使用者自行承担，原作者及项目贡献者不承担任何直接或间接的法律责任。
4.  **开源协议约束**：本项目遵循 [GNU GENERAL PUBLIC LICENSE Version 3](LICENSE) (GPL v3) 开源协议，在遵循协议的前提下可自由使用、修改与分发。

---

## 📜 证书 (License)

本项目采用 [GNU GENERAL PUBLIC LICENSE Version 3](LICENSE) 协议授权。

---
<div align="right">
  <i>Update Time: 2026-10-01</i>
</div>
