<div align="center">
  <img src="assets/banner.svg" alt="PondCast Banner" width="100%">
</div>

<h1 align="center">PondCast</h1>

<p align="center">
  <strong>Local File Pool & Sharing · 局域网互传与共享文件池小工具</strong>
</p>

<p align="center">
  无需安装 App · 浏览器即开即用 · 可视化网络拓扑 · 系统托盘集成
</p>

<p align="center">
  <a href="https://github.com/[你的GitHub用户名]/PondCast/releases">
    <img src="https://img.shields.io/github/v/release/[你的GitHub用户名]/PondCast?color=22d3ee&label=Download&logo=github&style=flat-square" alt="Download">
  </a>
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Platform-Win%20%7C%20Mac%20%7C%20Linux-gray?style=flat-square" alt="Platform">
</p>

<br>

## 🌊 简介 (Introduction)

**PondCast** 是一款轻量化、极简、现代化的局域网文件共享小工具。

它将局域网视为一个 **“池塘 (Pond)”**，任何设备都可以向池中 **“投送 (Cast)”** 文件，或从中拾取文件。不同于传统点对点传输，PondCast 提供了一个**中心化的文件池**模式，即使发送者离线，文件依然保留在池中供他人下载。

**核心亮点：**
* **零客户端**：只有一台电脑运行服务端，其他手机/平板/电脑只需浏览器即可互传。
* **单文件运行**：打包为独立可执行文件，无需安装 Python，下载即用。
* **桌面级体验**：支持系统托盘运行，提供快捷菜单，不占用任务栏空间。

---

## ✨ 功能特性 (Features)

* **💧 文件池模式 (Pool Mode)**：
    * 开启后，所有人上传的文件汇聚一处，局域网内任何人皆可下载。
    * 适合团队协作、家庭聚会照片分享、会议资料分发。
* **🖥️ 系统托盘集成 (System Tray)**：
    * 程序启动后自动最小化至系统托盘（右下角），后台静默运行。
    * 右键托盘图标可快速打开网页、接收文件夹或退出程序。
* **🔒 隐私保护**：
    * 关闭文件池模式时，仅管理员可管理文件。
    * 实时动态流会自动对他人上传的文件名进行脱敏处理（如 `pho***.jpg`），保护隐私。
* **🕸️ 实时网络拓扑**：
    * 美观的物理力导向图，直观展示谁在上传、谁在下载。
    * 支持呼吸灯动画与流光连线效果。
* **⚡ 极速部署**：
    * 自动检测可用端口（默认 8000，冲突则自动切换）。
    * 启动后自动调用系统默认浏览器打开 Web 界面。

---

## 🚀 快速开始 (For Users)

### 1. 下载
前往 [Releases 页面](https://github.com/[你的GitHub用户名]/PondCast/releases) 下载适合您系统的版本：
* **Windows**: `PondCast_Windows.exe`
* **macOS**: `PondCast_MacOS`
* **Linux**: `PondCast_Linux`

### 2. 运行
* **Windows**: 直接双击 `.exe` 文件。
    * *注意：程序启动后**没有窗口**，请查看屏幕右下角的蓝色 "P" 字托盘图标。*
    * *首次运行若弹出防火墙提示，请务必勾选“允许访问专用网络”和“公用网络”。*
* **macOS / Linux**:
    在终端中赋予执行权限并运行：
    ```bash
    chmod +x PondCast_MacOS  # 或 PondCast_Linux
    ./PondCast_MacOS
    ```

### 3. 使用与关闭
* **访问**：程序会自动打开浏览器。将屏幕上显示的 **局域网访问地址** 发给其他设备即可。
* **关闭**：
    * **方法一**：点击网页右上角的 **电源图标** 按钮。
    * **方法二**：在系统托盘图标上右键，选择 **Exit**。

---

## 🛠️ 高级配置 (Configuration)

PondCast 支持通过命令行参数或配置文件进行自定义。

### 方法一：命令行参数
```bash
# 指定端口启动
./PondCast_Windows.exe --port 9999

```

### 方法二：配置文件

在程序同级目录下创建一个名为 `config.json` 的文件：

```json
{
  "port": 8888,
  "release_dir": "my_shared_folder",
  "received_dir": "my_downloads"
}

```

* `port`: 服务端口。
* `release_dir`: “公共文件”的存储目录。
* `received_dir`: 接收到的文件存储目录。

---

## 💻 开发者指南 (For Developers)

如果您想参与开发或从源码运行：

### 环境要求

* Python 3.9+

### 安装与运行

1. **克隆仓库**
```bash
git clone [https://github.com/](https://github.com/)[你的GitHub用户名]/PondCast.git
cd PondCast

```


2. **安装依赖**
```bash
pip install -r requirements.txt

```


*(注：主要依赖为 `flask`, `pyinstaller`, `pystray`, `Pillow`)*
3. **运行源码**
```bash
python app.py

```



### 构建发布包

本项目使用 GitHub Actions 自动构建。如果您想在本地打包：

```bash
# Windows
pyinstaller --onefile --noconsole --name "PondCast" --add-data "index.html;." app.py

# macOS / Linux
pyinstaller --onefile --noconsole --name "PondCast" --add-data "index.html:." app.py

```

---

## 🤝 贡献 (Contributing)

欢迎提交 Issue 或 Pull Request！

* 如果您发现了 Bug，请详细描述复现步骤。
* 如果您有新功能建议，欢迎在 Discussions 中讨论。

---

## 📄 开源协议 (License)

本项目基于 [MIT License](https://www.google.com/search?q=LICENSE) 开源。这意味着您可以自由地使用、复制、修改和分发本项目，只需保留原作者版权声明。
