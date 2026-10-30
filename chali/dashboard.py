"""Curses-based split-panel terminal dashboard."""

from __future__ import annotations

import curses
import queue
import threading
import time
from collections import deque
from typing import Any

from .stream import StreamEvent, run_sources


def _rgb(value: str) -> tuple[int, int, int]:
    return tuple(int(value[index : index + 2], 16) for index in (1, 3, 5))


def _xterm_color(value: str) -> int:
    red, green, blue = _rgb(value)
    levels = (0, 95, 135, 175, 215, 255)
    cube = tuple(min(range(6), key=lambda index: abs(levels[index] - channel)) for channel in (red, green, blue))
    cube_index = 16 + 36 * cube[0] + 6 * cube[1] + cube[2]
    gray = max(0, min(23, round(((red + green + blue) / 3 - 8) / 10)))
    gray_value = 8 + gray * 10
    gray_index = 232 + gray
    cube_distance = sum((channel - levels[index]) ** 2 for channel, index in zip((red, green, blue), cube))
    gray_distance = sum((channel - gray_value) ** 2 for channel in (red, green, blue))
    return cube_index if cube_distance <= gray_distance else gray_index


def _init_badge_colors(screen: Any, chat_config: dict[str, Any]) -> int:
    pair = 1
    try:
        curses.start_color()
        curses.use_default_colors()
        if curses.COLORS >= 256:
            curses.init_pair(
                pair,
                _xterm_color(chat_config["author_badge_foreground"]),
                _xterm_color(chat_config["author_badge_background"]),
            )
        else:
            curses.init_pair(pair, curses.COLOR_WHITE, curses.COLOR_BLUE)
    except curses.error:
        curses.init_pair(pair, curses.COLOR_WHITE, curses.COLOR_BLUE)
    return curses.color_pair(pair) | curses.A_BOLD


def _fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) > width:
        return text[: max(0, width - 1)] + "…"
    return text.ljust(width)


def _draw(
    screen: Any,
    state: dict[str, Any],
    lines: deque[list[tuple[str, int]]],
    config: dict[str, Any],
) -> None:
    screen.erase()
    height, width = screen.getmaxyx()
    if height < 9 or width < 40:
        screen.addnstr(0, 0, "Resize terminal to at least 40x9. Press q to quit.", max(0, width - 1))
        screen.refresh()
        return
    top = 0
    screen.addnstr(top, 0, _fit(" CHALI  ·  LIVE STREAM DASHBOARD", width - 1), width - 1, curses.A_BOLD | curses.A_REVERSE)
    screen.addnstr(1, 0, _fit(f" Viewers: {state['viewers']}", width - 1), width - 1)
    screen.addnstr(2, 0, _fit(f" Latest activity: {state['activity']}", width - 1), width - 1)
    if config["streamlabs"]["fund_bar_enabled"]:
        target = max(float(state["fund_target"]), 0.0)
        current = max(float(state["fund_current"]), 0.0)
        ratio = min(1.0, current / target) if target else 0.0
        filled = int(ratio * 20)
        bar = "█" * filled + "░" * (20 - filled)
        label = config["streamlabs"]["fund_label"]
        currency = state["currency"]
        screen.addnstr(
            3,
            0,
            _fit(f" {label}: [{bar}] {currency}{current:g}/{currency}{target:g}", width - 1),
            width - 1,
        )
        chat_top = 5
    else:
        chat_top = 4
    screen.addnstr(chat_top - 1, 0, _fit(" CHAT  ·  Press q to quit", width - 1), width - 1, curses.A_BOLD | curses.A_REVERSE)
    available = height - chat_top - 1
    for index, line in enumerate(list(lines)[-available:]):
        _add_styled(screen, chat_top + index, width - 1, line)
    try:
        screen.refresh()
    except curses.error:
        pass


