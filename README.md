# MissAV 智能下载终端 (MissAV Downloader)

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![UI](https://img.shields.io/badge/UI-CustomTkinter-green)
![Status](https://img.shields.io/badge/Status-Active-brightgreen)

这是一个基于 Python 的桌面端视频下载工具，专为 MissAV 设计。它结合了 **Playwright** 的自动化嗅探能力和 **N_m3u8DL-RE** 的强大下载能力，封装在一个现代化的 GUI 界面中。

本项目针对 **“便携化”** 和 **“打包发布”** 进行了特殊优化，支持将浏览器内核与执行文件打包在一起，实现开箱即用，无需用户手动安装复杂的环境。

## ✨ 功能特性

*   **📺 双模式支持**：
    *   **链接模式**：直接粘贴视频链接或演员主页链接。
    *   **搜索模式**：输入番号或演员名字自动搜索并跳转。
*   **🧠 智能筛选与打分**：自动识别“中文字幕”、“无码”、“英文字幕”并按优先级排序，自动去重。
*   **🕷️ 深度爬取**：支持自动翻页、多层级遍历（主列表 -> 中文校验 -> 详情页）。
*   **🛡️ 自动绕过验证**：内置 Cloudflare 验证等待逻辑和模拟点击机制。
*   **💾 磁盘保护**：下载前自动检测磁盘空间（<5GB 预警）。
*   **📦 便携设计**：代码内置相对路径处理，方便打包为 EXE。

## 🛠️ 安装与环境准备

### 1. 克隆项目
```bash
git clone https://github.com/haohaizi554/MissAVDownloader.git
cd MissAVDownloader
```

### 2. 安装依赖

请确保你的 Python 版本 >= 3.8。在项目根目录下打开终端：

```bash
pip install -r requirements.txt
```

### 3. 配置外部工具 (必须)

无论是以源码运行还是打包，都需要这两个核心工具存在于项目根目录：

1.  **N_m3u8DL-RE.exe**: [下载链接](https://github.com/nilaoda/N_m3u8DL-RE/releases) (解压后放入根目录)
2.  **FFmpeg**: (N_m3u8DL-RE 依赖，确保 `ffmpeg.exe` 在根目录或环境变量中)

---

## 🚀 运行模式 A：源码直接运行 (开发调试)

如果你安装了 Python 环境，可以直接运行代码，Playwright 会**自动识别**系统安装的浏览器内核，无需额外配置路径。

1.  **安装浏览器内核**：
    ```bash
    playwright install chromium
    ```
2.  **运行脚本**：
    ```bash
    python 虾片.py
    ```

---

## 📦 运行模式 B：打包为 EXE (发布/便携)

如果你想生成一个**单文件** 的 `.exe` 发给别人使用，推荐使用 `auto-py-to-exe` 可视化工具。

**注意：** 对于 `虾片封装.py`，我们需要将浏览器内核文件夹以及下载器手动作为“附加文件”打入包内。

### 1. 准备工作：提取内核到本地
虽然源码运行时会自动找系统路径，但打包时必须把内核文件“搬”到项目里来：
1.  找到系统安装的内核路径 (通常在 `C:\Users\用户名\AppData\Local\ms-playwright\chromium-xxx`)。
2.  将这个 `chromium-xxx` 文件夹复制到你的项目根目录下，并重命名文件夹为 `playwright`（若不复制，后续添加文件夹时源路径选系统中的 chromium-xxx，但目标路径需填 playwright/chromium-xxx 以保留版本号目录层级）。
    *   *此时你的项目目录应包含：`playwright/` (文件夹), `N_m3u8DL-RE.exe`, `ffmpeg.exe`, `虾片封装.py`*

### 2. 开始打包
1.  安装并启动工具：
    ```bash
    pip install auto-py-to-exe
    auto-py-to-exe
    ```
2.  **配置参数 (关键步骤)**：

    *   **Script Location (脚本位置)**: 选择 `虾片封装.py`
    *   **Onefile (单文件)**: 选择 **One File** (生成单独的 .exe)
    *   **Console Window (控制台)**: 选择 **Window Based** (隐藏黑框，因为我们有 GUI)
    *   **Additional Files (附加文件) —— 最重要的一步！**:
        点击 "Add Files" 或 "Add Folder" 添加以下三项：
        1.  **添加文件**: 选择 `N_m3u8DL-RE.exe` -> 目标路径(Destination)填 `.`
        2.  **添加文件**: 选择 `ffmpeg.exe` -> 目标路径(Destination)填 `.`
        3.  **添加文件夹**: 选择项目目录下的 `playwright` 文件夹 -> 目标路径(Destination)填 `playwright`

3.  **点击转换**:
    点击底部的 **CONVERT .PY TO .EXE** 按钮。

### 3. 打包原理说明
`虾片封装.py` 中使用了 `sys._MEIPASS` 逻辑。在单文件模式下，程序启动时会将上述附加文件解压到临时目录，代码会自动定位到这些临时文件，从而实现“即插即用”，用户电脑无需安装任何环境。

---

## 📋 注意事项

1.  **网络环境**：请确保你的网络环境可以访问目标网站。程序界面中支持设置 HTTP 代理（默认预设 `7890` 端口）。
2.  **反爬虫验证**：如果程序频繁卡在 "Just a moment..." 验证界面，程序内置了 10 秒等待，请尝试手动在弹出的浏览器窗口中点击验证，或者降低爬取频率。
3.  **关于单文件启动速度**：使用单文件模式 (One File) 打包后，每次双击运行都需要先解压内核到临时文件夹，启动速度会比文件夹模式 (One Dir) 慢 5-10 秒，属于正常现象。

## ⚠️ 免责声明

本项目仅供技术研究和学习 Python 爬虫及 GUI 开发技术之用。请勿用于非法用途。作者不对使用本工具产生的任何后果负责。
请遵守当地法律法规以及目标网站的服务条款。
