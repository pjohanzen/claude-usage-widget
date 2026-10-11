"""Command-line entry point."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from claude_usage_widget import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="claude-usage-widget",
        description="Compact desktop widget for Claude usage. Shows live status-line data by default.",
    )
    parser.add_argument(
        "--fixture", type=Path, help="Read usage from a local JSON file (development and testing)."
    )
    parser.add_argument(
        "--source",
        choices=["demo", "statusline"],
        default="statusline",
        help="statusline (default): live data captured from Claude Code's status line. demo: sample numbers.",
    )
    parser.add_argument("--settings", type=Path, help="Use a different settings file.")
    parser.add_argument(
        "--capture-statusline",
        action="store_true",
        help="Internal: status-line hook. Reads Claude Code's JSON on stdin and saves usage limits.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    if args.capture_statusline:
        # Imported lazily: this runs on every status-line update, so it must not load Qt.
        from claude_usage_widget.services.statusline_capture import statusline_main

        return statusline_main()

    from claude_usage_widget.app import run_app
    from claude_usage_widget.services.statusline_source import StatuslineUsageProvider
    from claude_usage_widget.services.usage_client import (
        DemoUsageProvider,
        FixtureUsageProvider,
        UsageProvider,
    )
    from claude_usage_widget.storage.settings import default_settings_path, load_settings

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    provider: UsageProvider
    if args.fixture:
        provider = FixtureUsageProvider(args.fixture)
    elif args.source == "statusline":
        provider = StatuslineUsageProvider()
    else:
        provider = DemoUsageProvider()
    settings_path = args.settings or default_settings_path()
    settings = load_settings(settings_path)
    return run_app(provider, settings, settings_path)
