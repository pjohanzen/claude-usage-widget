# Claude Usage Widget

A compact, always-on-top desktop widget for Windows 10/11 and Linux (developed for CachyOS / Arch with KDE Plasma). It is built with Python and PySide6.

> **Status:** live data comes from Claude Code's status line (see "Live data" below). Until that is set up, the widget shows "No status-line data yet" instead of numbers. Sample numbers are available only with `--source demo`.

## What works today

- Frameless, draggable card with session and weekly progress bars, reset countdowns, and a "Updated … · source" footer.
- Warning and critical colors at thresholds you set. A quota the source did not report shows "Not provided", never a fake 0%.
- Stale marking: data older than two refresh cycles (minimum 10 minutes) is marked "Stale". A timestamp more than five minutes in the future is also marked "Stale", because it cannot be trusted.
- Error states: "Sign-in needed", "Rate limited", "Unavailable". The last good snapshot stays visible with its timestamp.
- Background refresh on a thread pool, with exponential backoff on rate limits and a 10-second gap on manual refresh.
- Pin button (📌) in the header keeps the widget above other windows. It is saved, and it stays in sync with the "Keep the widget above other windows" setting.
- Dark, light, or system theme; opacity; refresh interval; thresholds.
- Compact layout: hides the status line and reset details, keeps the bars and the staleness footer.
- Reset countdowns show the time remaining and the reset time in your local clock. A reset that has passed shows "waiting for new data" rather than an old percentage.
- Start-at-login is checked against the real autostart entry each time the widget starts.
- A pixel pet in the card header. It is happy when usage is low, worried near the warning threshold, alarmed near critical, sleepy when data is stale or unavailable, and busy while a refresh runs. It blinks and bobs, and clicking it makes it hop. Turn it off with "Show the pixel pet" in Settings.
- System tray icon with Show/hide, Refresh, Settings, and Quit. "Hide to tray" is disabled when no tray is available.
- Start at login: a per-user Startup script on Windows, an XDG autostart `.desktop` file on Linux. Both are reversible and need no admin or root rights.

## What is not built yet

- **Live account usage.** No endpoint or credential handling is implemented. See "Data sources" below.
- **Claude Code local activity.** Not implemented.
- **Packaging.** No PyInstaller spec, AppImage, or Arch package yet.
- **History.** Not stored.

## Install as an AppImage (Linux)

A portable AppImage bundles Python and Qt, so you don't need a Python setup.

```bash
packaging/build_appimage.sh                 # builds dist/Claude_Usage_Widget-<version>-x86_64.AppImage
packaging/install_linux.sh dist/Claude_Usage_Widget-*-x86_64.AppImage
```

The installer copies the AppImage to `~/Applications`, adds an icon, and adds "Claude Usage Widget" to your application menu. It needs no root. To uninstall, delete `~/Applications/Claude_Usage_Widget.AppImage`, `~/.local/share/applications/claude-usage-widget.desktop`, and `~/.local/share/icons/hicolor/512x512/apps/claude-usage-widget.png`. If start-at-login was on, turn it off in Settings first.

Build notes:
- The build downloads a pinned `appimagetool` into `build/tools/` and refuses to use it if its SHA-256 changes.
- The AppImage is built on CachyOS, so it may not run on very old distributions with an older glibc.
- The Windows build is written (CI workflow and local script) but has not been run yet.

## Setup

Requires Python 3.12 or newer.

### CachyOS / Arch Linux

```bash
sudo pacman -S --needed python python-pip   # Python is usually already installed
cd "claude usage widget"
python -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
claude-usage-widget                         # or: python -m claude_usage_widget
```

Development checks:

```bash
pytest
ruff check src tests
mypy
```

Demo a failure state with a local fixture (see "Usage document format"):

```bash
claude-usage-widget --fixture tests/fixtures/rate_limited.json
claude-usage-widget --fixture tests/fixtures/valid.json --settings /tmp/test-settings.json
```

Start-at-login is set in Settings and writes `~/.config/autostart/claude-usage-widget.desktop`. An application-menu launcher is not provided yet.

### Windows 10/11

**Not yet verified on Windows.** The build and workflow below are written, but they have not been run on a Windows machine yet.

**Build a portable app (on Windows):**

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1
```

This runs the checks, builds `build\dist\ClaudeUsageWidget\`, smoke-tests `ClaudeUsageWidget.exe`, and writes `build\ClaudeUsageWidget-windows-portable.zip`. Unzip it anywhere and run `ClaudeUsageWidget.exe`. Nothing needs installing.

**Build in CI (no Windows machine needed):** push to GitHub. The workflow `.github/workflows/windows.yml` runs on a Windows runner and uploads the same zip as the artifact `ClaudeUsageWidget-windows-portable`.

**Run from source (development):**

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
claude-usage-widget
```

Settings are in `%APPDATA%\claude-usage-widget\settings.json`. Usage data is cached in `%LOCALAPPDATA%\claude-usage-widget\Cache`. Start-at-login writes `Claude Usage Widget.cmd` into your per-user Startup folder. Nothing needs administrator rights.

