"""Demo and optional live stream event sources."""

from __future__ import annotations

import asyncio
import queue
import random
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, quote, urlparse


@dataclass
class StreamEvent:
    kind: str
    payload: dict[str, Any]


def youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().split(":", 1)[0]
    if host in {"youtu.be", "www.youtu.be"}:
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host.endswith("youtube.com"):
        values = parse_qs(parsed.query)
        video_id = values.get("v", [""])[0]
        if not video_id:
            match = re.match(r"/(?:live|embed|shorts)/([^/?]+)", parsed.path)
            video_id = match.group(1) if match else ""
    else:
        raise ValueError("URL must be a YouTube video or live-stream URL")
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,}", video_id):
        raise ValueError("could not find a valid YouTube video ID in URL")
    return video_id


def _post(events: queue.Queue[StreamEvent], kind: str, **payload: Any) -> None:
    events.put(StreamEvent(kind, payload))


def _format_message_time(value: Any) -> str:
    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")
    if isinstance(value, (int, float)):
        return time.strftime("%H:%M:%S", time.localtime(value))
    if isinstance(value, str):
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(value[:19], fmt).strftime("%H:%M:%S")
            except ValueError:
                continue
        if re.fullmatch(r"\d{2}:\d{2}:\d{2}", value):
            return value
    return time.strftime("%H:%M:%S")


async def _demo_source(events: queue.Queue[StreamEvent], stop: threading.Event, config: dict[str, Any]) -> None:
    names = ["Mira", "bytewizard", "Luna", "Kairo", "Nova"]
    messages = [
        "Hello everyone! 👋",
        "This demo is running entirely offline.",
        "The badges use your saved palette.",
        "Great stream!",
        "Fund bar and alerts update live here.",
    ]
    current = float(config["streamlabs"]["fund_current"])
    target = float(config["streamlabs"]["fund_target"])
    _post(events, "viewers", count=random.randint(120, 480))
    _post(events, "activity", text="Demo stream connected")
    last_alert = time.monotonic()
    while not stop.is_set():
        await asyncio.sleep(2.2)
        if stop.is_set():
            return
        _post(
            events,
            "chat",
            time=_format_message_time(time.time()),
            author=random.choice(names),
            message=random.choice(messages),
        )
        _post(events, "viewers", count=random.randint(120, 480))
        if time.monotonic() - last_alert >= 13:
            amount = random.choice([5.0, 10.0, 15.0])
            current += amount
            alert = {
                "label": "Demo tip",
                "amount": amount,
                "current": current,
                "target": target,
                "currency": "$",
            }
            _post(events, "alert", **alert)
            _post(events, "activity", text=f"Demo tip: +${amount:.0f}")
            last_alert = time.monotonic()


async def _youtube_source(
    url: str, events: queue.Queue[StreamEvent], stop: threading.Event
) -> None:
    try:
        import pytchat
        from requests.exceptions import RequestException
    except ImportError:
        _post(events, "error", text="Live YouTube chat needs pytchat. Install its Debian package if available.")
        return
    video_id = youtube_video_id(url)
    try:
        chat = await asyncio.to_thread(pytchat.create, video_id=video_id)
    except (
        pytchat.exceptions.InvalidVideoIdException,
        pytchat.exceptions.UnknownConnectionError,
        pytchat.exceptions.VideoInfoParseError,
        pytchat.exceptions.ResponseContextError,
        pytchat.exceptions.RetryExceedMaxCount,
        RequestException,
        OSError,
        RuntimeError,
    ) as exc:
        _post(events, "error", text=f"Could not connect to YouTube chat: {exc}")
        return
    _post(events, "activity", text="YouTube chat connected")
    while not stop.is_set() and await asyncio.to_thread(chat.is_alive):
        try:
            data = await asyncio.to_thread(chat.get)
            for item in data.sync_items():
                author = getattr(getattr(item, "author", None), "name", "Unknown")
                message = getattr(item, "message", "")
                _post(
                    events,
                    "chat",
                    time=_format_message_time(getattr(item, "datetime", None)),
                    author=str(author),
                    message=str(message),
                )
        except (
            pytchat.exceptions.ChatParseException,
            pytchat.exceptions.RetryExceedMaxCount,
            RequestException,
            OSError,
            RuntimeError,
        ) as exc:
            _post(events, "error", text=f"YouTube chat polling failed: {exc}")
            await asyncio.sleep(1)
            continue
        await asyncio.sleep(1)
    _post(events, "activity", text="YouTube chat ended")


