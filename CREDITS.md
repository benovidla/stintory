# Credits and provenance

Stintory is a cross-platform continuation of a Python port inspired by, and with tracking logic and data conventions adapted from, [resolve-edit-tracker](https://github.com/jasonbacong/resolve-edit-tracker) by Jason Grech (MIT; Copyright (c) 2026 Jason Grech). The original copyright and permission notice is retained in LICENSE. Stintory adds its own interface, branding, platform launchers, localization, PDF invoice generator and other functionality. It is not a claim of independently inventing every part of the tracker.

Stintory’s interface and visual identity were developed for this project, with AI-assisted design exploration and custom artwork. Third-party commercial tracker code and artwork are not bundled.

Runtime dependencies: Python/Tkinter (PSF/Tcl-Tk licenses), Pillow (MIT-CMU / historical HPND), pystray (LGPL-3.0), ReportLab (BSD), fontTools (MIT), and on macOS PyObjC (MIT). See each upstream package for exact terms and notices. PyInstaller is optional build tooling (GPL with bootloader exception). Do not strip third-party notices from binary distributions. The Blackmagic Resolve scripting libraries are discovered locally and never bundled. System fonts are used from the user's operating system at PDF export time; font files are not distributed with the source. PDF subsetting checks font flags but users must confirm font usage rights. See THIRD_PARTY_NOTICES.md.

Before publishing binaries, review the licenses and notices of the exact installed dependency versions (including transitive dependencies), especially LGPL requirements for pystray. Source archives contain the Stintory code and assets only, with dependencies installed separately.

The custom wordmark uses outlined lettering from Inter by the Inter Project Authors (SIL Open Font License 1.1); no font software is shipped. The timeline symbol was redrawn from the selected generated concept.
