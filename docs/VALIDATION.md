# MVP 验证记录

> 这是 2026-10-10 的首轮历史记录，文件大小、哈希及测试数属于当时构建。2026-10-11 第二轮构建与验证见 [ROUND2.md](ROUND2.md)。

日期：2026-10-10，Asia/Shanghai。构建与实测机器：Windows 11 x64（10.0.26300），Python 3.12.14，PySide6 Essentials 6.12.0，PyInstaller 6.22.3。

## 已完成

1. `python -m unittest discover -s tests -v`：**23 项通过**，约 1.55 秒。覆盖配置持久化/拒绝非法输入；单次超时不掉线；连续失败/恢复；事件时长；部分可达/HTTP 限制；质量防抖；本机断网分类；睡眠间隙；内部错误；通知禁用/事件去重/冷却；临时 HTTP 服务上的并行期限、302/403/429 与 GET 正文限制。
2. `python main.py --once --data-dir .runtime-cli`：通过当前系统网络路径的实际探测。Google 204、Cloudflare 200、GitHub 200。完整新连接请求耗时明显高于 ping，约 0.7–1.6 秒，所以本机当前观测为 HIGH_LATENCY；阈值允许修改。
3. `python tools/smoke_gui.py`：离屏 GUI 启动、显示、暂停/恢复、工作模式、模拟事件处理及退出通过。预览在 `docs/dashboard-preview.png`，明确标注模拟数据。离屏字体由工具加载系统微软雅黑；实际 Windows UI 使用系统字体。
4. `python tools/smoke_monitor.py`：通过。收到真实结果后主动结束探测进程，确认自动重启；再触发看门狗，确认 UNKNOWN 诊断后重新收到结果；最后有界回收，子进程 ID 为 0。所有三次真实探测均达到 quorum。
5. `python -m PyInstaller --clean --noconfirm VPNWatchdog.spec`：构建成功。最终 `dist/VPNWatchdog.exe` 为 **37,902,911 字节（约 36.1 MiB）**。
6. `python tools/smoke_packaged.py`：最终单文件 EXE 通过。无控制台程序的父进程/探测子进程输出管道正常，三目标结果正常传回，一轮后自然退出。
7. 最终打包实测（15:27:32，UTC+8）：GitHub 200 / 813 ms，Cloudflare 200 / 1047 ms，Google 204 / 1422 ms；`STATUS=UNKNOWN observed=HIGH_LATENCY consecutive=1` 符合第一轮防抖语义。
8. 测试结束后检查 EXE 进程，无遗留 VPNWatchdog 或诊断 EXE 进程。

最终 EXE SHA-256：

```text
8DEC3A97FCBAF307338C5EAAB20B8F5B2AE27C4FC8825BC02177DCB0C838CAA2
```

## 实测发现并修正

- Cloudflare trace 的 HEAD 返回 404，改为有正文上限的小型 GET，复测返回 200。
- 首次打包引入构建环境 PATH 上其他工具的运行库，QtCore 加载发生 DLL procedure 错误。spec 限定 DLL 搜索路径并排除额外 UCRT 后，清理重建并实测通过。未修改系统 DLL 或全局 PATH。
- PyInstaller windowed 程序标准输出可能为 None；探测进程专门恢复继承的 Windows 输出句柄，最终冻结版本成功传回 JSON。

## 仍需人工验收

Windows 10、无 Python 的干净 Windows 11；通知实际桌面显示与声音/勿扰模式；物理网线/Wi-Fi 开关、VPN/节点切换、真实代理端口关闭、DNS/证书故障；睡眠唤醒、数小时乃至数周后台运行、CPU 和全部进程合计内存。自动化模拟验证不替代这些环境测试。步骤见 `TESTING.md`。

MVP 未提供 ICMP 丢包率、DNS/TCP 分段耗时、图表、今日持久统计或自动启动，未将这些功能算作已完成。
