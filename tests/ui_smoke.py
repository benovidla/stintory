"""Headless UI smoke test (run under xvfb-run). Drives the real app against the simulated probe."""
import os, sys, tempfile, traceback
os.environ["RET_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import ImageGrab
from resolve_edit_tracker.app import TrackerApp
from resolve_edit_tracker import winapi
from resolve_edit_tracker.state import START_GRACE

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/shots"
os.makedirs(OUT, exist_ok=True)
problems = []

app = TrackerApp(simulate=True, use_tray=False)
app.root.geometry("+0+0")


def shot(name):
    try:
        app.root.update()
        ImageGrab.grab(xdisplay=os.environ["DISPLAY"]).save(os.path.join(OUT, name + ".png"))
    except Exception:
        problems.append("shot " + name + ": " + traceback.format_exc())


def guard(fn):
    def run():
        try:
            fn()
        except Exception:
            problems.append(traceback.format_exc())
    return run


# toast screenshot shortly after it appears
orig_show = app.toast.show
def show_and_shoot(**kw):
    orig_show(**kw)
    app.root.after(450, guard(lambda: shot("toast_" + kw["title"].replace(" ", "_"))))
app.toast.show = show_and_shoot
app.state.toast_fn = lambda **kw: app.toast.show(**kw)

def popup_open():
    app.popup.show()
    app.root.after(300, guard(lambda: shot("popup_tracking")))
def popup_pause():
    app.state.toggle_pause()
    app.popup.refresh()
    app.root.after(200, guard(lambda: shot("popup_paused")))
def popup_close():
    app.popup.hide()
def settings_open():
    app.open_settings()
    app.root.after(400, guard(lambda: shot("settings")))
def history_open():
    app.settings_win._close()
    app.state.add_manual_session("Wedding Sara & Tobias", __import__("time").time() - 7200, 95, "client call, <b>notes</b>", "color")
    app.state.add_manual_session("Demo Project", __import__("time").time() - 86400, 30, "", "edit")
    app.open_history()
    app.root.after(500, guard(lambda: shot("history")))
def dialogs():
    from resolve_edit_tracker.history_window import SessionDialog, TimesheetDialog
    sel = app.history_win.tree.get_children()
    app.history_win.tree.selection_set(sel[0])
    SessionDialog(app.history_win.win, app.state, app.history_win._selected()[0], lambda: None)
    app.root.after(400, guard(lambda: shot("edit_dialog")))
def finish():
    st = app.state
    print("state:", st.state, "| sessions:", len(st.sessions), "| elapsed: %.1f" % st.elapsed,
          "| project:", st.status.project, "| conn:", st.connection.kind)
    print("tooltip:", st.tray_tooltip)
    app.quit()

# probe: ~4 s no project, then "Demo Project"; tracking starts after START_GRACE
app.root.after(14000, guard(popup_open))
app.root.after(16000, guard(popup_pause))
app.root.after(17200, guard(popup_close))
app.root.after(17500, guard(settings_open))
app.root.after(19000, guard(history_open))
app.root.after(21000, guard(dialogs))
app.root.after(23500, guard(finish))
app.run()
print("PROBLEMS:", len(problems))
for p in problems:
    print(p)
print(sorted(os.listdir(OUT)))
