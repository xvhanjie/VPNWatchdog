# 逐模块运行与排查

以下命令在项目根目录使用 `.venv\Scripts\python.exe` 执行。首轮架构见 `DESIGN.md`，第二轮逐文件变更与完整测试命令见 [ROUND2.md](ROUND2.md)。

| 模块 | 完成内容 | 如何运行/测试 | 正常结果 | 失败如何排查 |
|---|---|---|---|---|
| NetworkMonitor / ProbeWorker / WorkerControl | 1～3 目标异步请求、期限、故障分类、双向 IPC、同一 QTimer 实时更新、子进程看门狗 | `python main.py --once --data-dir .runtime-cli`；`python tools/smoke_dynamic.py` | 每个目标有 HTTP/RTT/错误；配置更新后 PID 和调度器保持相同；首次确认状态 UNKNOWN 正常 | 查目标错误码，再查系统代理/TUN 和 logs；MONITOR_TIMEOUT 检查 PAC/WORKER 诊断 |
| StateManager | 动态多数门槛、防抖、掉线/恢复去重、目标变更重置 | `python -m unittest tests.test_state_manager -v` | 单次 Timeout 不 Down；第 3 轮全失败 Down；第 2 轮达到门槛 Recovery | 门槛分别为 1/1、2/2、2/3；有效 HTTP 响应与成功指标分开 |
| Windows Notification | 原生系统通知、事件去重、质量/探测器错误冷却、额外系统声音 | `python -m unittest tests.test_notifier -v`；实际启动后托盘 Test Notification | 自动化不发送真实通知；桌面测试出现明确的“通知测试”，不改变网络状态 | 检查 Windows 通知/勿扰/声音设置、软件通知开关、日志 SYSTEM_NOTIFICATION_UNAVAILABLE |
| System Tray | 状态颜色、菜单、打开窗口、暂停、检测、设置、工作模式、退出 | `python main.py`；双击/右键托盘图标 | 默认隐藏窗口；颜色跟随已确认状态；Exit 完全结束 | 查隐藏图标区域；用 --dashboard 打开；无托盘时主窗口保持可见 |
| Dashboard | 当前/观测状态、请求 RTT、HTTP 失败率、目标表、有限近期记录、本次运行计数 | `python main.py --dashboard`；`python tools/smoke_gui.py` | 界面能响应，超时不阻塞；离屏截图有明确模拟数据说明 | 检查 Qt 平台/DLL；模拟截图无字体时检查 C:/Windows/Fonts/msyh.ttc；真实界面使用系统字体 |
| Config / Settings | 3～30 秒整数、五选 1～3、原子保存、迁移修复与备份、临时工作模式 | `python -m unittest tests.test_config -v`；`python -m unittest tests.gui_cases -v` | 保存实时应用，重启读相同普通周期与目标；GUI 阻止非法选择 | 查 settings.json、settings.json.bak 和 CONFIG_REPAIRED 日志；不可写时修复只在内存生效 |
| Logger | 每轮状态和每目标结果、异常/恢复时长、日志轮转 | CLI/GUI 运行后查看 data-dir/logs/network.log | 每轮有 STATE 与 TARGET 行；轮转最多约 12 MB | 检查目录写权限和指定数据目录；不同 GUI/CLI 实例不要共享日志目录 |
| 进程稳定性 | 崩溃重启、监测器异常区分、有界退出 | `python tools/smoke_monitor.py` | 三轮真实结果，中间有错误诊断，最终 Monitor smoke OK 且无遗留子进程 | 查代理和 stderr WORKER 行；若完全无输出检查 Python/EXE 路径和运行库 |
| Packaging | 生成图标、单文件无控制台 EXE、独立 Python 运行、冻结进程输出管道 | `build.bat`；`python tools/smoke_packaged.py` | dist/VPNWatchdog.exe；Frozen smoke OK，自然退出 | 查看 PyInstaller 警告；spec 必须使用受控 DLL 搜索路径；不要带入外部 UCRT/同名 OpenSSL |

完整环境故障清单与长期运行步骤见 `TESTING.md`。真实网络依赖当前环境，不应通过修改测试断言去掩盖目标失败。未人工执行的用例在 `VALIDATION.md` 中明确保留为待验收。