async def _viewer_source(url: str, events: queue.Queue[StreamEvent], stop: threading.Event) -> None:
    try:
        import yt_dlp
    except ImportError:
        _post(events, "activity", text="Live viewer count unavailable (yt-dlp is not installed)")
        return
    ydl_options = {"quiet": True, "no_warnings": True, "skip_download": True}
    while not stop.is_set():
        try:
            def extract() -> int | None:
                with yt_dlp.YoutubeDL(ydl_options) as ydl:
                    info = ydl.extract_info(url, download=False)
                value = info.get("concurrent_view_count") if info else None
                return int(value) if value is not None else None

            count = await asyncio.to_thread(extract)
            if count is not None:
                _post(events, "viewers", count=count)
        except (yt_dlp.utils.DownloadError, OSError, ValueError) as exc:
            _post(events, "error", text=f"Could not update viewer count: {exc}")
        for _ in range(30):
            if stop.is_set():
                return
            await asyncio.sleep(1)


def _alert_text(data: Any) -> tuple[str, float, str] | None:
    if not isinstance(data, dict):
        return None
    alert_type = str(data.get("type") or data.get("for") or "alert").lower()
    records = data.get("message", data.get("data", []))
    if isinstance(records, dict):
        records = [records]
    if not isinstance(records, list):
        records = []
    messages: list[str] = []
    amount = 0.0
    currency = "$"
    for record in records:
        if not isinstance(record, dict):
            continue
        name = str(record.get("name") or record.get("from") or record.get("username") or "Someone")
        raw_amount = record.get("amount", record.get("quantity", 0))
        try:
            amount += float(raw_amount or 0)
        except (TypeError, ValueError):
            pass
        currency = str(record.get("currency") or currency)
        messages.append(name)
    detail = ", ".join(messages) or "New alert"
    label = alert_type.replace("_", " ").title()
    return f"{label}: {detail}", amount, currency


async def _streamlabs_source(
    token: str,
    events: queue.Queue[StreamEvent],
    stop: threading.Event,
    config: dict[str, Any],
) -> None:
    try:
        import socketio
    except ImportError:
        _post(events, "error", text="Streamlabs alerts need python-socketio (Debian package: python3-socketio).")
        return

    client = socketio.AsyncClient(reconnection=True, logger=False, engineio_logger=False)
    current = float(config["streamlabs"]["fund_current"])
    target = float(config["streamlabs"]["fund_target"])

    @client.on("event")
    async def on_event(data: Any) -> None:
        nonlocal current
        parsed = _alert_text(data)
        if not parsed:
            return
        text, amount, currency = parsed
        current += amount
        _post(events, "alert", label=text, amount=amount, current=current, target=target, currency=currency)
        _post(events, "activity", text=text)

    try:
        connection_url = f"https://sockets.streamlabs.com?token={quote(token, safe='')}"
        await client.connect(
            connection_url,
            transports=["websocket"],
            socketio_path="socket.io",
            wait_timeout=10,
        )
        _post(events, "activity", text="Streamlabs connected")
        while not stop.is_set() and client.connected:
            await asyncio.sleep(0.5)
    except (
        socketio.exceptions.SocketIOError,
        asyncio.TimeoutError,
        OSError,
        RuntimeError,
        ValueError,
    ) as exc:
        details = str(exc)
        if token:
            details = details.replace(token, "[redacted]")
            details = details.replace(quote(token, safe=""), "[redacted]")
        _post(events, "error", text=f"Streamlabs connection failed: {details}")
    finally:
        if client.connected:
            await client.disconnect()


def run_sources(
    events: queue.Queue[StreamEvent],
    stop: threading.Event,
    config: dict[str, Any],
    url: str | None,
    demo: bool,
) -> None:
    async def run() -> None:
        if demo:
            await _demo_source(events, stop, config)
            return
        if not url:
            _post(events, "error", text="Live mode requires a YouTube URL.")
            return
        tasks = [asyncio.create_task(_youtube_source(url, events, stop))]
        tasks.append(asyncio.create_task(_viewer_source(url, events, stop)))
        token = config["streamlabs"]["socket_token"].strip()
        if token:
            tasks.append(asyncio.create_task(_streamlabs_source(token, events, stop, config)))
        await asyncio.gather(*tasks)

    try:
        asyncio.run(run())
    except (OSError, RuntimeError, ValueError, asyncio.TimeoutError) as exc:
        _post(events, "error", text=f"Stream worker stopped: {exc}")
