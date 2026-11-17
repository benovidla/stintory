"""Run each unit test module in a fresh process; exit on first failed or timed out module."""
from pathlib import Path
import subprocess,sys
root=Path(__file__).resolve().parents[1]
for path in sorted((root/'tests').glob('test_*.py')):
    print(f'--- {path.name} ---',flush=True)
    subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',path.name,'-v'],cwd=root,check=True,timeout=60)
print('ALL TEST MODULES PASSED',flush=True)