**Unverified on Windows:**
- The status-line hook. Claude Code runs the hook as `ClaudeUsageWidget.exe --capture-statusline`. The build is windowed, so the hook may receive no input. If usage never updates on Windows, that is the cause, and the fix is a console build for the hook.
- Tray, opacity, always-on-top, and start-at-login.

## Linux display notes

- Always-on-top and window positioning depend on the compositor. On Wayland, some compositors ignore client-side positioning and always-on-top hints. The widget still runs; it may not stay above other windows or remember its position.
- Opacity may be ignored under some compositors.
- Tray support requires a StatusNotifier-compatible panel. KDE Plasma supports this. Without a tray, "Hide to tray" is disabled so the widget cannot disappear.
- The app needs no root privileges and no systemd user service.

## Connect your Claude account

The widget does not sign in to Claude itself. Claude Code does, with your Google or email login, and the widget reads the usage Claude Code reports. The widget never asks for your Google password or Claude login, and it does not read Claude Code's login files.

1. Sign in to Claude Code with the same account (run `claude` and follow its login prompts).
2. Start the widget. If the status line is not set up, a **Claude connection** screen opens. Whenever the connection needs attention, the card shows a button such as **Finish connecting Claude…** that opens the same screen. It is also in the tray menu as **Claude connection…**.
3. Click **Set up status line**. This adds one entry to Claude Code's `settings.json`, with a backup written next to it (`settings.json.bak`). If Claude Code already has a different status line, the widget leaves it alone and tells you.
4. Send one message in Claude Code. Its next response updates the widget.

The connection screen shows one of four states:

- **Setup needed:** the status-line entry is missing.
- **Waiting for Claude Code:** the entry is set up, but Claude Code has not reported usage yet.
- **Connected:** usage was reported in the last 30 minutes.
- **Stale:** the last report is more than 30 minutes old. Open Claude Code to refresh it, or sign in again if it asks.

**Disconnect** clears the widget's cached usage and removes the status-line entry the widget created. It does not change Claude Code's sign-in.

Limits:

- Usage updates only when Claude Code makes an API response. When Claude Code is idle, the widget shows the last value, marked Stale.
- The status line reports only the limits your plan has. A plan without a weekly limit shows "Not provided" for it.
- The widget's status-line hook runs as `claude-usage-widget --capture-statusline`. It reads only the `rate_limits` field, makes no network requests, and writes one small file in the widget's cache. If you move the AppImage, use Set up status line again, so the entry points at the new location.
- Google sign-in and email sign-in are handled entirely by Claude Code and claude.ai. The widget has no Google or email login of its own.

## Usage document format

The only format the app parses is its own internal JSON document. The fixtures in `tests/fixtures/` show examples.

```json
{
  "updated_at": "2026-10-11T12:00:00Z",
  "session": {"used_percent": 42.5, "resets_at": "2026-10-11T14:30:00Z"},
  "weekly": {"used_percent": 61, "resets_at": "2026-10-14T00:00:00Z"}
}
```

- `updated_at` is required. It is when the data was current. A missing or invalid value is rejected.
- `session` and `weekly` are optional. A missing window shows "Not provided".
- `used_percent` must be a number from 0 to 100. Booleans, NaN, and strings are rejected.
- `resets_at` is optional. An ISO 8601 timestamp without a timezone is treated as UTC.
- A fixture may set `"simulate"` to `"rate_limited"`, `"sign_in_needed"`, or `"unavailable"`. This is for development only.

## Privacy

- **Read:** only the settings file the app wrote itself, and any `--fixture` file you pass.
- **Stored:** preferences only, in `settings.json`: refresh interval, thresholds, theme, opacity, always-on-top, start-at-login, and the window position. No credentials, tokens, cookies, usage history, or account data.
- **Leaves the machine:** nothing. The build makes no network requests. There is no telemetry, analytics, or crash reporting.
- **Written outside settings:** only the start-at-login file (`.cmd` in Startup on Windows, `.desktop` in `~/.config/autostart` on Linux), and only when you turn that option on.
- **Logs:** operational messages only. Usage values and credentials are never logged.

Reset to defaults in Settings, or delete `settings.json`, to clear saved preferences. Turning off start-at-login removes its file.

## Known limitations

- Live data exists only while Claude Code runs with the status line configured, and it updates only when Claude Code makes an API response. The widget never shows sample numbers unless `--source demo` is given.
- Windows is untested. Linux was developed on CachyOS only.
- Packaging for Windows (PyInstaller) and Linux (AppImage or Arch package) is not built.
- Wayland window behavior varies by compositor, as described above.

## Testing status

| Platform | Unit tests and lint/type checks | Running the GUI | Packaging |
| --- | --- | --- | --- |
| CachyOS (Linux, offscreen Qt platform) | Verified (see below) | Verified offscreen only; no real compositor tested | Not built |
| Windows 10/11 | Not yet tested | Not yet tested | Not built |

The Linux checks that were run: `pytest`, `ruff check`, `mypy --strict`, and rendering the widget in several states to images with the offscreen Qt platform.
