# 第二轮：自定义周期与监测网站

验证日期：2026-10-11，Asia/Shanghai。沿用现有 Python / PySide6、独立探测进程、纯 Python 状态机、Windows 托盘通知和轮转日志，没有新建项目或重写主界面。本轮代码和 EXE 已通过下面的自动化与集成测试；实际 VPN 开关、桌面通知与长期运行仍列为人工待验收。

## 逐文件变更

| 文件 | 本轮修改及目的 |
|---|---|
| `utils/config.py` | 统一五个 TARGETS 和请求策略；校验 3～30 秒/1～3 个目标；增加配置转换、旧字段迁移、异常修复、原文件备份与原子保存。内部保留 interval_s，JSON 使用 check_interval，减少旧模块改动。 |
| `config/settings.example.json` | 改用 check_interval，新增默认 selected_targets；保留既有通知、超时、防抖、延迟参数。 |
| `ui/settings_window.py` | 周期改为 QSpinBox；五个 Checkbox 实时阻止第 4/5 个和取消最后一个；显示数量/原因；恢复默认；保存并应用。 |
| `core/worker_control.py`（新增） | 一个阻塞 stdin 读取线程，通过 Qt 信号将 JSON 控制命令交给探测进程事件循环；EOF 停止进程，无额外轮询调度器。 |
| `core/probe_worker.py` | 同一个 QTimer 接收 configure/check/stop；实时 setInterval；选定目标和轮次版本；目标变化等当前轮结束再运行新组合；ChatGPT/YouTube 使用 HTTP 可达策略。 |
| `core/network_monitor.py` | 通过既有 QProcess 输入管道发送命令；启动后同步最新设置；检测忙状态；配置确认；忽略旧目标版本结果；沿用看门狗和重启。 |
| `main.py` | 探测入口接入控制通道、ready 状态和目标版本参数；GUI/CLI 入口沿用。 |
| `utils/streams.py` | 无控制台 EXE 恢复继承的 stdin，保留 stdout/stderr，支持冻结版本双向 IPC。 |
| `core/models.py` | Probe 增加响应说明 note；Round 增加 revision；旧格式默认值兼容。延迟和失败率仍由每轮实际结果计算。 |
| `core/state_manager.py` | 多数门槛 N//2+1 同时用于分类与恢复；2/3 成功允许 HEALTHY；增加目标变更完整证据重置；恢复连续轮数正确显示。 |
| `ui/application.py` | 普通周期与工作模式分别处理；周期更改保留状态；目标集合变化重置状态/当前数据/界面近期记录，保留磁盘日志；立即检测沿用进程且忙时阻止；配置/模式/范围变更日志。 |
| `ui/main_window.py` | 表格按当前目标生成；实际数量、失败率、失败目标、受限响应、连续轮数；监测范围显示；仅顺序变化时按名称保留 RTT。 |
| `ui/tray.py` | 菜单显示实际检测周期/工作模式；目标变化重置托盘状态；沿用原菜单与系统通知路径。 |
| `core/cli.py` | 输出服务响应说明和配置修复日志，探测当前 selected_targets。 |
| `utils/logger.py` | 每个目标记录 note，帮助区分网络失败与服务限制。 |
| `build.bat` | 打包前分别运行核心和 GUI 测试，避免同一进程混用 QCoreApplication/QApplication。 |
| `tests/test_config.py` | 扩展任意周期、旧配置、缺字段、坏 JSON、越界、未知/重复/过多目标、备份和落盘测试。 |
| `tests/test_scheduler.py`（新增） | 连续周期修改复用同一 QTimer；忙时定时/手动检测均跳过。 |
| `tests/test_network_monitor.py`（新增） | 手动连点只发一次命令、周期更新不换进程、不丢启动期间设置、丢弃旧目标结果。 |
| `tests/test_probe_worker.py` | ChatGPT/YouTube 策略接受 302/403/429；4.2 秒长请求与 3 秒周期/手动触发不能重叠；保留原错误、正文限制和并行测试。 |
| `tests/test_state_manager.py` | 覆盖 1/2/3 目标分类与 Down/Recovery、防旧范围事件、成功 RTT 中位数、动态失败率和部分失败。 |
| `tests/gui_cases.py`（新增） | 七项设置/控制器/动态表格测试，覆盖 0/4/5 个目标、工作模式、范围变化、顺序变化和立即检测忙状态。 |
| `tools/probe_candidates.py`（新增） | 开发诊断一次探测全部五个候选，输出真实 HTTP、RTT 和错误；正常产品依旧最多三个。 |
| `tools/smoke_dynamic.py`（新增） | 真实 NetworkMonitor 进程十次周期更新及四种目标组合，核对相同 PID 与 scheduler_id。 |
| `tools/smoke_frozen_control.py`（新增） | 最终 EXE stdin 控制、十次周期、目标切换、同一调度器和 graceful stop。 |
| `tools/smoke_gui.py` | 沿用原模拟故障/恢复/暂停/工作模式渲染；增加两目标主界面和设置窗口预览。 |
| `README.md`、`docs/MODULE_GUIDE.md`、`docs/TESTING.md` | 更新当前配置、动态门槛、测试入口和人工步骤。 |
| `docs/DESIGN.md`、`docs/VALIDATION.md` | 首轮背景/历史证据保留，标注已由本轮说明更新。 |
| `docs/ROUND2.md`（新增） | 本轮逐文件交付、机制、实测和验收清单。 |
| `dist/VPNWatchdog.exe` | 重新构建并执行冻结版本集成验证。 |

