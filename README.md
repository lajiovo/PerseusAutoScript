# Perseus AutoTools - 珀尔修斯 AT

<p align="center">
  <img src="sources/icon.jpeg" alt="PerseusAT" width="200">
</p>

<p align="center">
  <a href="https://deepwiki.com/lajiovo/PerseusAutoScript"><img src="https://deepwiki.com/badge.svg" alt="DeepWiki"></a>
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

### 1. 🎮 游戏自动化运维 (AzurPilot & MuMu)
针对《碧蓝航线》自动化工具 AzurPilot (Alas) 与 MuMu 模拟器深度定制的监控系统：
*   🙈 **静默运行**：自动隐藏各窗口
*   🔄 **自愈流程**：自动定时检查
*   🌐 **网页操作**：基于Playwright实现对其Webui的控制与数据抓取
*   📲 **Push代收**：
    *   **信息解析**：解析红尖尖委托、行动力等消息
    *   **异常处理**：收到报错消息时重启游戏
    *   **多端推送**：同步推送到BarkApp及QQ群
*   📁 **网页后端**：可在网页后端控制进程，监视运行状态与资源任务信息

### 2. 🤖 QBot
基于 `botpy` 实现的深度交互机器人，集成在 [`QBot/`](QBot/) 目录下：
*   💬 **单聊群聊**：支持群聊与私聊模式
*   📜 **管理员远程控制**：
    *   **系统监控**：查看统计信息、运行状态
    *   **进程管理**：指令控制主服务
    *   **内网穿透**：开启内网穿透隧道远程访问
*   🖼️ **日志查看**：支持远程查看日志，支持翻页，支持游戏截图
*   🔌 **云崽 Bot 接入**：支持基于 `WebSocket` 与 `OneBot v11` 协议链接云崽 Bot（Yunzai-bot），并支持 `phi-plugin` 等插件扩展
*   🎮 **附加玩法**：内置钓鱼、拆弹专家、21 点、算术 24 点、战力排行榜等养成与互动玩法
*   🖥️ **网页后端**：提供带密码验证的 WebUI 管理后台，可以收发消息，支持备注

### 3. 📚 轻小说管理 (LK & iNovel)
*   🕵️ **轻之国度爬虫**：
    *   **常规模拟**：基于 Playwright 逐卷逐章爬取，支持滚木
    *   **断点缓存**：支持断点续爬，也支持只读本地缓存
    *   **插图处理**：自动下载补齐插图
    *   **EPUB生成**：自动打包成epub
    *   **TKgui**：提供独立的Tkinter GUI桌面程序进行可视化管理
*   📖 **哔哩轻小说 & iNovel**：
    *   **资源下载**：解析哔哩轻小说链接，并从iNovel站获取资源
    *   **XML解析缓存**：自动解析 `feed.xml` ，并识别解析分卷
    *   **插图处理**：自动下载补齐插图
    *   **EPUB生成**：自动打包成epub
    *   **TKgui**：提供独立的Tkinter GUI桌面程序进行可视化管理
    *   **WEBui**：提供的后端网页入口进行可视化管理

### 4. 🛠️ 百宝箱工具集 (Addition)
*   🌐 **完整网页后端**：自带导航网页 [`index.html`](main/webassets/index.html) ，快捷跳转各板块
*   📻 **实时日志**：网页后端实时查看各进程日志
*   🛡️ **管理员提权**：校验管理员权限
*   📈 **统计信息**：从Push处理次数到运行时长统计等
*   🌐 **Cpolar内网穿透**：一键启动 HTTP 隧道，自动关停保护
*   🎵 **MusicDL控制**：
    *   **局域网内访问**：基于端口重用与双向流量透传
    *   **自动隐藏**：自动隐藏Webview窗口
*   🎬 **FFmpeg音乐加工**：自动将 MP3 转换为 64k 低比特率版本，并抹除冗余元数据标签
*   🍎 **Pgrjz签到**：针对水果软件站的 Playwright 模拟Webapp登录与每日签到任务
*   🌐 **滚木浏览器**：地理位置伪装、剪切板穿透的独立滚木浏览器
*   📃 **在线剪切板**：内置网页实现在局域网内文件互传
*   🎺 **Vela应用**：神秘腕上应用，仅支持RedmiWacth5/6（开发中）
*   🕰  **手表同步**：同步腕上app的数据（开发中）

---

## 📁 项目目录结构

<details>
<summary>点击展开：</summary>

```
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
│   ├── botpy.log             # botpy 的日志文件
│   └── yz.py                 # 云崽 Bot 接入
├── brocache/                 # [`zBrowser.py`](zBrowser.py) 缓存文件
├── servercache/              # 大本营的缓存文件
│   ├── clipboard/            # clipboard 缓存
│   ├── ap/                   # ap 状态暂存
│   ├── pushlog/              # push 消息日志
│   └── stats.json            # 大本营统计信息
├── sources/                  # 资源
│   └── icon.jpeg/            # README用图标
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

</details>

---

## 🚀 安装与启动教程 （必看）

<details>
<summary>点击展开：</summary>

### 1. 依赖包安装
本项目基于 Python 3.10+ 开发，核心依赖包括 `Flask`, `playwright`, `botpy` (腾讯频道机器人 SDK) 等。
```bash
# 安装 Python 依赖包
pip install aiohttp botpy beautifulsoup4 ebooklib flask opencc playwright psutil pynput requests ruamel.yaml urllib3 pywin32

