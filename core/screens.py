import core.backend as backend

from textual.app import ComposeResult
from textual.widgets import Header, Footer, ListItem, ListView, Label, Button, Markdown, LoadingIndicator, Input
from textual.containers import Horizontal, Center
from textual import work
from textual.screen import Screen

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
        ("/", "search", "Search"),
        ("escape", "clear_search", "Clear Search"),
    ]

    def __init__(self, articles: list[dict], conn):
        super().__init__()
        self.articles = articles
        self.all_articles = articles
        self.conn = conn

        self.show_sources = backend.load_display_pref("show_sources", default=True)
        self.show_timestamps = backend.load_display_pref("show_timestamps", default=False)

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(placeholder="Search articles... (/ to focus, esc to clear)", id="search-bar")
        yield ListView(
            *[self.make_item(a) for a in self.articles]
        )
        yield Footer()

    def action_search(self):
        self.query_one("#search-bar").focus()

    def action_clear_search(self):
        search = self.query_one("#search-bar", Input)
        search.value = ""
        self.query_one(ListView).focus()
        self.refresh_list(self.all_articles)

    def on_input_changed(self, event: Input.Changed) -> None:
        query = event.value.lower().strip()
        if not query:
            self.refresh_list(self.all_articles)
            return
        filtered = [
            a for a in self.all_articles
            if query in a["title"].lower()
            or query in a["summary"].lower()
            or query in a["source"].lower()
        ]
        self.refresh_list(filtered)

    def make_item(self, a: dict) -> ListItem:
        colors = {"tech": "cyan", "world": "yellow", "music": "magenta"}
        color = colors.get(a["category"], "white")

        parts = []
        if self.show_sources:
            parts.append(f"[{color}][[{a['source']}]][/{color}]")
        if self.show_timestamps:
            parts.append(f"[dim]{a.get('published', '')[:16]}[/dim]")
        title = f"[dim]{a['title']}[/dim]" if a.get("read", 0) else a["title"]
        parts.append(title)

        return ListItem(Label(" ".join(parts)))

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
    
    def apply_read_filter(self, unread_only: bool):
        if unread_only:
            filtered = [a for a in self.all_articles if not a.get("read", 0)]
        else:
            filtered = self.all_articles
        self.refresh_list(filtered)
        state = "unread only" if unread_only else "all articles"
        self.notify(f"Showing {state}")

    def sort_by(self, key: str):
        if key == "relevance":
            self.articles = sorted(self.all_articles, key=lambda a: a.get("relevance", 0), reverse=True)
        elif key == "date":
            self.articles = sorted(self.all_articles, key=lambda a: a.get("published", ""), reverse=False)
        elif key == "source":
            self.articles = sorted(self.all_articles, key=lambda a: a.get("source", ""))
        backend.save_display_pref("sort", key)
        self.refresh_list(self.articles)
        self.notify(f"Sorted by {key}.")

    def toggle_source_tags(self):
        self.show_sources = not self.show_sources
        backend.save_display_pref("show_sources", self.show_sources)
        self.refresh_list(self.articles)
        self.notify(f"Source tags {'shown' if self.show_sources else 'hidden'}.")

    def toggle_timestamps(self):
        self.show_timestamps = not self.show_timestamps
        backend.save_display_pref("show_timestamps", self.show_timestamps)
        self.refresh_list(self.articles)
        self.notify(f"Timestamps {'shown' if self.show_timestamps else 'hidden'}.")

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