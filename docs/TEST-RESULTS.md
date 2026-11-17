# Stintory 1.0.0 — validation results

## Automated development validation

Linux, Python 3.13.5, Tk/Xvfb and simulated Resolve API or fake probe processes. The complete isolated-module runner finished successfully: 124 tests passed across 18 modules. Two additional version consistency tests passed after final version/metadata checks (126 distinct tests total). The three brand-cleanup tests and 35 state/data tests were also rerun successfully. Existing test fixtures emitted ResourceWarning messages about temporary files; these did not fail tests.

The six new startup regression tests cover stale empty API proxies, repeated null or failed scripting calls, recovery after short outages, resuming without new mouse input while still inside the idle limit, and preventing a resume beyond that limit. Existing helper restart and Linked shutdown tests passed in the complete run.

GUI checks in Xvfb passed:
- All 20 locales opened dashboard, settings, history and invoice dialogs.
- All 20 locales switched in the running application while retaining the current session object, currency, rate and independent invoice language; compact and hidden dashboard states were preserved.
- The real Tk event loop and an isolated fake helper process handled delayed scripting availability, Project Manager and hide-to-tray during startup, then started tracking and accrued time without reopening the window.
- Nine theme palettes, manual tray widget behavior and currency/invoice UI smoke checks.
- Invoice-generation tests in the complete automated run, including all 20 supported invoice languages in this Linux environment.

## Native status and limitations

Windows Linked was user-tested by the maintainer on their Windows PC with Resolve Studio 21 during private development. Basic installation, automatic launch and project/timeline tracking were confirmed. A startup issue was reported when hiding the tracker before Resolve was ready, and language previously required a restart. The corrections above were tested in simulation only. Retest this exact release on real Windows before marking it stable; particularly repeat the hidden-startup and live-language scenarios. Windows Resident and both macOS profiles remain experimental. Resolve API capability checks are not guarantees of future compatibility. Windows/macOS tray integration, native performance, optional executable builds and GitHub Actions have not been verified in this environment.

The public release is a source-distributed beta, not a signed native binary. See TESTING.md for the native checklist.