def _render_chat(event: StreamEvent, badge_attr: int, width: int) -> list[list[tuple[str, int]]]:
    payload = event.payload
    if event.kind == "chat":
        stamp = str(payload.get("time", time.strftime("%H:%M:%S")))
        author = str(payload.get("author", "Unknown")).replace("\n", " ")[:32]
        message = str(payload.get("message", "")).replace("\n", " ")
        prefix = f"[{stamp}] "
        badge = f"[{author}]"
        indent_width = len(prefix) + len(badge) + 2
        first_width = max(1, width - indent_width)
        first = [(prefix, 0), (badge, badge_attr), (": ", 0)]
        if len(message) <= first_width:
            return [first + [(message, 0)]]
        first.append((message[:first_width], 0))
        rows = [first]
        rest = message[first_width:]
        continuation_width = max(1, width - indent_width)
        while rest:
            rows.append([(" " * indent_width, 0), (rest[:continuation_width], 0)])
            rest = rest[continuation_width:]
        return rows
    if event.kind == "alert":
        text = f" ★ ALERT: {payload.get('label', 'New alert')} "
        if payload.get("amount"):
            text += f"{payload.get('currency', '$')}{float(payload['amount']):g}"
        return [[(text[:width], curses.A_BOLD | curses.A_REVERSE)]]
    if event.kind == "error":
        return [[(f" ! {payload.get('text', 'Unknown error')}"[:width], curses.A_BOLD)]]
    if event.kind == "activity":
        return [[(f" · {payload.get('text', '')}"[:width], curses.A_DIM)]]
    return []


def _add_styled(screen: Any, y: int, width: int, styled: list[tuple[str, int]]) -> None:
    x = 0
    for text, attr in styled:
        pieces = text.split("\n")
        for index, piece in enumerate(pieces):
            if piece:
                remaining = width - x - 1
                if remaining > 0:
                    try:
                        screen.addnstr(y, x, piece, remaining, attr)
                    except curses.error:
                        pass
                x += len(piece)
            if index < len(pieces) - 1:
                y += 1
                x = 0


def _worker(events: queue.Queue[StreamEvent], stop: threading.Event, config: dict[str, Any], url: str | None, demo: bool) -> None:
    run_sources(events, stop, config, url, demo)


def run_dashboard(config: dict[str, Any], url: str | None, demo: bool) -> None:
    events: queue.Queue[StreamEvent] = queue.Queue()
    stop = threading.Event()
    worker = threading.Thread(target=_worker, args=(events, stop, config, url, demo), daemon=True)

    def screen_loop(screen: Any) -> None:
        screen.nodelay(True)
        screen.keypad(True)
        badge_attr = _init_badge_colors(screen, config["chat"])
        lines: deque[list[tuple[str, int]]] = deque(maxlen=config["chat"]["max_messages"])
        state: dict[str, Any] = {
            "viewers": "—",
            "activity": "Starting demo" if demo else "Connecting",
            "fund_current": config["streamlabs"]["fund_current"],
            "fund_target": config["streamlabs"]["fund_target"],
            "currency": "$",
        }
        flash_until = 0.0
        worker.start()
        try:
            while True:
                key = screen.getch()
                if key in (ord("q"), ord("Q"), 27):
                    break
                while True:
                    try:
                        event = events.get_nowait()
                    except queue.Empty:
                        break
                    if event.kind == "viewers":
                        state["viewers"] = f"{event.payload.get('count', '—'):,}" if isinstance(event.payload.get("count"), int) else "—"
                    elif event.kind == "activity":
                        state["activity"] = str(event.payload.get("text", ""))
                    elif event.kind == "alert":
                        state["fund_current"] = event.payload.get("current", state["fund_current"])
                        state["fund_target"] = event.payload.get("target", state["fund_target"])
                        state["currency"] = event.payload.get("currency", "$")
                        flash_until = time.monotonic() + 4
                    styled_rows = _render_chat(event, badge_attr, screen.getmaxyx()[1] - 1)
                    lines.extend(styled_rows)
                display_state = dict(state)
                if time.monotonic() < flash_until:
                    display_state["activity"] = f"★ NEW ALERT ★ {state['activity']}"
                _draw(screen, display_state, lines, config)
                time.sleep(0.08)
        finally:
            stop.set()
            worker.join(timeout=3)

    try:
        curses.wrapper(screen_loop)
    except curses.error as exc:
        raise RuntimeError(f"could not initialize terminal dashboard: {exc}") from exc
