# VPN Watchdog / Network Guardian

Windows 后台国际网络监测工具。通过当前系统代理或 TUN 网络路径探测国际服务；持续异常和恢复时发送 Windows 系统通知。不依赖 VPN 软件进程，不修改 VPN 或网络设置。

支持 **3～30 秒整数周期**、**五选一至三个监测目标**和实时应用设置。候选为 Google、GitHub、Cloudflare、ChatGPT、YouTube；默认保留前三个。提供托盘、防抖、通知、暂停、日志及 Windows 单文件 EXE。

**普通用户请先阅读 [中文使用说明](docs/USER_GUIDE.md)**，了解下载安装、工作模式、状态含义和常见问题。程序下载请打开仓库首页右侧的 **Releases**，选择发布附件中的 `VPNWatchdog.exe` 或 Windows 压缩包；GitHub 自动生成的 Source code 压缩包是源码，不是安装包。

开发变更、配置机制、验证证据与人工清单见 [ROUND2.md](docs/ROUND2.md)。未加入任意 URL、测速或 VPN 控制功能。

## 运行 EXE

构建产物为 `dist/VPNWatchdog.exe`，可以复制到其他目录运行，无需安装 Python。面向 Windows 10/11 x64；当前仅在 Windows 11 上构建和测试，Windows 10 和干净虚拟机仍需人工验收。

双击后默认进入系统托盘。双击托盘图标打开主界面；右键可暂停/恢复、立即检测、打开设置、开启工作模式、测试系统通知、退出。关闭主窗口会继续在托盘监测，选择 **Exit** 或 Dashboard 的 **退出** 才真正结束。没有可用托盘时显示主窗口。

显示主界面启动：

```powershell
.\dist\VPNWatchdog.exe --dashboard
```

配置和日志默认位于 `%LOCALAPPDATA%\VPNWatchdog`，可用 `--data-dir D:\SomeFolder` 指定目录。主程序对同一数据目录限制单实例；命令行测试请用独立数据目录，避免与 GUI 同时写日志。

没有添加开机启动，也不需要管理员权限。

## 安装依赖和源码运行

使用 Python 3.11 或更新版本（验证环境为 Python 3.12 x64）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py --dashboard
```

只安装 PySide6 Essentials，含 QtCore、QtNetwork、QtGui、QtWidgets；避免下载无关的浏览器组件。`requirements.lock.txt` 保存本次构建的确切版本，复现时可替代 `requirements.txt`。

命令行检测一轮或持续检测：

```powershell
.\.venv\Scripts\python.exe main.py --once --data-dir .runtime-cli
.\.venv\Scripts\python.exe main.py --cli --data-dir .runtime-cli
```

持续检测按 Ctrl+C 结束。一轮输出每个目标的 `GOOD` / `NORMAL` / `HIGH_LATENCY` / `VERY_HIGH_LATENCY` 或错误类别，以及 HTTP 状态码和 RTT；最终输出 `STATUS`（已确认状态）和 `observed`（本轮观测）。第一次 `--once` 显示 `STATUS=UNKNOWN` 是预期行为，因为没有足够的连续证据。退出码 2 表示配置或探测器错误；网络失败以结果字段表达，交付一轮结果后退出码为 0。

## Dashboard 与判定

- 绿色：HEALTHY / RECOVERED。
- 黄色：HIGH_LATENCY。
- 橙色：UNSTABLE，成功数不足多数门槛，但至少一个目标可达。
- 红色：VPN_DOWN。
- 灰色：UNKNOWN / NO_INTERNET / 暂停。

界面只显示启用目标，表格随选择动态变化，并显示实际检测周期。请求延迟中位数只取成功目标；失败率分母为本轮启用目标数。连续判定轮数与本轮成功目标数分别显示。近期记录最多 200 行，本次运行的事件数/超时数/已结束事件总中断时长不是持久化的“今日统计”。

Google 使用 HEAD 并要求 204；GitHub 使用 HEAD 并要求 200；Cloudflare trace 对 HEAD 实测返回 404，因此使用小型 GET，要求 200，累计读取超过 4096 字节则中止（在途网络数据可能略多）。ChatGPT / YouTube 对首页发 HEAD，收到有效 HTTPS HTTP 200～599 响应就算网络路径可达；非 200 响应会注明限制、重定向或服务异常，不表示账户、页面或视频功能正常。不下载完整网页或视频、不使用缓存、不自动跟随重定向、不忽略 TLS 证书错误。

成功门槛为 `N // 2 + 1`：一个目标需 1/1，两个需 2/2，三个需 2/3 或 3/3。达到门槛且延迟低于阈值，本轮为 HEALTHY；2/3 成功时额外注明失败目标。达到门槛但延迟高则为 HIGH_LATENCY。部分可达但不足门槛为 UNSTABLE。所有目标没有有效连接且连续 3 轮，才确认 VPN_DOWN（明确无本机网卡时为 NO_INTERNET）。有效 HTTP 服务错误不会单凭响应判 VPN_DOWN。质量异常连续 3 轮确认，健康连续 2 轮确认；已确认中断连续 2 轮达到门槛后仅发送一次 RECOVERED。

