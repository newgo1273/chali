"""Textual configuration editor."""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Button, Checkbox, Footer, Header, Input, Label, Static

from .config import save_config

PALETTE = {
    "navy": "#3451A3",
    "indigo": "#4338CA",
    "teal": "#0F766E",
    "green": "#166534",
    "amber": "#B45309",
    "red": "#B91C1C",
    "slate": "#334155",
    "charcoal": "#27272A",
    "white": "#FFFFFF",
    "ivory": "#FFF7ED",
    "mist": "#E2E8F0",
    "black": "#111827",
}


class ConfigApp(App[bool]):
    TITLE = "Chali Setup"
    SUB_TITLE = "Local preferences"
    CSS = """
    Screen { align: center middle; }
    #form { width: 76; height: 90%; max-height: 90%; border: round $primary; padding: 1 2; }
    .section { margin-top: 1; text-style: bold; color: $accent; }
    .field { height: 3; }
    .field Label { width: 30; padding-top: 1; }
    .field Input { width: 1fr; }
    .palette { height: 3; }
    .palette Button { width: 1fr; min-width: 8; margin-right: 1; }
    #actions { height: 3; align-horizontal: right; }
    #actions Button { margin-left: 1; }
    #notice { height: 2; color: $success; }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__()
        self.config = config

    def on_mount(self) -> None:
        for name in ("navy", "indigo", "teal", "green", "amber", "red", "slate", "charcoal"):
            button = self.query_one(f"#bg-{name}", Button)
            button.styles.background = PALETTE[name]
            button.styles.color = "#FFFFFF"
        for name in ("white", "ivory", "mist"):
            button = self.query_one(f"#fg-{name}", Button)
            button.styles.background = PALETTE[name]
            button.styles.color = "#111827"
        black = self.query_one("#fg-black", Button)
        black.styles.background = PALETTE["black"]
        black.styles.color = "#FFFFFF"

    def compose(self) -> ComposeResult:
        youtube = self.config["youtube"]
        streamlabs = self.config["streamlabs"]
        chat = self.config["chat"]
        yield Header()
        with VerticalScroll(id="form"):
            yield Static("YouTube defaults", classes="section")
            with Horizontal(classes="field"):
                yield Label("Default language")
                yield Input(youtube["default_language"], id="language")
            with Horizontal(classes="field"):
                yield Label("Default quality")
                yield Input(youtube["default_quality"], id="quality")
            yield Checkbox("Demo mode (no network or credentials)", youtube["demo_mode"], id="demo")
            yield Static("Streamlabs and Fund Bar", classes="section")
            with Horizontal(classes="field"):
                yield Label("Socket API token")
                yield Input(streamlabs["socket_token"], password=True, id="token")
            yield Checkbox("Show Fund Bar", streamlabs["fund_bar_enabled"], id="fund-enabled")
            with Horizontal(classes="field"):
                yield Label("Fund label")
                yield Input(streamlabs["fund_label"], id="fund-label")
            with Horizontal(classes="field"):
                yield Label("Goal target")
                yield Input(str(streamlabs["fund_target"]), id="fund-target")
            with Horizontal(classes="field"):
                yield Label("Current amount")
                yield Input(str(streamlabs["fund_current"]), id="fund-current")
            yield Static("Chat author badge palette", classes="section")
            with Horizontal(classes="field"):
                yield Label("Badge background (#RRGGBB)")
                yield Input(chat["author_badge_background"], id="badge-bg")
            with Horizontal(classes="field"):
                yield Label("Badge foreground (#RRGGBB)")
                yield Input(chat["author_badge_foreground"], id="badge-fg")
            yield Static("Background palette")
            with Horizontal(classes="palette"):
                for name in ("navy", "indigo", "teal", "green"):
                    yield Button(name.title(), id=f"bg-{name}")
            with Horizontal(classes="palette"):
                for name in ("amber", "red", "slate", "charcoal"):
                    yield Button(name.title(), id=f"bg-{name}")
            yield Static("Foreground palette")
            with Horizontal(classes="palette"):
                for name in ("white", "ivory", "mist", "black"):
                    yield Button(name.title(), id=f"fg-{name}")
            yield Static("", id="notice")
            with Horizontal(id="actions"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", id="cancel")
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("bg-"):
            self.query_one("#badge-bg", Input).value = PALETTE[button_id[3:]]
            return
        if button_id.startswith("fg-"):
            self.query_one("#badge-fg", Input).value = PALETTE[button_id[3:]]
            return
        if button_id == "cancel":
            self.exit(False)
            return
        if button_id != "save":
            return
        try:
            config = {
                "youtube": {
                    **self.config["youtube"],
                    "default_language": self.query_one("#language", Input).value.strip() or "en",
                    "default_quality": self.query_one("#quality", Input).value.strip() or "auto",
                    "demo_mode": self.query_one("#demo", Checkbox).value,
                },
                "streamlabs": {
                    **self.config["streamlabs"],
                    "socket_token": self.query_one("#token", Input).value.strip(),
                    "fund_bar_enabled": self.query_one("#fund-enabled", Checkbox).value,
                    "fund_label": self.query_one("#fund-label", Input).value.strip() or "Fund",
                    "fund_target": float(self.query_one("#fund-target", Input).value),
                    "fund_current": float(self.query_one("#fund-current", Input).value),
                },
                "chat": {
                    **self.config["chat"],
                    "author_badge_background": self.query_one("#badge-bg", Input).value.strip(),
                    "author_badge_foreground": self.query_one("#badge-fg", Input).value.strip(),
                },
            }
            target = save_config(config)
        except (TypeError, ValueError, OSError) as exc:
            self.query_one("#notice", Static).update(f"Could not save: {exc}")
            self.query_one("#notice", Static).styles.color = "red"
            return
        self.query_one("#notice", Static).update(f"Saved securely to {target}")
        self.exit(True)


def run_config_tui(config: dict[str, Any]) -> bool:
    return ConfigApp(config).run()
