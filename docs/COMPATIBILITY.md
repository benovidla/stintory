# Resolve compatibility

Stintory uses the read-only subset of the locally installed DaVinci Resolve Studio scripting API. The vendor's installed Developer/Scripting README is the reference for a given release. The application does not redistribute the API module or the native library, patch Resolve, inspect project databases, or bypass Studio licensing. Keep External scripting using set to Local, not Network. The vendor manual documents this option.

## Forward compatibility (best effort)

- No hard-coded maximum Resolve version. The probe logs `GetVersionString()` or falls back to `GetVersion()` if available. An unknown version alone does not prevent tracking.
- Discover a real `Modules/DaVinciResolveScript.py`, with local `RESOLVE_SCRIPT_API` and `RESOLVE_SCRIPT_LIB` overrides. Windows also checks the running process location; macOS includes per-user Applications paths. Explicit native library paths take priority.
- Required calls: current page, project manager, current project, project name, current timeline and its name when present. Missing/throwing calls pause billing, invalidate the response, and retry. A named active timeline can establish project presence without `GetTimelineCount()`. An empty/default project is not billed.
- Timecode and rendering checks are optional. If missing, playback/render-aware idle exceptions may not work; standard idle behavior remains.
- New page names are logged and conservatively paused until explicitly added and tested. No automatic billing on unknown pages. Existing Project Manager detection remains best-effort.
- Probe process isolation and the supervisor's restart timeout guard against native API hangs. The probe reacquires empty startup connections and recycles the whole helper after repeated API failures. Hiding the dashboard never stops these retries. No stale time is backfilled after an outage. Tracking is sampled; some delay is possible.

A future API or ABI change can still require a code update. Resolve, its native scripting library and the Python interpreter must be architecture-compatible. Prefer supported Python 3.12 until tested otherwise. The CI matrix is intended to test application Python compatibility, not proprietary Resolve compatibility.

If connection fails after a Resolve update, restart Resolve and Stintory, check Local scripting, verify the local paths, and consult debug.log. Include only the detected version, OS/architecture, launch profile, and a redacted description when reporting. Do not attach vendor libraries, project data or full unredacted logs.
