#
#   COPYRIGHT (C) 2026 Nico Rajala. All rights reserved.
#

import core.backend as backend
import core.screens as screens
import sys
import argparse

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

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

    def on_mount(self):
        self.conn = backend.get_db()
        config = backend.load_config(backend.CONFIG_PATH)
        articles = backend.fetch_all(config["sources"], self.conn)
        self.push_screen(screens.FeedScreen(articles, self.conn))

    def on_unmount(self):
        self.conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="briefd -- terminal news reader")
    parser.add_argument("--digest", action="store_true", help="Print daily digest and exit")
    parser.add_argument("--limit", type=int, default=10, help="Number of articles in digest")
    args = parser.parse_args()

    if args.digest:
        run_digest(args.limit)
    else:
        app = Briefd()
        app.run()