import time
import sys
import os
import argparse

from datetime import datetime
from pathlib import Path

def get_notifier():
    try:
        from plyer import notification
        return notification
    except ImportError:
        return None

def send_notification(title: str, message: str):
    notifier = get_notifier()
    if notifier:
        try:
            notifier.notify(
                title=title,
                message=message[:256],
                app_name="briefd",
                timeout=10,
            )
        except Exception as e:
            print(f"[briefd daemon] notification failed: {e}")
    else:
        print(f"[briefd daemon] {title}: {message}")

def run_daemon(update_hours: float):
    import core.backend as backend

    print(f"[briefd daemon] started, updating every {update_hours}h")
    print(f"[briefd daemon] PID: {os.getpid()}")

    pid_file = backend.APP_DIR / "daemon.pid"
    pid_file.write_text(str(os.getpid()))

    try:
        while True:
            try:
                print(f"[briefd daemon] fetching at {datetime.now().strftime('%H:%M:%S')}")
                conn = backend.get_db()
                config = backend.load_config()
                articles = backend.fetch_all(config["sources"], conn, force=True)

                # get top 3 most relevant unread articles
                unread = [a for a in articles if not a.get("read", 0)]
                top = sorted(unread, key=lambda a: a.get("relevance", 0), reverse=True)[:3]

                if top:
                    title = f"briefd — {len(unread)} unread articles"
                    body = "\n".join(f"• {a['title'][:60]}" for a in top)
                    send_notification(title, body)
                else:
                    print("[briefd daemon] no new articles to notify about")

                conn.close()

            except Exception as e:
                print(f"[briefd daemon] error during update: {e}")

            time.sleep(update_hours * 3600)

    except KeyboardInterrupt:
        print("[briefd daemon] stopped.")
    finally:
        if pid_file.exists():
            pid_file.unlink()

def stop_daemon():
    import core.backend as backend
    pid_file = backend.APP_DIR / "daemon.pid"
    if not pid_file.exists():
        print("No daemon running.")
        return
    pid = int(pid_file.read_text())
    try:
        if sys.platform == "win32":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
            ctypes.windll.kernel32.TerminateProcess(handle, -1)
            ctypes.windll.kernel32.CloseHandle(handle)
        else:
            os.kill(pid, 15)  # SIGTERM
        pid_file.unlink()
        print(f"Daemon stopped (PID {pid}).")
    except Exception as e:
        print(f"Failed to stop daemon: {e}")
        pid_file.unlink()

def daemon_status():
    import core.backend as backend
    pid_file = backend.APP_DIR / "daemon.pid"
    if not pid_file.exists():
        print("Daemon is not running.")
        return
    pid = int(pid_file.read_text())

    try:
        if sys.platform == "win32":
            import ctypes
            handle = ctypes.windll.kernel32.OpenProcess(0x400, False, pid)
            if handle:
                print(f"Daemon is running (PID {pid}).")
                ctypes.windll.kernel32.CloseHandle(handle)
            else:
                print("Daemon PID file exists but process is dead.")
                pid_file.unlink()
        else:
            os.kill(pid, 0)  # signal 0 checks if process exists
            print(f"Daemon is running (PID {pid}).")
    except ProcessLookupError:
        print("Daemon PID file exists but process is dead.")
        pid_file.unlink()