未改动网络路由/系统代理、VPN 控制、通知实现和单实例策略。已有 notifier 用例继续通过。

## 配置与实时生效

新增持久化字段如下，其余参数保持原默认值：

```json
{
  "check_interval": 8,
  "selected_targets": ["GitHub", "ChatGPT", "YouTube"]
}
```

默认文件位于 `%LOCALAPPDATA%\VPNWatchdog\config\settings.json`；使用 `--data-dir` 时改为该目录下 `config\settings.json`。

保存先严格校验并原子替换 JSON，然后向当前探测 QProcess 发送 configure。探测进程在自己的 Qt 事件循环上调用原 QTimer 的 setInterval，不新建自动检测计时器，不重启进程。改变运行中的计时器间隔会按新周期重新计时，行为依据 [Qt QTimer 文档](https://doc.qt.io/qt-6/qtimer.html#interval-prop)。请求期限计时器、看门狗和 GUI 时钟分别承担期限/健康检查/显示职责，不是额外的自动检测调度器。

普通周期始终保存在 settings.check_interval（内部兼容字段 interval_s）。工作模式临时覆盖实际周期为 3 秒，关闭后恢复普通周期。例如 15 → 3 → 15。工作模式期间保存普通周期 12 秒，实际仍为 3 秒，关闭后变为 12 秒。工作模式开关不持久化，重新启动按普通模式运行。只修改周期或模式不清空状态和证据。

探测进程 run_round 首先检查 active；当前轮未结束时，自动/手动请求都跳过。主进程 request_check 同时检查 is_checking/ready，发出手动命令后立即标记忙；按钮显示“正在检测中…”且禁用，快速连点不会积累任务。目标集合改变时当前在途请求可完成，但其 revision 已过期，主进程忽略它；随后一轮只探测新组合。不并发运行旧、新组合。

目标集合改变时重置确认状态、连续计数、临时观测、RTT、结果缓存与界面近期记录。磁盘历史日志保留，记录 MONITORING_SCOPE_CHANGED；旧组合未结束事件不能由新组合发 RECOVERED。仅调整同一集合顺序保留状态和 RTT。本次运行累计事件/Timeout 数仍保留，代表跨范围的运行总计。

加载旧 interval_s 时保留其合法周期并迁移字段；缺失周期使用 5，缺失目标使用默认三站。整数越界夹到 3～30，错误类型恢复默认；目标筛选合法名称、去重后取前三个，空集合恢复默认。损坏 JSON 也能启动。每次迁移/修复前将当前原字节写入 settings.json.bak（保留最近一次修复前原文件），并写 CONFIG_REPAIRED；保存权限不足则明确记录修复仅在内存生效。

## 判定与轻量请求

| 启用目标数 | 本轮 HEALTHY 门槛（RTT 低于阈值） | 部分成功 | 全部真正失败 |
|---:|---|---|---|
| 1 | 1/1 | 无部分成功情况 | 0/1 进入连续失败计数 |
| 2 | 2/2 | 1/2 为 UNSTABLE | 0/2 进入连续失败计数 |
| 3 | 2/3 或 3/3 | 1/3 为 UNSTABLE；2/3 注明异常目标 | 0/3 进入连续失败计数 |

这是 observed 分类；确认状态仍用原防抖：默认连续 3 轮全失败才 Down，连续 2 轮达到动态门槛才恢复。高延迟规则保留。连续轮数与本轮成功数量分别显示。

RTT median 只用成功目标；例如 180、220、Timeout 得到 200 ms。失败率为失败数/N，例如 1/2=50.0%，1/3=33.3%。

| 目标 | 地址 | 请求/成功策略 |
|---|---|---|
| Google | https://www.google.com/generate_204 | HEAD，204 |
| GitHub | https://github.com/ | HEAD，200 |
| Cloudflare | https://www.cloudflare.com/cdn-cgi/trace | 小型 GET，200，读取正文超过 4096 字节中止 |
| ChatGPT | https://chatgpt.com/ | HEAD，有效 HTTPS HTTP 200～599 表示路径可达 |
| YouTube | https://www.youtube.com/ | HEAD，同上，不下载页面正文或视频 |

ChatGPT/YouTube 的 301/302/403/429/5xx 会显示“网络可达（HTTP …）”，附说明；不保证服务功能正常。DNS、连接拒绝、代理、请求超时、TLS 校验等错误仍失败。所有目标不跟随重定向、不忽略证书，保留请求期限与读取上限。

## 已执行验证

环境：Windows 11 x64 10.0.26300、Python 3.12.14、PySide6 Essentials 6.12.0、PyInstaller 6.22.3。

| 检查 | 结果与范围 |
|---|---|
| 核心 unittest | **39 项通过**，约 5.67 秒；包含本机真实长请求 4.2 秒与 3 秒周期/手动触发重叠保护。 |
| 单独 GUI unittest | **7 项通过**，周期 3/5/8/15/30、默认恢复、选择 0/4/5 阻止、模式/状态/范围/缓存/忙状态/持久化。 |
| 离屏 GUI smoke | 模拟故障/恢复、暂停、工作模式通过；默认三站、ChatGPT+YouTube 两站和设置窗口渲染成功，并检查了预览。 |
| 五候选真实 HTTPS | Google 204，其余 200；全站 RTT 约 187～375 ms，为当时环境样本。 |
| 源码动态进程 | 同 PID 39852 和同 scheduler_id；更新 3/5/8/15/30/5/10/3/20/8 秒；完成 ChatGPT、ChatGPT+YouTube、默认三站、GitHub+ChatGPT+YouTube 四种组合。全部有正确 HTTP 返回。 |
| 崩溃/看门狗 smoke | 三轮真实结果均 3/3，强制结束测试子进程及模拟监督超时后自动恢复；有界退出、无遗留探测子进程。 |
| PyInstaller | 最终源码构建成功，EXE **37,914,704 字节（约 36.2 MiB）**。 |
| 冻结实时控制 smoke | 十次周期更新保持同调度器，切换单/双/三目标，ChatGPT/YouTube/GitHub 均 HTTP 200，stop 正常退出。 |
| 冻结主程序 smoke | 14:18:22 UTC+8，Google 204/203 ms、Cloudflare 200/172 ms、GitHub 200/187 ms；首轮 UNKNOWN / observed=HEALTHY / consecutive=1；自然退出。 |
| EXE 进程检查 | 集成测试后只读查询，没有遗留 VPNWatchdog.exe 进程。 |

周期集成测试核对工作进程 QTimer 的 interval 和对象身份，没有逐个等待 30 秒周期多轮运行；长请求测试确实跨过 3 秒自动触发。长期资源增长和实际桌面通知依然属于人工验收。

预览使用模拟数据：[双目标主界面](dashboard-selected-preview.png)、[设置窗口](settings-preview.png)、[默认三目标](dashboard-preview.png)。

最终 EXE SHA-256：

```text
11147538F2923142A7C124CF8629C3BBE5A63F66C56D4AE6ABBDFD2E0D2239A1
```

## 完整测试命令

在项目根目录执行。前三条使用本机服务/模拟数据；后续联网 smoke 依赖当前系统代理/TUN 与外部服务，不会关闭 VPN。

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

`build.bat` 会重复核心/GUI 测试再构建；若只需要构建使用 `.\.venv\Scripts\python.exe -m PyInstaller --noconfirm VPNWatchdog.spec`。GUI 测试单独运行，以免 Qt Application 单例类型冲突。

## 人工验收 checklist（待执行）

- [ ] 启动 `dist\VPNWatchdog.exe --dashboard`；默认 5 秒和 Google/GitHub/Cloudflare；托盘正常。
- [ ] 输入 3、5、8、15、30 秒，保存；主界面/托盘立即显示实际周期，无需重启。反复修改 5→10→3→20→8，观察几轮，频率不累积；当前状态/轮数不因周期变化清空。
- [ ] 分别选择 ChatGPT、ChatGPT+YouTube、默认三站、GitHub+ChatGPT+YouTube；主表与新记录只含启用目标。取消最后一项或选择第 4/5 项被阻止；恢复默认回到 5 秒/默认三站。
- [ ] 普通 15 秒开启工作模式显示 3 秒，关闭恢复 15 秒；工作模式中将普通周期改 12，实际仍 3，关闭变 12。
- [ ] 检测尚未结束时反复点立即检测，按钮禁用或提示忙，界面可响应，无新探测组堆积。暂停后无新检测，恢复和退出正常。
- [ ] 保存普通周期 8 秒、GitHub+ChatGPT+YouTube；打开 `%LOCALAPPDATA%\VPNWatchdog\config\settings.json` 核对两个字段；通过“退出”结束后重启，设置和主界面恢复该组合/8 秒。自定义 data-dir 则检查相应路径。
- [ ] 用独立测试 data-dir 放旧配置或手动设周期 1/100、空目标/过多目标；启动得到 3/30 或默认/合法前三站，原内容位于 settings.json.bak，日志出现 CONFIG_REPAIRED。
- [ ] 目标组合变化后状态回 UNKNOWN、RTT/连续证据/界面记录清空；磁盘历史日志保留。仅改周期不清空；旧组合故障不能被新组合错误报恢复。
- [ ] 在不影响重要任务时实际关闭 VPN：仅在全部启用目标真正失败连续达到阈值后 Down；重连后达到动态门槛连续两轮才一次 Recovery。先分别对 1/2/3 个目标执行。若直连可达则不应假报 Down。
- [ ] 观察 ChatGPT/YouTube 返回 403/重定向时，界面说明网络可达，不能假报 VPN_DOWN。三目标一个失败时仍可 HEALTHY 并注明异常，失败率 33.3%。
- [ ] 用托盘 Test Notification 核对实际 Windows 通知和声音；检查勿扰模式；再观察真实 Down/Recovery 去重。
- [ ] 持续运行数小时后记录主程序、onefile 引导和探测进程合计 CPU/内存/线程；退出后无残留。睡眠唤醒、Windows 10/干净机器与 24～72 小时测试参照 [TESTING](TESTING.md)。

以上人工项未经本轮自动化替代；未验收前不宣称全部功能验收或长期稳定性完成。
