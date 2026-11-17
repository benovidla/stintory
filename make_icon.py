"""Copy the checked-in multi-resolution icon without resampling tiny variants."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
shutil.copyfile(root/'resolve_edit_tracker/assets/app.ico',root/'app.ico')
print('app.ico written')