默认周期 5 秒、请求超时 3 秒。掉线报警通常在故障后的约 13–18 秒出现，取决于故障相对于检测周期的位置及请求耗时；系统代理/PAC 阻塞时可能更久。不能保证任意异常“立即”告警。

中断时长从第一轮连续失败到确认恢复计算，含确认等待、睡眠或暂停间隙，是观察窗口的估算，不能证明未观察期间一直断网。异常持续期间只发送一次 Down、一次 Recovery；质量下降提醒默认冷却 10 分钟。暂停及睡眠间隙清除未确认计数。仅改周期、切工作模式或立即检测保留状态；检测中忽略额外请求。改变目标集合重置当前状态、计数、RTT、界面记录及旧事件上下文，磁盘日志保留；新组合不能替旧组合发恢复通知。仅调整同一集合的顺序保留状态与 RTT。

## 配置

主程序首次运行创建 `config/settings.json`，设置窗口保存后立即生效。示例见 `config/settings.example.json`。

| 配置项 | 默认 | 说明 |
|---|---:|---|
| check_interval | 5 | 任意整数 3～30 秒；持久化普通周期 |
| selected_targets | Google / GitHub / Cloudflare | 五个候选中选择 1～3 个不同目标 |
| timeout_s | 3 | 单请求期限，1–10 秒；轮次不重叠 |
| failure_count | 3 | 连续异常确认，2–10 轮 |
| recovery_count | 2 | 连续恢复确认，2–10 轮 |
| good_ms | 150 | GOOD 上限 |
| high_ms | 300 | HIGH_LATENCY 起点 |
| very_high_ms | 500 | VERY_HIGH_LATENCY 起点 |
| notification_cooldown_s | 600 | 质量提醒冷却，至少 60 秒 |
| notifications | true | 是否发送异常/恢复系统通知 |
| sound | true | 是否额外播放 Windows 系统提示音 |

阈值必须递增。旧 `interval_s` 自动迁移为 `check_interval`；缺失字段补默认值。越界周期夹到 3～30；目标过滤未知名称、去重、取合法前三个，空集合恢复默认。损坏 JSON 恢复默认。修复前原字节备份为 `settings.json.bak`，修复行为写入日志；若目录不可写，修复仅在内存生效。工作模式是本次运行的临时 3 秒覆盖，不写入配置；退出后恢复保存的普通周期。工作模式中修改普通周期也不会退出工作模式。

额外提示音使用 Windows `MessageBeep`。关闭它不改变 Windows 自身的通知声音设置。自定义 warning.wav / recovered.wav 留到第二阶段。

## 代理、网络与误差边界

默认使用 Qt 的系统代理工厂，Windows 下通过 WinHTTP 获取代理。不用环境变量覆盖系统代理。TUN/WireGuard/OpenVPN 由系统路由处理；系统 HTTP/SOCKS 代理由 Qt 能解析的系统配置处理。只有客户端提供本地代理端口、却没有开启系统代理/TUN 时，需要先在 VPN 客户端启用对应模式；MVP 尚未提供手动代理配置。

WinHTTP 配置可能与浏览器专用代理不同，PAC、代理认证及代理切换仍需在实际客户端环境验收。每轮使用新连接管理器；系统代理查询可能存在缓存或延时。主进程对失联探测器回收并重启，显示 `UNKNOWN / MONITOR_TIMEOUT`，不会把内部超时误记为 VPN_DOWN。

探测器内部错误会单独通知“监测暂不可用”，按质量提醒周期冷却去重，避免监测器失效时用户误以为它仍在工作。

`NO_INTERNET` 只在 Windows 没有非 loopback 的 operational 网卡时确认；虚拟网卡仍在线时，物理网络故障可能显示 VPN_DOWN。网卡信息查询失败不会冒充本机断网。

HTTP RTT 包含 DNS、代理、TCP、TLS 和响应耗时，采用新连接，通常高于 ping 延迟。MVP 无法可靠拆分 TCP 连接超时和 HTTP 响应超时，统一显示 `REQUEST_TIMEOUT`；DNS/代理/TLS/拒绝连接/连接重置等按 Qt 错误分类。HTTP 探测失败率不是 ICMP 丢包率。本工具证明探测服务的可用性，不能证明特定 Codex 会话、OpenAI 账户或每个国外站点正常，也不能证明流量一定经过 VPN。

通知使用 Qt Windows 原生托盘系统通知。Windows 通知设置、勿扰/专注模式、远程桌面环境会影响显示和声音。托盘菜单的 **Test Notification** 可独立检查通知投递；自动化测试验证了通知调用和去重，实际桌面显示需人工检查。

## 日志

`logs/network.log` 包括每轮状态、连续轮数、延迟、失败率、目标状态码/错误/响应说明、事件和中断时长；新增 SETTINGS_CHANGED、WORK_MODE_ON/OFF、MONITORING_SCOPE_CHANGED、CONFIG_REPAIRED。每个文件 2 MB，保留 5 个备份，总计约 12 MB。不保存网页正文、代理密码或外网 IP。目录不可写时请改用可写的 `--data-dir`。

