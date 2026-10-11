# CLAUDE.md

## Project

Build a lightweight, native-feeling **Claude Usage Widget** for
**Windows 10/11 and CachyOS Linux**. Use one shared codebase.

## Stack

-   Python 3.12+ and PySide6/Qt.
-   Keep OS-specific behavior in separate platform modules.
-   Use type hints, small modules, and tests.

## Core features

-   Compact, draggable, always-on-top desktop widget with optional
    system tray.
-   Show Claude session and weekly usage, reset times, and last-updated
    status **only when verified data is available**.
-   Refresh controls, configurable warning thresholds, dark/light
    themes, settings, and launch-at-login.
-   Clearly distinguish account-plan usage from local Claude Code
    activity.

## Data and security

-   Verify the usage data source and response format; never invent
    endpoints, fields, limits, percentages, or reset times.
-   Treat unofficial endpoints as unstable and document the limitation.
-   Handle network errors, expired credentials, and rate limits
    gracefully; show stale data with its timestamp.
-   Never log or hardcode tokens, cookies, or secrets. Do not transmit
    credentials to third parties.
-   Read local Claude Code data only when needed, optionally, and
    read-only. Do not upload or modify it.
-   No telemetry or analytics by default.

## Platform support

-   **Windows:** per-user settings, tray support, reversible startup
    option, and portable executable build.
-   **CachyOS:** support KDE Plasma where possible, XDG config/cache
    paths, `.desktop` launcher, and optional XDG autostart. Do not
    require root.
-   Document Wayland/X11 differences and mark any platform that has not
    been tested.

## Working rules

1.  Inspect the repository before editing and explain a brief plan.
2.  Implement in small, testable steps; label mock data clearly.
3.  Keep the UI responsive; perform network work asynchronously.
4.  Test valid, missing, malformed, stale, and rate-limited responses.
5.  Run available tests and checks. Never claim a build or platform was
    tested unless it was.
6.  Keep `README.md` updated with setup, build, privacy, and known
    limitations.
