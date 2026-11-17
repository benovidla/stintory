# Test plan and release gates

See README and TEST-RESULTS.md for the separate user-reported Windows Linked validation. All profiles require a native retest of this release. Record OS build, Resolve version/edition, Stintory version, profile, Python architecture and each observed result; redact paths, project names and billing data before sharing.

Automated tests exercise session transitions, idle behavior, crash recovery, aggregation, helper reconnect, themes, PDF generation, locale persistence and optional billing period. Linux GUI smoke checks instantiate all 20 locales and switch themes against simulated project data. This does not verify native Windows/macOS APIs or real Resolve Studio.

Before marking a release stable, run on Windows 10/11 and macOS on Apple Silicon and Intel (as supported by Resolve):

- Install linked mode: verify no resident Stintory process before launching Resolve. On Windows check that the short per-user scheduled task is registered, launches from existing taskbar/Start shortcuts within approximately a minute, and exits when Resolve is absent. Verify that disabling the scheduled check leaves the linked desktop launcher functional. On macOS verify no login agent in Linked mode. Launch from linked icon, open a project, switch timelines, close Resolve, and verify the tracker and helper both quit. Force-terminate Resolve, then restart using launcher and verify no duplicate time.
- Install resident mode after quitting/removing linked mode: log out/in, verify tracker starts once, waits idle, tracks automatically, and stays available after Resolve closes. Reopen Resolve. Disable startup, log in again and confirm no tracker.
- Verify foreground detection for Resolve and other apps, idle timeout, scrubbing, playback and rendering, sleep/wake, app crash restoration, and non-ASCII project names.
- Switch all nine explicit themes, 20 UI locales, PDF invoice language, custom idle interval. Inspect PDFs and totals, especially non-ASCII characters, differing historical rates and date filters.
- Compare Activity Monitor / Task Manager CPU, memory and disk activity with Resolve alone vs. both launch modes; measure rather than promise usage numbers.
- Check build artifacts, signing/notarization, dependency license notices, and installer removal. Do not promote CI builds to stable until native tests pass.

Check native font coverage and shaping for Arabic, Urdu, Hindi, Bengali, Chinese, Japanese and Korean. Verify actual scripts and translations with native speakers. See TEST-RESULTS.md for the observed development results.

- Open Stintory directly with Resolve closed; leave it open beyond two minutes; start Resolve and verify tracking attaches without a second tracker. Close Resolve and verify exit. Repeat manual review and close without starting Resolve. Test Hide to tray in both windows, restore via tray and desktop shortcut, and test fallback when the tray is unavailable.

After every Resolve update: verify Local scripting remains enabled, compare measured time against a known interval, switch timelines, reopen Project Manager, and close/reopen Resolve. Confirm the exact version logged in debug.log. Unknown pages or missing required API methods must pause accrual until explicitly supported.

- Hide the dashboard while Resolve is still loading; wait for Project Manager and open a project. Verify the timer starts without reopening Stintory or Resolve. Repeat with a slow startup and temporary scripting failure. Switch language during an active session; verify the timer, history, window mode and billing rate are preserved.
