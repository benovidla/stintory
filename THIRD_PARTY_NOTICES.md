# Third-party notices

Scope: source-only beta archive. The MIT notice in LICENSE is retained from [Resolve Edit Tracker](https://github.com/jasonbacong/resolve-edit-tracker/blob/main/LICENSE), Copyright (c) 2026 Jason Grech. See CREDITS.md for provenance. No Blackmagic proprietary SDK, third-party commercial app, font file, dependency wheel or Python interpreter is shipped in this archive. Installation downloads dependencies separately. Their own licenses apply; this document is an index, not a replacement for their license texts.

| Dependency | License / reference |
| --- | --- |
| Python | [PSF and included components](https://docs.python.org/3/license.html) |
| Tk | [Tcl/Tk license](https://www.tcl-lang.org/software/tcltk/license.html) |
| pystray | [LGPL-3.0 upstream](https://github.com/moses-palmer/pystray), check exact distribution notices |
| Pillow | [MIT-CMU; historical HPND](https://github.com/python-pillow/Pillow/blob/main/LICENSE), plus native libraries |
| ReportLab open-source toolkit | [BSD](https://docs.reportlab.com/developerfaqs/) |
| fontTools | [MIT and component notices](https://github.com/fonttools/fonttools) |
| PyObjC (macOS) | [MIT and component licenses](https://github.com/ronaldoussoren/pyobjc) |
| six | [MIT](https://github.com/benjaminp/six) |
| charset-normalizer | [MIT](https://github.com/jawah/charset_normalizer) |
| PyInstaller (optional developer tool) | [GPL with bootloader exception / Apache for selected files](https://pyinstaller.org/en/stable/license.html) |

Transitive and embedded native components vary by installed version/platform. Do not assume all dependencies are MIT. Before distributing binaries, inventory the exact wheels and embedded libraries, preserve full notices, satisfy LGPL source/relinking and other applicable distribution requirements, and verify signing and any bundled fonts. The PyInstaller exception does not waive dependency obligations. Do not publish the experimental native-build artifacts before that review.

The local Resolve scripting API is used for read access; users must supply their own licensed installation and comply with its terms. See README for the independent-project notice. Font embedding flags are a technical check only; use fonts for which document use is authorized.
