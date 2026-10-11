import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="VPN Watchdog — 多目标国际网络监测")
    parser.add_argument("--cli", action="store_true", help="命令行持续监测")
    parser.add_argument("--once", action="store_true", help="命令行检测一轮")
    parser.add_argument("--dashboard", action="store_true", help="启动时显示 Dashboard")
    parser.add_argument("--data-dir", type=Path, help="配置和日志目录")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--settings-json", help=argparse.SUPPRESS)
    parser.add_argument("--revision", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker or args.cli or args.once:
        from utils.streams import attach_worker_streams
        attach_worker_streams()
    from utils.config import Settings, data_dir, load
    if args.worker:
        from PySide6.QtCore import QCoreApplication
        from core.probe_worker import ProbeWorker, print_round
        from core.worker_control import WorkerControl
        app = QCoreApplication(sys.argv[:1])
        settings = Settings(**json.loads(args.settings_json)).validate()
        worker = ProbeWorker(settings, print_round, status_publish=lambda event: print(json.dumps(event), flush=True),
                             revision=args.revision)
        control = WorkerControl(worker.handle_command)
        print(json.dumps({"event": "ready"}), flush=True)
        return app.exec()
    directory = args.data_dir or data_dir()
    try:
        settings = load(directory / "config" / "settings.json")
    except (OSError, ValueError, TypeError) as error:
        if args.cli or args.once:
            print(f"配置错误: {error}", file=sys.stderr)
        else:
            from PySide6.QtWidgets import QApplication, QMessageBox
            app = QApplication(sys.argv[:1])
            QMessageBox.critical(None, "VPN Watchdog 配置错误", f"{directory / 'config' / 'settings.json'}\n{error}")
        return 2
    if args.cli or args.once:
        from core.cli import run
        return run(settings, directory, args.once)
    from ui.application import run
    return run(settings, directory, args.dashboard)


if __name__ == "__main__":
    raise SystemExit(main())
