"""Subtle card corners. Redraw only on resize or theme changes, not timer ticks."""
import tkinter as tk
import math


class RoundedPanel(tk.Frame):
    def __init__(self, parent, *, background, fill, edge, radius=12):
        super().__init__(parent, bg=background, bd=0, highlightthickness=0)
        self.radius = radius
        self.inset = max(5, (radius+1)//2)
        self.colors = (background, fill, edge)
        self.canvas = tk.Canvas(self, bg=background, highlightthickness=0, bd=0)
        self.canvas.pack(fill='both', expand=True)
        self.content = tk.Frame(self.canvas, bg=fill, bd=0, highlightthickness=0)
        self.window = self.canvas.create_window(self.inset, self.inset, anchor='nw', window=self.content)
        self._size = None
        self._job = None
        self.canvas.bind('<Configure>', self._resize)
        self.content.bind('<Configure>', self._request)
        self._request()

    def _request(self, event=None):
        if self._job is None:
            self._job = self.after_idle(self._natural_size)

    def _natural_size(self):
        self._job = None
        if not self.winfo_exists(): return
        width = self.content.winfo_reqwidth()+2*self.inset
        height = self.content.winfo_reqheight()+2*self.inset
        if (int(self.canvas.cget('width')), int(self.canvas.cget('height'))) != (width,height):
            self.canvas.configure(width=width, height=height)

    def _resize(self, event=None):
        w,h=max(1,self.canvas.winfo_width()),max(1,self.canvas.winfo_height())
        if self._size == (w,h,self.colors): return
        self._size = (w,h,self.colors)
        self.canvas.itemconfigure(self.window,width=max(1,w-2*self.inset),height=max(1,h-2*self.inset))
        r=min(self.radius,w/2,h/2); x,y=w-1,h-1
        points=[]
        for cx,cy,angle in [(x-r,1+r,-90),(x-r,y-r,0),(1+r,y-r,90),(1+r,1+r,180)]:
            for k in range(13):
                a=math.radians(angle+90*k/12)
                points.extend((cx+r*math.cos(a),cy+r*math.sin(a)))
        self.canvas.delete('shape')
        self.canvas.create_polygon(points,fill=self.colors[1],outline=self.colors[2],width=1,tags='shape')
        self.canvas.tag_lower('shape')

    def set_colors(self,background,fill,edge):
        self.colors=(background,fill,edge)
        self.configure(bg=background); self.canvas.configure(bg=background); self.content.configure(bg=fill)
        self._resize()

    def destroy(self):
        if self._job is not None:
            try: self.after_cancel(self._job)
            except tk.TclError: pass
            self._job = None
        super().destroy()


def rounded_button_style(root, theme, colors, primary=False, selected=False):
    """Nine-slice image-backed native ttk button. No animation or redraw loop."""
    from tkinter import ttk
    from PIL import Image, ImageDraw, ImageTk
    from .ui_common import FONT
    role = 'Primary' if primary else 'Selected' if selected else 'Secondary'
    name = f'Stintory.{theme}.{role}'
    style = ttk.Style(root)
    cache = getattr(root, '_rounded_button_images', None)
    if cache is None:
        cache = root._rounded_button_images = {}
    if name not in cache:
        def image(fill, edge=None):
            im=Image.new('RGBA',(34*3,34*3))
            d=ImageDraw.Draw(im)
            d.rounded_rectangle((3,3,34*3-4,34*3-4),radius=11*3,fill=fill,outline=edge,width=3)
            return ImageTk.PhotoImage(im.resize((34,34),Image.Resampling.LANCZOS),master=root)
        base=colors['GREEN'] if primary else colors['SELECTED'] if selected else colors['BUTTON']
        hover=colors['PRIMARY_HOVER'] if primary else colors['HOVER']
        imgs=[image(base),image(hover),image(hover,colors['GREEN']),image(colors['PANEL'],colors['EDGE']),image(base,colors['BLUE'])]
        element=name+'.surface'
        style.element_create(element,'image',imgs[0],('disabled',imgs[3]),('pressed',imgs[2]),('focus',imgs[4]),('active',imgs[1]),border=15,sticky='nsew')
        cache[name]=imgs
        style.layout(name+'.TButton',[(element,{'sticky':'nsew','children':[('Button.padding',{'sticky':'nsew','children':[('Button.label',{'sticky':'nsew'})]})]})])
    fg=('#ffffff' if theme=='Light' else colors['BG']) if primary else colors['GREEN'] if selected else colors['TEXT']
    style.configure(name+'.TButton',font=(FONT,10,'bold'),foreground=fg,padding=(10,3),width=0,background=colors['PANEL'],anchor='center')
    style.map(name+'.TButton',foreground=[('disabled',colors['MUTED'])],background=[('active',colors['PANEL']),('pressed',colors['PANEL'])])
    return name+'.TButton'
