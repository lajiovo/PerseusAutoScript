# Vela OS (Redmi Watch 6) 数理化解析展示系统 & Python 后端规范文档

本文档作为 Prompt 指南，指导 AI 逐步实现运行在 **Redmi Watch 6 (Vela OS / QuickJS + LVGL)** 上的前端解析阅读器，以及对应的 **Python 后端服务与 Web 管理端**。

---

## 目录
1. [系统整体架构与设计原则](#一-系统整体架构与设计原则)
2. [手表端 (Vela OS) 界面与逻辑规划](#二-手表端-vela-os-界面与逻辑规划)
    - [2.1 入口界面 (Home)](#21-入口界面-home)
    - [2.2 分类筛选界面 (Category)](#22-分类筛选界面-category)
    - [2.3 设置界面与存储管理 (Settings)](#23-设置界面与存储管理-settings)
    - [2.4 核心阅读界面 (Reader) - Markdown & AST 公式渲染](#24-核心阅读界面-reader---markdown--ast-公式渲染)
    - [2.5 增量同步界面 (Sync)](#25-增量同步界面-sync)
3. [服务端 (Python) 架构与路由规划](#三-服务端-python-架构与路由规划)
    - [3.1 API 服务 `main/zAnsApi.py`](#31-api-服务-mainzansapipy)
    - [3.2 Markdown & LaTeX 转 AST 核心处理引擎 `main/zAns.py`](#32-markdown--latex-转-ast-核心处理引擎-mainzanspy)
    - [3.3 Web 管理与模拟渲染前端 `main/webassets/watchans.html`](#33-web-管理与模拟渲染前端-mainwebassetswatchanshtml)
4. [核心代码逻辑与算法指导（供 AI 实现时遵循）](#四-核心代码逻辑与算法指导供-ai-实现时遵循)

---

## 一、 系统整体架构与设计原则

1. **核心目标**：在内存极受限的手表端（QuickJS/LVGL 环境），实现**零图片存储、基于字符与组件手搓**的 Markdown + LaTeX 复杂公式排版阅读器。
2. **数据流向**：
   - **Web 端**（`watchans.html`）输入原始 Markdown/LaTeX $\rightarrow$ **后端引擎**（`zAns.py`）提取并转化为包含 AST 的结构化 JSON $\rightarrow$ **存储在服务器/离线同步至手表** $\rightarrow$ **手表端组件化渲染**。
3. **关键约束**：
   - 手表内存极小，不可一次性加载过长文本，必须**按段/按字数的分页机制**。
   - 绝不使用图片渲染 LaTeX，全部依赖基于 LVGL Label、Line、Flexbox 拼接的 AST 算法。

---

## 二、 手表端 (Vela OS) 界面与逻辑规划

### 2.1 入口界面 (Home)
- **UI 布局**：
  - **顶部右侧**：设置按钮（点击跳转至设置界面）。
  - **主体内容**：卡片/列表流，分页展示所有题目解析的主标题及摘要信息，点击进入【阅读界面】。
  - **右下角**：悬浮圆形按钮（Floating Action Button），点击跳转至【分类界面】。
- **状态管理**：保存当前选中的分类标签，若未选择则默认展示“全部”。

### 2.2 分类筛选界面 (Category)
- **UI 布局**：网格或列表布局。
- **包含分类**：`全部`, `语文`, `数学`, `英语`, `物理`, `化学`, `生物`, `历史`, `地理`, `政治` 等。
- **交互**：选中某一分类后更新全局筛选条件，自动切回入口界面并刷新题目列表。

### 2.3 设置界面与存储管理 (Settings)
- **菜单选项**：
  1. **数据同步**：点击跳转至【增量同步界面】。
  2. **存储空间管理**：
     - 显示当前设备已用存储空间 / 题目数据占用空间（字节/KB 计算）。
     - 提供“一键清空本地题目缓存”按钮，带二次确认弹窗。
  3. **字体/排版微调**：设置公式基本字号。

### 2.4 核心阅读界面 (Reader) - Markdown & AST 公式渲染
- **UI 结构**：
  - **顶部固定栏**：题目标题 + 当前页码（例如 `2/5`）。
  - **底部固定栏**：[返回] 按钮与 [删除] 按钮（点击删除触发 `LVGL Dialog` 弹窗确认，确认后标记本地为已删除并在下次同步时通知服务端）。
  - **中间主体（Scrollable Container）**：Markdown 节点 + AST 手搓公式。

#### 核心渲染规则（AI 需重点实现）：
1. **分页分块机制（防止内存溢出）**：
   - 将整篇解析内容在生成时打碎为多个区块，按固定字数（如 300-500 字/页）分段。
   - **防错位算法**：切分点不得切断一个 Markdown 节点或切断一个 LaTeX AST 节点，必须在完整的段落或公式边界处进行切分。
   - 界面提供左右滑动手势或点击上一页/下一页，动态销毁旧页面的 LVGL 控件，创建新页面的控件。
2. **Markdown 渲染**：
   - H1/H2/H3：转化为加粗、加大字号的 LVGL Label。
   - 普通文本：自适应换行（`LV_LABEL_LONG_WRAP`） Label。
3. **AST 复杂公式渲染（手搓拼装引擎）**：
   - 手表端实现递归函数 `renderASTNode(node, parent_obj)`：
     - **普通字符 (`text`)**：创建 Label。
     - **分式 (`fraction`)**：创建 Flex 列容器，上方为分子 AST，中间绘制 1px 高度的 LVGL Line，下方为分母 AST。
     - **上下标 (`sup`/`sub`)**：主字符采用正常字号，右上/右下方叠加小字号 Label，调整 Y 轴偏移量。
     - **根号 (`sqrt`)**：左侧/外围绘制根号符号 `√` 与顶杠 Line，内部递归渲染内容。
   - **横向平移扩展**：当某个公式渲染后的宽度超过手表屏幕时，该公式容器自动开启 **横向滑动（Horizontal Scroll）**，允许用户左右平移查看长公式。

### 2.5 增量同步界面 (Sync)
- **固定连接路由**：访问 `http://192.168.10.3:25566/watch/ans/tasks` 获取任务队列。
- **任务队列交互与防中断逻辑**：
  - 返回的任务 JSON 包含数组（如 `[{"id": 1, "action": "download", "target": "xxx"}, ...]`）。
  - **依次队列执行**：手表端采用 `async/await` 串行执行任务。
  - **边完成边消销**：每成功处理一个任务，**立即**向服务端发送回调 API 确认销毁该任务，然后再执行下一个。这样若在第 3 个任务时闪退，下次重新进入同步时，服务端不会重发前两个任务，有效防止重复下载或状态错位。

---

## 三、 服务端 (Python) 架构与路由规划

在Perseus/main文件夹下

### 3.1 API 服务 `main/zAnsApi.py`
使用 Flask / FastAPI 托管以下路由，前缀统一为 `/watch/ans`：

| 路由 | 方法 | 功能描述 |
| :--- | :--- | :--- |
| `/watch/ans/tasks` | GET | 返回当前手表需执行的任务列表（如：新增解析、删除解析、分类更新） |
| `/watch/ans/task/ack` | POST | 手表端回调，确认某个任务已在本地完成，服务端从任务队列中删除该项 |
| `/watch/ans/get/<ans_id>` | GET | 获取指定解析 ID 的完整 JSON 数据（包含分页后的 Markdown 及公式 AST） |
| `/watch/ans/upload` | POST | 接收 Web 前端提交的原始解析文本，触发 `zAns.py` 转成 AST 格式并入库 |
| `/watch/ans/list` | GET | 获取所有的题目列表（提供给 Web 端管理使用） |

### 3.2 Markdown & LaTeX 转 AST 核心处理引擎 `main/zAns.py`
1. **LaTeX 提取**：使用正则表达式截取 `$ ... $` (行内) 和 `$$ ... $$` (块级) 公式。
2. **AST 转换器**：
   - 将公式文本解析为 AST 节点树结构。示例 JSON 输出结构：
   ```json
   {
     "type": "fraction",
     "numerator": { "type": "text", "value": "a + b" },
     "denominator": {
       "type": "sqrt",
       "content": { "type": "text", "value": "x^2" }
     }
   }
   ```
3. **长文分块算法**：
   - 输入完整的 Markdown 字符串。
   - 解析出段落节点树。
   - 按照每页约 300-500 字的安全限制，将 Markdown 节点与 AST 公式分配到 `pages: [...]` 数组中，确保公式无截断。

### 3.3 Web 管理与模拟渲染前端 `main/webassets/watchans.html`
- **功能 1：文本上传与编辑**：左侧文本框支持直接粘贴含 LaTeX 的 Markdown 解析，选择科目分类后上传至 `/watch/ans/upload`。
- **功能 2：手表渲染模拟器**：
  - 右侧构建一个 1:1 还原 Redmi Watch 6 屏幕分辨率与 QuickJS/LVGL 渲染逻辑的 DOM 容器。
  - 实时读取后端生成的 AST JSON，用 DOM / Canvas 模拟“手搓公式”与 Markdown 分页排版，确保上传者在电脑上就能看到手表端的最终视觉效果。

---

## 四、 核心代码逻辑与算法指导（供 AI 实现时遵循）

在生成实际代码时，请特别注意以下细节：

1. **AST 数据映射规范**：
   - 保持 AST 节点的极简性，包含 `type`（类型）、`value`（值）、`children`（子节点）或特定属性（`num`/`den`）。
   - 切勿生成过于庞大复杂、难以被 QuickJS 解释器解析的深层嵌套。

2. **LVGL 内存回收机制**：
   - 手表端切换阅读页码时，必须使用 `lv_obj_del(old_page_node)` 显式递归销毁上一个页面的所有子控件，防止 LVGL 句柄泄漏引发 Watch OS 崩溃。

3. **同步断点续传设计**：
   - 任务列表使用 SQLite 或本地 JSON 文件持久化。
   - `ACK` 路由收到 task_id 后必须加锁更新任务队列文件。

---

**请根据上述规范与流程，依次生成 `main/zAns.py`、`main/zAnsApi.py`、`main/webassets/watchans.html` 以及手表端 JS 运行逻辑代码。**
```

---
