# 手动上传到 GitHub

使用 GitHub 网页即可，不需要安装 GitHub CLI。请先确认当前登录的是自己的账户。

## 创建公开仓库

1. 打开 https://github.com/new 。
2. Owner 选择自己的账户，Repository name 填 `VPNWatchdog`。
3. Description 可填写：`Windows 后台国际网络监测工具，支持自定义检测周期、监测网站和异常恢复通知。`
4. 选择 Public，勾选 Add a README file，然后点击 Create repository。

## 上传源码和说明

已准备干净文件夹：`D:\My_Project\VPN_test\dist\GitHub-upload`。里面是源码、测试、资源和文档，没有虚拟环境、编译缓存、运行日志或个人配置。

1. 在新仓库的 Code 页面点击 Add file → Upload files。
2. 打开上述文件夹，进入文件夹内部，全选其中的文件和子文件夹，拖到网页上传区域。不要拖整个 GitHub-upload 外层文件夹。
3. 保留 `core/`、`ui/`、`utils/`、`docs/` 等目录层级；主目录应直接有 README.md、main.py、build.bat。
4. 等待全部上传，提交说明填 `Initial project upload with Chinese user guide`。
5. 点击 Commit changes。若页面显示 Propose changes，则按页面建立分支并完成合并。
6. 返回仓库首页，确认 README 自动显示，点击“中文使用说明”确认文档和图片能打开。

首次网页上传会更新创建仓库时的占位 README。浏览器一次最多上传 100 个文件，每个文件最多 25 MiB；准备好的源码文件夹满足这个限制。

## 发布 EXE 下载

`VPNWatchdog.exe` 约 36.2 MiB，超过普通源码网页上传限制，请放入 Releases。

1. 仓库首页点击右侧 Releases → Create a new release / Draft a new release。
2. Choose a tag 输入 `v0.2.0`，选择创建新 tag，Target 选择 main。
3. 标题填写 `VPN Watchdog v0.2.0`。
4. 说明可复制下面内容。
5. 在附件区域上传 `D:\My_Project\VPN_test\dist\VPNWatchdog.exe`、同目录的 Windows 压缩包和 SHA256SUMS.txt。
6. 本版本尚有真实 VPN 开关、桌面通知、长期运行和干净机器人工验收待完成，可勾选 This is a pre-release。
7. 等待附件上传完成，然后点击 Publish release。

发布说明示例：

```text
VPN Watchdog / Network Guardian：Windows 后台国际网络监测工具。

功能：
- 自定义 3～30 秒整数检测周期，保存实时生效。
- Google、GitHub、Cloudflare、ChatGPT、YouTube 五选 1～3。
- 工作模式临时每 3 秒检测，退出后恢复普通周期。
- 请求 RTT、动态状态判定、异常/恢复通知、系统托盘和轮转日志。

使用：下载 VPNWatchdog.exe 直接运行；也可下载 Windows 压缩包，解压后运行。
详细说明：仓库 docs/USER_GUIDE.md。

验证：39 项核心测试、7 项 GUI 测试及源码/打包进程集成测试通过。
已在 Windows 11 x64 验证。实际 VPN 开关、桌面通知、Windows 10/干净机器和长期运行仍待人工验收。
程序不连接或控制 VPN，不测速下载。
```

## 最后检查

- 仓库 URL 可由其他人打开。
- 首页直接显示 README，中文使用说明链接和图片正常。
- 根目录没有 .venv、build、日志或真实 settings.json。
- Releases 的 Assets 中有 EXE/Windows 压缩包，下载后可运行。
- 本地干净上传文件夹是本次快照。以后修改源码时，需要重新同步相应文件再上传。

参考：[GitHub 文件上传](https://docs.github.com/en/repositories/working-with-files/managing-files/adding-a-file-to-a-repository)、[发布 Release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)。
