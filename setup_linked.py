"""Configure Stintory Linked without round-tripping Unicode paths through CMD."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def configure(root, executable, windows, run):
    pythonw = executable.with_name('pythonw.exe')
    if not pythonw.is_file():
        raise FileNotFoundError(f'pythonw.exe not found: {pythonw}')
    for name in ('link_resolve.ps1', 'make_shortcut.vbs', 'launch_with_resolve.vbs', 'run_tracker.pyw', 'launch_resolve.pyw'):
        if not (root / name).is_file():
            raise FileNotFoundError(f'Missing {name}; copy the repair files into the Stintory folder.')
    system = windows / 'System32'
    powershell = system / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
    run('Disable old login startup', [str(executable), '-m', 'resolve_edit_tracker', '--disable-autostart'])
    run('Link Resolve desktop shortcut', [str(powershell), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(root / 'link_resolve.ps1'), '-Python', str(pythonw)])
    run('Create Stintory desktop shortcut', [str(system / 'cscript.exe'), '//nologo', str(root / 'make_shortcut.vbs')])
    from linked_task import install
    install(root, windows, pythonw, run)
    (root / 'launch-mode.txt').write_text('linked\n', encoding='ascii')


def main():
    if sys.platform != 'win32':
        print('This repair is for Windows only.')
        return 1
    log = ROOT / 'setup-linked.log'
    try:
        sys.stdout.reconfigure(errors='backslashreplace')
        if not (ROOT / 'resolve_edit_tracker').is_dir():
            raise FileNotFoundError('Copy these repair files into the extracted Stintory folder.')
        with log.open('w', encoding='utf-8') as f:
            def report(message):
                print(message, flush=True)
                f.write(message + '\n'); f.flush()
            def run(stage, argv):
                report('\n=== ' + stage + ' ===')
                report(subprocess.list2cmdline(argv))
                result = subprocess.run(argv, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, errors='replace', check=False)
                if result.stdout:
                    report(result.stdout.rstrip())
                if result.returncode:
                    raise RuntimeError(f'{stage} failed (exit code {result.returncode}).')
            try:
                configure(ROOT, Path(sys.executable), Path(os.environ['WINDIR']), run)
            except Exception as exc:
                report(f'FAILED: {exc}')
                return 1
            report('ALL GOOD. Desktop shortcut starts immediately; other shortcuts are checked within one minute.')
        return 0
    except Exception as exc:
        print(f'FAILED: {exc}')
        return 1
    finally:
        print(f'Diagnostic log: {log}')


if __name__ == '__main__':
    raise SystemExit(main())
