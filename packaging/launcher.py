"""Entry point for the frozen build. PyInstaller needs a plain script, not a package."""

from claude_usage_widget.main import main

raise SystemExit(main())
