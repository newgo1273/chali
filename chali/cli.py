"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys

from . import __version__
from .config import load_config


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chali",
        description="A terminal dashboard for YouTube live chat and Streamlabs alerts.",
    )
    parser.add_argument("url", nargs="?", help="YouTube live-stream URL (use --live to connect)")
    parser.add_argument("--config", action="store_true", help="open the interactive setup screen")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--live", action="store_true", help="connect to the live YouTube URL")
    mode.add_argument("--demo", action="store_true", help="run the simulated stream without network access")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        config = load_config()
        if args.config:
            from .config_tui import run_config_tui

            return 0 if run_config_tui(config) else 1
        demo = args.demo or (config["youtube"]["demo_mode"] and not args.live)
        if args.live and not args.url:
            _parser().error("--live requires a YouTube URL")
        from .dashboard import run_dashboard

        run_dashboard(config, args.url, demo)
    except (ImportError, TypeError, ValueError, OSError, RuntimeError) as exc:
        print(f"chali: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