```text
2026-10-10 15:17:06 STATE=UNKNOWN observed=HIGH_LATENCY consecutive=1 latency_ms=1046.0 ...
2026-10-10 15:17:06 TARGET=Cloudflare success=True reachable=True rtt_ms=1046.0 http=200 error=-
```

## 测试、验收与排查

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m unittest tests.gui_cases -v
.\.venv\Scripts\python.exe tools\smoke_gui.py
.\.venv\Scripts\python.exe tools\probe_candidates.py
.\.venv\Scripts\python.exe tools\smoke_dynamic.py
.\.venv\Scripts\python.exe tools\smoke_monitor.py
.\build.bat
.\.venv\Scripts\python.exe tools\smoke_packaged.py
.\.venv\Scripts\python.exe tools\smoke_frozen_control.py
```

自动化使用临时 HTTP 服务和合成结果，不关掉你的网络。GUI 用例单独启动 QApplication，核心测试使用 QCoreApplication，因此分两条命令运行。联网工具使用真实 HTTPS；probe_candidates 只诊断全部候选，正常监测仍最多三个。离屏预览明确标注模拟数据。当前测试结果见 [ROUND2.md](docs/ROUND2.md)，完整环境验收见 [TESTING.md](docs/TESTING.md)，首轮历史记录见 [VALIDATION.md](docs/VALIDATION.md)。

常见问题：

- **正常网络显示高延迟**：这是完整 HTTPS 请求耗时；按实际基线调高阈值。先查看每个目标结果和日志。
- **关闭 VPN 仍正常**：你的网络本身可能能直连这些服务；检测不是 VPN 进程检查。也可能 TUN 或系统代理还在处理流量。
- **浏览器正常，工具失败**：浏览器可能使用插件/单独代理；检查 Windows/WinHTTP 代理与 VPN 客户端系统代理选项。
- **一个服务失败**：先看 HTTP/DNS/SSL/代理错误。三目标中 2/3 成功仍可 HEALTHY 或 HIGH_LATENCY，并注明失败目标；两目标中 1/2 成功为 UNSTABLE。均不直接报掉线。
- **收到 MONITOR_TIMEOUT**：查 PAC/系统代理、日志中的 WORKER 诊断；检测进程会重启，此事件没有证明 VPN 掉线。
- **没有通知**：运行 Test Notification，检查 Windows 通知、勿扰模式和设置中的通知开关。
- **托盘找不到**：查看 Windows 隐藏图标区域；用 `--dashboard` 启动。
- **打包后启动报缺少 DLL**：使用 x64 Windows，查看错误框和构建警告；干净机器应安装微软官方 Visual C++ Redistributable，随后复测。不要从不明网站下载 DLL。

## 打包

```powershell
.\build.bat
```

脚本先运行核心和 GUI 测试，再生成图标和单文件 `dist/VPNWatchdog.exe`。EXE 无控制台；其探测子进程恢复继承的输入/输出管道，标准输入传控制命令，标准输出传结果和确认。源码 CLI 更适合终端排查。

单文件首次启动会解压到临时目录；主程序关闭前有界回收探测进程。EXE 未签名，Windows 是否显示 SmartScreen 取决于本机策略；对外发布需代码签名、Qt/Python/PyInstaller 许可证与干净机器验收。CPU/内存的长期指标尚未做数周验证，不能承诺小于 100 MB。

本次 EXE 约 36.2 MiB。构建 spec 限制 DLL 搜索路径，避免其他工具的同名 DLL 被带入；使用 Windows 系统 UCRT。三个目标、5 秒周期每天约 51,840 次请求；HEAD/小型 GET 限制正文，但 TLS/响应头仍有开销。有流量限制时可用 30 秒并减少目标数。

## 开发结构

```text
main.py                    入口、GUI/CLI/探测进程路由
core/
  models.py                纯 Python 数据模型与延迟等级
  local_network.py         Windows 网卡证据
  probe_worker.py          隔离进程内的异步并行探测
  network_monitor.py       子进程 IPC、看门狗、重启与回收
  worker_control.py        单个 stdin 读取线程向 Qt 事件循环交付命令
  state_manager.py         纯 Python 状态机、防抖、事件时长
  cli.py                   命令行输出与日志
ui/
  application.py           UI 协调、暂停、工作模式、单实例
  main_window.py           Dashboard
  tray.py                  状态图标与托盘菜单
  settings_window.py       基础设置与校验
utils/                     配置、轮转日志、通知、打包管道
tests/                     模型和本机探测故障测试
tools/                     图标生成、GUI/进程集成 smoke
docs/                      设计、人工验收、验证报告
resources/app.ico          应用图标
config/settings.example.json
requirements.txt / requirements.lock.txt
VPNWatchdog.spec / build.bat
```

设计依据：[Qt 系统代理](https://doc.qt.io/qt-6/qnetworkproxyfactory.html)、[异步网络与传输超时](https://doc.qt.io/qt-6/qnetworkaccessmanager.html)、[Reply 取消与生命周期](https://doc.qt.io/qt-6/qnetworkreply.html)。
