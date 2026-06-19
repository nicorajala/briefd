from textual.command import Provider, Hit, Hits, DiscoveryHit
from textual.screen import Screen
from textual.widgets import OptionList, Header, Footer, Label
from textual.widgets.option_list import Option
from textual.app import ComposeResult
from textual.binding import Binding

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from textual.app import App

DENSITY_OPTIONS = {
    "low": 5,
    "medium": 3,
    "high": 2,
}

class SettingsScreen(Screen):
    BINDINGS = [
        Binding("escape", "app.pop_screen", "Back"),
    ]

    SETTINGS = [
        # (label, help, command_name)
        ("UX", [
            ("Sort by: Relevance",          "Sort feed by your personal relevance score",       "sort_relevance"),
            ("Sort by: Date",               "Sort feed by publish date (newest first)",         "sort_date"),
            ("Sort by: Source",             "Group articles by source",                         "sort_source"),
            ("Article Density: Low",        "Spacious list items",                              "density_low"),
            ("Article Density: Medium",     "Default list item height",                         "density_medium"),
            ("Article Density: High",       "Compact list items, more articles visible",        "density_high"),
            ("Mark All as Read",            "Mark every loaded article as read",                "mark_all_read"),
            ("Toggle Source Tags",          "Show/hide [Source] prefix in list",                "toggle_source_tags"),
            ("Toggle Timestamps",           "Show/hide publish date in list items",             "toggle_timestamps"),
        ]),
        ("Data", [
            ("Clear Topic Scores",          "Reset your personal relevance/taste profile",      "clear_scores"),
            ("Reload Config",               "Pick up config.toml changes without restarting",   "reload_config"),
        ]),
        ("Info", [
            ("Stats",                       "(TODO) View your reading stats and taste profile",        "show_stats"),
        ]),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        options = []
        for section, items in self.SETTINGS:
            options.append(Option(f"[bold dim]── {section} ──[/bold dim]", disabled=True))
            for label, help_text, _ in items:
                options.append(Option(f"  {label}\n  [dim]{help_text}[/dim]"))
        yield OptionList(*options, id="settings-list")
        yield Footer()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        # map index back to command, skipping section headers
        flat = []
        for _, items in self.SETTINGS:
            flat.append(None)
            for _, _, cmd in items:
                flat.append(cmd)

        cmd = flat[event.option_index]
        if cmd:
            self.app.pop_screen()
            self.app.run_command(cmd)

class BriefdCommands(Provider):
    async def discover(self) -> Hits:
        yield DiscoveryHit(
            "Settings",
            self._open_settings,
            help="Open briefd settings menu",
        )
        yield DiscoveryHit(
            "Open Config File",
            self._open_config,
            help="Open config.toml in your default editor",
        )

    async def search(self, query: str) -> Hits:
        commands = [
            ("Settings", self._open_settings, "Open briefd settings menu"),
            ("Open Config File", self._open_config, "Open config.toml in your default editor"),
        ]
        query_lower = query.lower()
        for name, callback, help_text in commands:
            if query_lower in name.lower():
                yield Hit(1.0, name, callback, help=help_text)

    async def _open_settings(self) -> None:
        await self.app.push_screen(SettingsScreen())

    async def _open_config(self) -> None:
        import subprocess
        import sys
        from core.backend import CONFIG_PATH
        if sys.platform == "win32":
            subprocess.Popen(["notepad", str(CONFIG_PATH)])
        else:
            import os
            editor = os.environ.get("EDITOR", "nano")
            subprocess.Popen([editor, str(CONFIG_PATH)])