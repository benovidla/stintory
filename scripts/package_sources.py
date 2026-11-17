"""Make four profile-specific source installers and a GitHub repository ZIP."""
import argparse, hashlib, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
VERSION=__import__("runpy").run_path(str(ROOT/"resolve_edit_tracker/__init__.py"))["__version__"]
SKIP={'.git','__pycache__','.venv','.build-venv','build','dist','.pytest_cache','.DS_Store','launch-mode.txt','launcher-config.txt','resident-python.txt','sessions.json','current.json','settings.json','instance.lock','.env'}
# Explicit source allowlist. Do not ship arbitrary exports or user files alongside code.
ROOT_FILES = set(".gitignore LICENSE CREDITS.md THIRD_PARTY_NOTICES.md README.md CHANGELOG.md CONTRIBUTING.md SECURITY.md RELEASE_NOTES.md QUICKSTART-SK.txt app.ico build_exe.bat build_mac.command diagnose.bat disable_auto.bat disable_login.command DISABLE-LINKED-CHECK.bat launch_resident.vbs launch_resolve.pyw launch_with_resolve.vbs link_resolve.ps1 linked_task.py make_icon.py make_shortcut.vbs open_data_folder.bat open_panel.bat requirements.txt restore_resolve.bat review_history.bat review_history.command run.bat run_resident.bat run_tracker.py run_tracker.pyw setup.bat setup_linked.bat setup_linked.command setup_linked.py setup_mac.command setup_resident.bat setup_resident.command try_demo.bat try_demo.command REPAIR-LINKED.bat".split())
ASSETS = {'app.ico','brand.png','icon.png','neon_brand.png','translations.json','brand_light.png','tray.png','logo.svg','logo-light.svg','symbol.svg','app.svg','tray.svg','wordmark.svg'}
DOCS = {'ARCHITECTURE.md','TEST-RESULTS.md','TESTING.md','COMPATIBILITY.md','dashboard.png','dashboard-sk.png','brand-banner.svg','BRAND.md'}

def allowed(rel):
    if len(rel.parts)==1: return rel.name in ROOT_FILES
    if rel.parts[0] in ('resolve_edit_tracker','scripts','tests') and len(rel.parts)==2:
        return rel.suffix=='.py' and rel.name!='DaVinciResolveScript.py'
    if rel.parts[:2]==('resolve_edit_tracker','assets') and len(rel.parts)==3:
        return rel.name in ASSETS
    if rel.parts[0]=='docs' and len(rel.parts)==2: return rel.name in DOCS
    if rel.parts[:2] in (('.github','workflows'),('.github','ISSUE_TEMPLATE')) and len(rel.parts)==3:
        return rel.suffix in ('.md','.yml','.yaml')
    return rel.as_posix()=='.github/pull_request_template.md'

def entries():
    for file in sorted(ROOT.rglob('*')):
        rel=file.relative_to(ROOT)
        if file.is_file() and not file.is_symlink() and allowed(rel):
            yield file,rel

def pack(out, platform=None, mode=None):
    suffix=f'{platform}-{mode}' if platform else 'GitHub-source'
    path=out/f'Stintory-{VERSION}-{suffix}.zip'
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for file,rel in entries():
            if platform and rel.parts[0]=='.github':continue
            z.write(file,'Stintory/'+rel.as_posix())
        if platform:
            win=platform=='Windows'; script=f'setup_{mode}'+('.bat' if win else '.command')
            name='INSTALL.bat' if win else 'INSTALL.command'
            data=f'@echo off\r\ncall "%~dp0{script}"\r\n' if win else f'#!/bin/bash\ncd "$(dirname "$0")"\nexec /bin/bash ./{script}\n'
            zi=zipfile.ZipInfo('Stintory/'+name);zi.create_system=3;zi.external_attr=(0o100755<<16);zi.compress_type=zipfile.ZIP_DEFLATED;z.writestr(zi,data)
            z.writestr('Stintory/START-HERE.txt',f'Stintory {VERSION} public beta — {platform} / {mode}\n\nRun {name} (or {script}). Quit older tracker and Resolve before installing. Requires Python 3.12 recommended and Resolve Studio with Local external scripting. Read QUICKSTART-SK.txt and README.md. Source package, not a signed binary. Keep the folder in a stable location.\n')
    with zipfile.ZipFile(path) as z: assert z.testzip() is None
    return path

def main():
    a=argparse.ArgumentParser();a.add_argument('output',type=Path);ns=a.parse_args();ns.output.mkdir(parents=True,exist_ok=True)
    files=[pack(ns.output)]+[pack(ns.output,p,m) for p in ['Windows','macOS'] for m in ['linked','resident']]
    (ns.output/f'Stintory-{VERSION}-SHA256.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files))
    for p in files: print(p,p.stat().st_size)
if __name__=='__main__':main()