# 安装 Playwright 浏览器内核
playwright install chromium
```

### 2. 配置文件初始化
1.   将 [`main/config.example.yaml`](main/config.example.yaml) 复制并重命名为 `config.yaml`，按需填入模拟器路径、Bark Key、Token 等。
2.   将 [`main/auth.example.json`](main/auth.example.json) 复制并重命名为 `auth.json`，在指示位置`azurpilot.access-password` 填入Webui访问密码。
3.   将 [`QBot/key.example.json`](QBot/key.example.json) 复制并重命名为 `key.json`，填入自定义密码。
4.   将 [`Begin.example.bat`](Begin.example.bat) 复制并重命名为 `Begin.bat`，修改填入绝对路径。

### 3. AzurPilot配置
*   在 错误推送设置、大世界推送设置 等当中填入
```
provider: bark
key: http://127.0.0.1:25566/push
```

### 4. PRGJZ配置(可选)
*   使用python运行[`main/zPgrjzLogin.py`](main/zPgrjzLogin.py)，登录账户再关闭浏览器，登录信息就会保存到`pgrjzauth.json`。

### 5. 加入系统自动化(可选)

<details>
<summary>点击展开：</summary>

1. **打开任务计划程序**
* 按下 `Win + R` 键，输入 `taskschd.msc` 并回车。

2. **创建基本任务**
* 在右侧操作面板点击 **“创建基本任务...”**。
* **名称**：填写自定义任务名称（如 `PerseusAutoRun`）。

3. **设置触发器 (何时运行)**
* 根据需求选择触发时机：
* **计算机启动时**：系统开机即运行（无需用户登录）。
* **当前用户登录时**：用户进入桌面时运行。
* **定时 (每天/每周)**：指定每日固定时间段运行。

4. **设置操作 (执行内容)**
* 选择 **“启动程序”**。
* **程序或脚本**：选择[`begin.vbs`](begin.vbs)


5. **完成并启用**
* 勾选 “完成时打开此任务的属性对话框”。
* 在属性界面的“常规”选项卡中，按需勾选 **“使用最高权限运行”**（如需管理员权限）。

</details>

### 6. 主服务多级启动入口
Perseus 提供了优雅的多级防闪退、静默挂载启动链：
1.  （推荐）**一级启动入口 [`begin.vbs`](begin.vbs)**：推荐日常双击使用的无窗口 VBS 脚本。它会自动检测后端 25566 端口，若未运行则自动调用权限提权并拉起批处理脚本。
2.  **二级启动入口 [`Begin.bat`](Begin.bat)**：负责初始化环境变量并调用 Python 后端。
3.  **三级启动入口 [`begin.pyw`](begin.pyw)**：通用 Python 入口，自动加载 [`zOnepush.py`](main/zOnepush.py) 。

### 7. QBot配置
关于如何获取我的ID和机器人ID并填入配置
1.  填入appid和appsecret并正常启动QBot
2.  给机器人设置全量消息
3.  @机器人并发送该消息
4.  在`QBot/log/app.log`找到最新一条日志，大致如下
```
2026-10-01 21:19:59,305 - [INFO] - root - [on_group_message_create] 群消息 | 群ID: DR61C959404C5BS6GB3NBFFB3CD4677E | 发送者: 3A777891DA3G1BM2OP136620HAAF89A | 内容: <@G1BM2OP13669U777891DA320HAAF89A>
```
5.  设置初始主人后，发送`#op help`获取指令菜单

### 8. 模块单走
这些代码可以单独直接运行，开箱即用

支持列表如下：
1. [`main/zLK.py`](main/zLK.py) - 支持tkgui
2. [`main/ziNovel.py`](main/ziNovel.py) - 支持tkgui
3. [`main/zBrowser.py`](main/zBrowser.py) - 唯一启动方法

### 9. 云崽接入
该功能稳定性差，教程略

</details>

---

## 🌐 后端路由清单

<details>
<summary>点击展开：</summary>

本项目后端以 [`zOnepush.py`](zOnepush.py) 为核心 Flask 调度枢纽，通过蓝图 (Blueprint) 机制聚合了多个子服务模块：

### 1. 主控大本营 (`zOnepush.py`) 核心路由
*   `GET /main/` / `GET /main/<path:filename>`：托管 Web 后台控制面板静态资源（[`main/webassets/`](main/webassets/)）。
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

### ...可能有遗漏（？

</details>

---

## 📖 使用说明与访问地址

### 本地控制台的WebUI
*   **主服务后台**：`http://localhost:25566/main/`
*   **QBot后台**：`http://localhost:25567/bot`

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
