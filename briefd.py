#
#   COPYRIGHT (C) 2026 Nico Rajala. All rights reserved.
#

import backend

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListItem, ListView, Label, Button, Markdown, LoadingIndicator
from textual.containers import Horizontal, Center
from textual import work
from textual.screen import Screen

console = Console()

# display
class ArticleScreen(Screen):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def __init__(self, article: dict, conn):
        super().__init__()
        self.article = article
        self.conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        yield LoadingIndicator()
        yield Center(Markdown("", id="article-md"))
        yield Horizontal(
            Button("Like", id="like", variant="success"),
            Button("Dislike", id="dislike", variant="error"),
            id="actions"
        )
        yield Footer()

    def on_mount(self):
        self.fetch_content()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "like":
            backend.update_topic_scores(self.conn, self.article, liked=True)
            self.notify("Got it, more like this.")
        elif event.button.id == "dislike":
            backend.update_topic_scores(self.conn, self.article, liked=False)
            self.notify("Got it, less like this.")
        elif event.button.id == "back":
            self.app.pop_screen()

    @work(thread=True)          # <- to make sure the ui doesn't freeze :(
    def fetch_content(self):
        content = backend.fetch_article_content(self.article["url"])
        markdown = f"# {self.article['title']}\n\n*{self.article['source']} — {self.article['published']}*\n\n{content}\n\n[Open in browser]({self.article['url']})"

        self.app.call_from_thread(self.update_content, markdown)

    def update_content(self, markdown: str):
        self.query_one(LoadingIndicator).display = False
        self.query_one(Markdown).update(markdown)

class FeedScreen(Screen):
    BINDINGS = [
        ("^q", "quit", "Quit"),
        ("^r", "reload", "Reload"),
    ]

    def __init__(self, articles: list[dict], conn):
        super().__init__()
        self.articles = articles
        self.conn = conn

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(
            *[self.make_item(a) for a in self.articles]
        )
        yield Footer()

    def make_item(self, a: dict) -> ListItem:
        colors = {"tech": "cyan", "world": "yellow", "music": "magenta"}
        color = colors.get(a["category"], "white")
        source_tag = f"[{color}][[{a['source']}]][/{color}]"

        # dim if already read
        title = f"[dim]{a['title']}[/dim]" if a["read"] else a["title"]
        return ListItem(Label(f"{source_tag} {title}"), id=f"item_{self.articles.index(a)}")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        index = event.list_view.index
        article = self.articles[index]

        # mark read in db and update label immediately
        backend.mark_as_read(self.conn, article["id"])
        article["read"] = 1
        colors = {"tech": "cyan", "world": "yellow", "music": "magenta"}
        color = colors.get(article["category"], "white")
        source_tag = f"[{color}][[{article['source']}]][/{color}]"
        read_tag = "- READ!"
        event.item.query_one(Label).update(f"{source_tag} [dim]{article['title']} {read_tag}[/dim]")
        self.app.push_screen(ArticleScreen(article, self.conn))

    @work(thread=True)
    def action_reload(self):
        self.app.call_from_thread(self.notify, "Refreshing feeds...")
        config = backend.load_config(backend.CONFIG_PATH)
        articles = backend.fetch_all(config["sources"], self.conn, force=True)
        self.app.call_from_thread(self.refresh_list, articles)

    def refresh_list(self, articles: list[dict]):
        self.articles = articles
        lv = self.query_one(ListView)
        lv.clear()
        for a in articles:
            lv.append(self.make_item(a))
        self.notify("Feeds refreshed.")

# main
class Briefd(App):
    CSS = """
        ListView {
            height: 1fr;
        }
        ListItem {
            padding: 1 1;
            height: 3;
        }
        ListItem:focus-within {
            background: $accent;
            color: $text;
        }
        #article-md {
            align: center top;
            width: 70%;
        }
        #actions {
            height: 3;
            dock: bottom;
            padding: 0 1;
            margin-bottom: 3;
        }
        #actions Button {
            margin: 0 1;
        }
    """

    def on_mount(self):
        self.conn = backend.get_db()
        config = backend.load_config(backend.CONFIG_PATH)
        articles = backend.fetch_all(config["sources"], self.conn)
        self.push_screen(FeedScreen(articles, self.conn))

    def on_unmount(self):
        self.conn.close()

if __name__ == "__main__":
    app = Briefd()
    app.run()