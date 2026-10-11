# VPN Watchdog — MVP 设计

> 以下保留首轮设计背景。第二轮在同一架构上增加实时设置控制通道、3～30 秒周期、五选 1～3 目标以及动态多数门槛；当前行为以 [README](../README.md) 和 [ROUND2](ROUND2.md) 为准。下面的固定三目标/固定 quorum 与修改设置清空计数描述属于首轮。

## 需求与技术选择

目标是检测当前 Windows 网络路径能否访问多个国际服务，不检测 VPN 进程，也不能证明流量一定经过 VPN。默认每 5 秒检测 Google、Cloudflare、GitHub，超时 3 秒，至少 2 个成功。针对 Windows 10/11 x64。

Python + PySide6 相对 C++ + Qt 开发与维护成本更低，Qt 提供托盘、系统通知、异步 HTTPS 和系统代理。选择 Python；PyInstaller 生成无需 Python 的 exe。Qt/Python 的内存不能承诺低于 100 MB，应实测主程序和探测进程总占用。

## 架构

`GUI/CLI → NetworkMonitor（进程监督）→ 独立 QtNetwork 探测进程`

`探测结果 → StateManager → Dashboard / Tray / Notifier / RotatingLogger`

模型和状态机是纯 Python；探测需要 QtCore/QtNetwork，完全不依赖 QtWidgets。探测进程并发发起三个请求，主程序通过标准输出 JSON 接收结果。每轮使用新连接管理器，避免复用旧代理连接；系统代理查询可能阻塞，主程序设总看门狗期限并回收失联子进程。探测器故障显示 UNKNOWN，不能冒充 VPN 故障。暂停、修改设置、睡眠间隙会清除连续计数。关闭时先 terminate，再有期限地 kill。

## 判定

- HEALTHY：达到 quorum，延迟中位数低于阈值，所有目标符合预期。
- HIGH_LATENCY：达到 quorum，但延迟中位数 ≥ 300 ms（可配置）。
- UNSTABLE：部分目标失败；或收到 403/429/5xx/非预期状态。HTTP 响应证明连接存在，不能因此判断 VPN_DOWN。
- VPN_DOWN：所有目标都无有效 HTTP 响应，连续 3 轮。TLS 校验失败也不视为有效连接。
- NO_INTERNET：Windows 没有非 loopback 的已连接网卡，连续 3 轮。网卡查询失败返回未知并继续真实探测，不能直接判定断网。
- RECOVERED：已发生掉线后，连续 2 轮达到 quorum；恢复通知仅一次，随后进入稳定质量状态。
- UNKNOWN：启动、暂停或探测器内部错误。

质量变差也需连续 3 轮；质量恢复需 2 轮。掉线期间部分成功不足 quorum 不能关闭故障事件。计数按轮而非目标数，周期不重叠。失败持续时间从第一轮失败开始，用单调时钟计算；睡眠后没有检测的时间不当作失败轮数。

## 工程修正与边界

HTTP RTT 为本次请求总耗时，含 DNS/TCP/TLS/代理；MVP 不虚构分段耗时。HTTP 失败率不能标成 ICMP 丢包率。ICMP 通常不走 HTTP/SOCKS 代理，不能用其失败否决 HTTPS 结果，留到第二阶段作为辅助指标。Google/GitHub 使用 HEAD，不下载正文；Google 预期 204，GitHub 预期 200。实测 Cloudflare trace 对 HEAD 返回 404，因此改用小型 GET，正文最多 4096 字节后主动中止（在途数据可能略多），预期 200。不自动跟随重定向、不忽略 TLS 错误，避免门户页面误判正常。

默认系统代理采用 Qt 的 Windows WinHTTP 查询。支持 Qt 能解析的系统代理和 TUN 路由，不保证所有 PAC/认证代理；监督期限触发会明确报探测器异常。环境变量代理不覆盖 Windows 系统代理。MVP 不设置开机启动、不改变网络/VPN/注册表。

## 迭代顺序

1. 设计与目录。
2. NetworkMonitor + 命令行探测。
3. StateManager + 合成故障测试。
4. Windows 通知与托盘。
5. Dashboard、基础配置、轮转日志。
6. 集成异常验证、PyInstaller 打包与人工验收。

第二阶段：延迟曲线、每日持久统计、CSV、自定义目标/显式代理、声音文件、经用户勾选的开机启动。第三阶段：报告/节点质量，暂不做进程监控。

参考：
- https://doc.qt.io/qt-6/qnetworkproxyfactory.html
- https://doc.qt.io/qt-6/qnetworkaccessmanager.html
- https://doc.qt.io/qt-6/qnetworkreply.html
