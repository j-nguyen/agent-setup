# Desktop recording candidates

Research checked 2026-11-15. These are implementation options, not installed or
validated backends. The browser-recorder remains the only implemented backend.

## Recommended first prototype: OBS Studio + obs-websocket

OBS exposes a built-in WebSocket endpoint for scripts. Its protocol includes
StartRecord, StopRecord (returns outputPath), GetRecordStatus and
SaveSourceScreenshot. That provides a promising common capture interface for
video and milestone images without an MCP server. Use a dedicated scene/profile
and capture the selected app window. Avoid changing an existing active recording.

Sources:
- https://obsproject.com/kb/developer-guide
- https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md
- https://obsproject.com/kb/window-capture-sources

Linux has Xcomposite and PipeWire window capture sources. For the user's Fedora
KDE environment, prototype PipeWire/portal capture in the actual desktop session;
do not assume a headless shell can capture it. Capture source and cursor behavior
need validation on each OS. The XDG ScreenCast portal supports cursor modes and
may prompt for source selection. Restoration tokens do not guarantee unattended
access when permissions or available windows change.

Portal specification:
https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.ScreenCast.html

## Alternatives

- Kooha: a simpler Linux screen-recording application. Worth considering for
  human-operated capture, but its documented UI workflow is less suitable than
  OBS's explicit remote API for an agent-controlled backend.
  https://github.com/SeaDve/Kooha
- wl-screenrec: an efficient CLI using hardware encoding. Requires specific
  Wayland capture protocols and GPU support; its supported compositor list does
  not establish KDE compatibility. Don't make it the portable default.
  https://github.com/rosalyntg/wl-screenrec

## Prototype acceptance criteria

Launch the target app built from the specified worktree, select only its window,
record start/actions/stop, save milestone screenshots, verify video playback and
cursor visibility, and preserve partial artifacts on failure. Test portal denial
and an already-running OBS recording without disrupting the user's session.

Recording and interaction are separate: OBS captures pixels but does not operate
the app. A desktop backend also needs app/platform-specific UI automation (or a
human-driven scenario). Choose that only when the target app/platform is known.
Keep the skill/subagent interface neutral across coding agents. Do not install
OBS or start capturing the user's desktop merely because this reference is read.
