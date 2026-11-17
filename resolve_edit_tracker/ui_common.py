"""Shared UI bits: palettes, DPI scaling, tray/window icons."""
import base64
import io
from pathlib import Path
from .themes import THEMES, effective
import tkinter as tk
from tkinter import ttk

from . import winapi

PALETTES = {
    "light": dict(bg="#fafafa", card="#ffffff", fg="#1c1c1e", muted="#6b6b70", border="#d6d6da",
                  track="#e6e6ea", accent="#e5484d", green="#30a46c", warn_bg="#fdf0dc", warn_fg="#7a5200",
                  btn="#ececf0", btn_hover="#e0e0e6", primary="#2f6fed", primary_hover="#255fd0",
                  primary_fg="#ffffff", danger="#c93b3b"),
    "dark": dict(bg="#232326", card="#2c2c30", fg="#f2f2f4", muted="#a0a0a8", border="#3d3d44",
                 track="#3a3a40", accent="#ff6369", green="#3dd68c", warn_bg="#463614", warn_fg="#f5d28a",
                 btn="#38383e", btn_hover="#45454c", primary="#3e7bff", primary_hover="#5a8fff",
                 primary_fg="#ffffff", danger="#ff7b7b"),
}


_theme = "Steel"


def set_theme(name):
    global _theme
    _theme = effective(name)


def palette():
    p = THEMES[_theme]
    return dict(PALETTES["dark"], bg=p["BG"], card=p["PANEL"], fg=p["TEXT"],
                muted=p["MUTED"], border=p["EDGE"], track=p["EDGE"], accent=p["GREEN"],
                green=p["GREEN"], btn=p["BUTTON"], btn_hover=p["HOVER"],
                primary=p["GREEN"], primary_hover=p["PRIMARY_HOVER"], primary_fg="#ffffff" if _theme=="Light" else p["BG"])


def brand_photo(width=178):
    from PIL import Image, ImageTk
    img = Image.open(Path(__file__).parent / "assets" / ("brand_light.png" if _theme=="Light" else "brand.png"))
    img.thumbnail((S(width), S(120)), Image.Resampling.LANCZOS)
    return ImageTk.PhotoImage(img)



class Scale:
    """Pixel sizes that follow the display scaling (125 %, 150 % ...)."""
    factor = 1.0

    @classmethod
    def init(cls, root):
        try:
            cls.factor = max(1.0, root.winfo_fpixels("1i") / 96.0)
        except tk.TclError:
            cls.factor = 1.0


def S(px):
    return int(round(px * Scale.factor))


FONT = ("Helvetica Neue" if __import__("sys").platform == "darwin" else "Segoe UI")


def font(size=9, weight="normal"):
    return (FONT, size, weight)


def apply_ttk_theme(root):
    style = ttk.Style(root)
    p=palette()
    style.theme_use('clam')
    style.configure('.',background=p['bg'],foreground=p['fg'],font=(FONT,10),bordercolor=p['border'],lightcolor=p['border'],darkcolor=p['border'],troughcolor=p['bg'],fieldbackground=p['card'],selectbackground=p['primary'],selectforeground=p['primary_fg'])
    style.configure('TFrame',background=p['bg'])
    style.configure('TLabel',background=p['bg'],foreground=p['fg'])
    style.configure('TLabelframe',background=p['bg'],bordercolor=p['border'],relief='solid',padding=14)
    style.configure('TLabelframe.Label',background=p['bg'],foreground=p['fg'],font=(FONT,11,'bold'))
    style.configure('TButton',padding=(12,7),background=p['btn'],foreground=p['fg'],borderwidth=1,relief='flat')
    style.map('TButton',background=[('active',p['btn_hover'])],foreground=[('disabled',p['muted'])])
    style.configure('TCheckbutton',background=p['bg'],foreground=p['fg'],padding=(0,4))
    style.map('TCheckbutton',background=[('active',p['bg'])],indicatorcolor=[('selected',p['primary']),('!selected',p['card'])])
    for name in ('TEntry','TCombobox','TSpinbox'):
        style.configure(name,foreground=p['fg'],fieldbackground=p['card'],background=p['btn'],insertcolor=p['fg'],padding=5,arrowcolor=p['fg'])
        style.map(name,fieldbackground=[('readonly',p['card'])],foreground=[('readonly',p['fg'])])
    style.configure('Treeview',background=p['card'],fieldbackground=p['card'],foreground=p['fg'],rowheight=32,borderwidth=0)
    style.configure('Treeview.Heading',background=p['btn'],foreground=p['fg'],font=(FONT,9,'bold'),padding=6)
    style.map('Treeview',background=[('selected',p['btn_hover'])],foreground=[('selected',p['fg'])])
    style.configure('Small.TLabel',foreground=p['muted'],font=(FONT,9))
    root.option_add('*TCombobox*Listbox.background',p['card']); root.option_add('*TCombobox*Listbox.foreground',p['fg'])
    root.option_add('*TCombobox*Listbox.selectBackground',p['btn_hover']); root.option_add('*TCombobox*Listbox.selectForeground',p['fg'])
    return style


