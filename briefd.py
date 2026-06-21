#
#   COPYRIGHT (C) 2026 Nico Rajala. All rights reserved.
#

import core.backend as backend
import core.screens as screens
import os
import sys
import argparse

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from pathlib import Path

from core.commands import BriefdCommands, DENSITY_OPTIONS

from textual.app import App

console = Console()

def run_digest(limit: int = 10):
    console = Console()
    conn = backend.get_db()
    config = backend.load_config()

    backend.fetch_all(config["sources"], conn)
    articles = backend.get_digest(conn, limit)

    console.print("\n[bold cyan]briefd - daily digest[/bold cyan]")
    console.print(f"[dim]Top {len(articles)} articles from the last 24 hours\n[/dim]")

    for i, a in enumerate(articles, 1):
        bar_len = min(int(a["relevance"] * 2 + 3), 10) if a["relevance"] != 0 else 0
        relevance_bar = "#" * bar_len + "-" * (10 - bar_len)

        console.print(Panel(
            f"[bold]{a['title']}[/bold]\n"
            f"[dim]{a['source']} -- {a['published']}[/dim]\n\n"
            f"{a['summary'][:300]}{'...' if len(a['summary']) > 300 else ''}\n\n"
            f"[dim]relevance: [{relevance_bar}][/dim]\n"
            f"{a['url']}",
            title=f"[cyan]#{i}[/cyan]",
            border_style="cyan" if a["relevance"] > 0 else "dim"
        ))

    conn.close()

# main
class Briefd(App):
    CSS_PATH = "briefd.css"
    COMMANDS = App.COMMANDS | {BriefdCommands}

    def on_mount(self):
        self.conn = backend.get_db()
        config = backend.load_config(backend.CONFIG_PATH)

        density = config.get("display", {}).get("density", "medium")
        self.current_density = density
        self.apply_density(density)
        self.show_unread_only = config.get("display", {}).get("unread_only", False)

        articles = backend.fetch_all(config["sources"], self.conn)
        sort_key = backend.load_display_pref("sort", default="relevance")
        if sort_key == "relevance":
            articles = sorted(articles, key=lambda a: a.get("relevance", 0), reverse=True)
        elif sort_key == "date":
            articles = sorted(articles, key=lambda a: a.get("published", ""), reverse=True)
        elif sort_key == "source":
            articles = sorted(articles, key=lambda a: a.get("source", ""))

        self.push_screen(screens.FeedScreen(articles, self.conn))

    def run_command(self, cmd: str):
        actions = {
            "sort_relevance":       lambda: self._feed_action("sort", "relevance"),
            "sort_date":            lambda: self._feed_action("sort", "date"),
            "sort_source":          lambda: self._feed_action("sort", "source"),
            "density_low":          lambda: self.set_density("low"),
            "density_medium":       lambda: self.set_density("medium"),
            "density_high":         lambda: self.set_density("high"),
            "mark_all_read":        self.mark_all_read,
            "toggle_source_tags":   lambda: self._feed_action("toggle_source_tags"),
            "toggle_timestamps":    lambda: self._feed_action("toggle_timestamps"),
            "clear_scores":         self.clear_scores,
            "reload_config":        self.reload_config,
            "show_stats":           self.show_stats,
        }
        action = actions.get(cmd)
        if action:
            action()

    def _feed_action(self, action: str, value: str = None):
        try:
            screen = self.screen_stack[-1]
            if isinstance(screen, screens.FeedScreen):
                if action == "sort":
                    screen.sort_by(value)
                elif action == "toggle_source_tags":
                    screen.toggle_source_tags()
                elif action == "toggle_timestamps":
                    screen.toggle_timestamps()
        except Exception:
            pass

    def mark_all_read(self):
        backend.mark_all_read(self.conn)
        try:
            screen = self.screen_stack[-1]
            if isinstance(screen, screens.FeedScreen):
                for a in screen.all_articles:
                    a["read"] = 1
                screen.refresh_list(screen.articles)
        except Exception:
            pass
        self.notify("Marked all as read.")

    def clear_scores(self):
        backend.clear_topic_scores(self.conn)
        self.notify("Topic scores cleared.")

    def reload_config(self):
        config = backend.load_config()
        self.notify("Config reloaded.")

        try:
            screen = self.screen_stack[-1]
            if isinstance(screen, screens.FeedScreen):
                screen.action_reload()
        except Exception:
            pass

    def show_stats(self):
        from core.screens import StatsScreen
        self.push_screen(StatsScreen(self.conn))

    def set_density(self, level: str):
        self.current_density = level
        self.apply_density(level)
        self.notify(f"Density set to {level}")

        backend.save_display_pref("density", level)

    def apply_density(self, level: str):
        for l in ["low", "medium", "high"]:
            self.remove_class(f"density-{l}")
        self.add_class(f"density-{level}")

    def on_unmount(self):
        self.conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="briefd -- terminal news reader")
    parser.add_argument("--digest", action="store_true", help="Print daily digest and exit")
    parser.add_argument("--limit", type=int, default=10, help="Number of articles in digest")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon")
    parser.add_argument("--kill", action="store_true", help="Stop the running daemon")
    parser.add_argument("--status", action="store_true", help="Check if daemon is running")
    parser.add_argument("--update", type=float, default=1.0, help="Daemon update interval in hours (e.g. 0.5 for 30min)")
    parser.add_argument("--daemon-child", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.digest:
        run_digest(args.limit)
    elif args.kill:
        from core.daemon import stop_daemon
        stop_daemon()
    elif args.status:
        from core.daemon import daemon_status
        daemon_status()
    elif args.daemon:
        from core.daemon import run_daemon, daemon_status
        import core.backend as backend

        pid_file = backend.APP_DIR / "daemon.pid"
        if pid_file.exists():
            print("Daemon is already running. Use --status or --stop.")
            sys.exit(0)

        if sys.platform == "win32":
            import subprocess
            pythonw = Path(sys.executable).parent / "pythonw.exe"
            if not pythonw.exists():
                pythonw = sys.executable
            
            cmd = [str(pythonw), __file__, "--daemon-child", "--update", str(args.update)]
            proc = subprocess.Popen(
                cmd,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"Daemon started in background (PID {proc.pid}).")
        else:
            if os.fork() != 0:
                sys.exit(0)
            run_daemon(args.update)
    elif args.daemon_child:
        # this is the detached background process on windows

        from core.daemon import run_daemon
        import core.backend as backend
        log_path = backend.APP_DIR / "daemon.log"
        sys.stdout = open(log_path, "a", buffering=1)
        sys.stderr = sys.stdout
        run_daemon(args.update)
    else:
        app = Briefd()
        app.run()