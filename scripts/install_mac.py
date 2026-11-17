#!/usr/bin/env python3
"""Configure per-user macOS launchers without modifying the Resolve application bundle."""
import argparse, os, plistlib, shlex, shutil, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HOME=Path.home()
APPS=HOME/'Applications'
VERSION=__import__("runpy").run_path(str(ROOT/"resolve_edit_tracker/__init__.py"))["__version__"]
AGENT=HOME/'Library/LaunchAgents/org.stintory.tracker.plist'
LABEL='org.stintory.tracker'
GUI=f'gui/{os.getuid()}' if hasattr(os,'getuid') else ''
DATA=HOME/'Library/Application Support/Stintory'

def migrate_legacy():
    """Upgrade only; do not overwrite or merge two existing histories."""
    old_data=HOME/'Library/Application Support/CutSync'
    if old_data.exists() and DATA.exists():
        raise RuntimeError('Both old and new data folders exist. Back them up and reconcile them before upgrading; neither was changed.')
    old_agent=HOME/'Library/LaunchAgents/org.cutsync.tracker.plist'
    if old_agent.exists():
        subprocess.run(['/bin/launchctl','bootout',GUI,str(old_agent)],check=False,capture_output=True)
        old_agent.unlink()
    if old_data.exists():
        DATA.parent.mkdir(parents=True,exist_ok=True)
        old_data.rename(DATA)
    # Old launcher icons may be removed manually after successful upgrade.

def unload():
    if AGENT.exists():
        subprocess.run(['/bin/launchctl','bootout',GUI,str(AGENT)],check=False,capture_output=True)
        AGENT.unlink(missing_ok=True)

def bundle(name, command, resolve=False):
    # Do not replace a third-party application at the same path.
    app=APPS/(name+'.app'); identifier='org.stintory.resolvelauncher' if resolve else 'org.stintory.desktop'
    if app.exists():
        info=app/'Contents/Info.plist'
        if not info.exists() or plistlib.loads(info.read_bytes()).get('CFBundleIdentifier') not in (identifier, 'org.cutsync.resolvelauncher' if resolve else 'org.cutsync.desktop'):
            raise RuntimeError(f'Refusing to replace unrelated application: {app}')
    exe=app/'Contents/MacOS/launch'; res=app/'Contents/Resources'
    exe.parent.mkdir(parents=True,exist_ok=True);res.mkdir(parents=True,exist_ok=True)
    # Use arrays/quoted arguments. Never invoke or alter the signed Resolve binary directly.
    text='#!/bin/bash\nset -e\nunset PYTHONHOME PYTHONPATH\n'
    if resolve:
        text+='if ! /usr/bin/open -a "DaVinci Resolve"; then\n /usr/bin/osascript -e '+shlex.quote('display alert "DaVinci Resolve not found" message "Install Resolve in Applications first."')+'\n exit 1\nfi\n'
    text+='exec '+shlex.join([str(x) for x in command])+'\n'
    exe.write_text(text);exe.chmod(0o755)
    (app/'Contents/Info.plist').write_bytes(plistlib.dumps(dict(CFBundleName=name,CFBundleDisplayName=name,CFBundleIdentifier=identifier,CFBundleExecutable='launch',CFBundlePackageType='APPL',CFBundleVersion=VERSION,CFBundleShortVersionString=VERSION,CFBundleIconFile='app.icns',NSHighResolutionCapable=True)))
    from PIL import Image
    Image.open(ROOT/'resolve_edit_tracker/assets/icon.png').save(res/'app.icns')
    return app

def install(mode):
    if sys.platform!='darwin': raise SystemExit('This installer requires macOS.')
    migrate_legacy()
    APPS.mkdir(exist_ok=True);DATA.mkdir(parents=True,exist_ok=True)
    unload()
    args=[sys.executable,str(ROOT/'run_tracker.py')]
    if mode=='linked':
        linked=bundle('DaVinci Resolve + Stintory',args+['--with-resolve','--wait-resolve'],True)
        print(f'Launch Resolve using {linked}. Drag that icon into your Dock.')
        bundle('Stintory',args+['--manual','--with-resolve'])
    else:
        bundle('Stintory',args+['--resident'])
        old=APPS/'DaVinci Resolve + Stintory.app'
        if old.exists():
            try:
                if plistlib.loads((old/'Contents/Info.plist').read_bytes()).get('CFBundleIdentifier') in ('org.stintory.resolvelauncher','org.cutsync.resolvelauncher'): shutil.rmtree(old)
            except (OSError,ValueError): pass
        AGENT.parent.mkdir(parents=True,exist_ok=True)
        AGENT.write_bytes(plistlib.dumps(dict(Label=LABEL,ProgramArguments=args+['--resident','--background'],RunAtLoad=True,ProcessType='Interactive',StandardOutPath=str(DATA/'login.log'),StandardErrorPath=str(DATA/'login-error.log'))))
        subprocess.run(['/bin/launchctl','bootstrap',GUI,str(AGENT)],check=True)
        print(f'Enabled resident login agent. Open {APPS / "Stintory.app"} for the dashboard.')
    (ROOT/'launch-mode.txt').write_text(mode)
    print('Keep the installation folder in its current location; reinstall if it moves.')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('mode',choices=['linked','resident','disable-login']);ns=a.parse_args()
    if ns.mode=='disable-login':
        if sys.platform!='darwin': raise SystemExit('macOS required')
        unload();print('Login agent disabled. No history deleted.')
    else: install(ns.mode)