# ------------------------------------------------------------------ icons (drawn with Pillow)

_icon_cache = {}


def make_icon_image(kind, size=64):
    """kind: idle | tracking | paused | warning. Returns a PIL image (RGBA)."""
    key = (kind, size)
    if key in _icon_cache:
        return _icon_cache[key]
    from PIL import Image, ImageDraw
    big = size * 4
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = big * 0.06
    box = [pad, pad, big - pad, big - pad]
    if kind in ("tracking", "brand", "idle"):
        asset = Path(__file__).parent / "assets"
        img = Image.open(asset / ("tray.png" if size <= 64 else "icon.png")).convert("RGBA")
        if kind == "idle":
            from PIL import ImageOps
            a = img.getchannel("A")
            img = ImageOps.grayscale(img).convert("RGBA")
            img.putalpha(a)
        out = img.resize((size, size), Image.Resampling.LANCZOS)
        _icon_cache[key] = out
        return out
    elif kind == "paused":
        d.ellipse(box, fill=(120, 124, 132, 255))
        w = big * 0.11
        for x in (big * 0.32, big * 0.57):
            d.rounded_rectangle([x, big * 0.28, x + w, big * 0.72], radius=w * 0.3, fill=(255, 255, 255, 255))
    elif kind == "warning":
        d.polygon([(big / 2, pad), (big - pad, big - pad), (pad, big - pad)], fill=(245, 166, 35, 255))
        d.rounded_rectangle([big * 0.46, big * 0.32, big * 0.54, big * 0.62], radius=big * 0.03, fill=(60, 40, 0, 255))
        d.ellipse([big * 0.455, big * 0.69, big * 0.545, big * 0.78], fill=(60, 40, 0, 255))
    else:   # idle: timer
        d.ellipse(box, outline=(120, 124, 132, 255), width=int(big * 0.09))
        d.line([(big / 2, big / 2), (big / 2, big * 0.27)], fill=(120, 124, 132, 255), width=int(big * 0.08))
        d.line([(big / 2, big / 2), (big * 0.66, big * 0.58)], fill=(120, 124, 132, 255), width=int(big * 0.08))
    out = img.resize((size, size), Image.LANCZOS)
    _icon_cache[key] = out
    return out


def tk_photo(kind="tracking", size=32):
    buf = io.BytesIO()
    make_icon_image(kind, size).save(buf, format="PNG")
    return tk.PhotoImage(data=base64.b64encode(buf.getvalue()))


def set_window_icon(win):
    # Tk on Windows uses native HICONs for both small and large icons when given
    # a multi-resolution ICO. Keep PNG fallback for other platforms.
    if winapi.IS_WIN:
        try:
            ico = Path(__file__).resolve().parent / "assets" / "app.ico"
            win.iconbitmap(default=str(ico))
            return
        except (tk.TclError, OSError):
            pass
    try:
        photo = tk_photo("brand", 64)
        win.iconphoto(True, photo)
        win._icon_ref = photo
    except Exception:
        pass


def bring_to_front(win):
    """Raise a window above Resolve even if Windows' focus-stealing prevention objects."""
    try:
        win.deiconify()
        win.lift()
        win.attributes("-topmost", True)
        win.after(250, lambda: win.attributes("-topmost", False))
        win.focus_force()
    except tk.TclError:
        pass
