"""Dark, resizable desktop dashboard. The tracking engine remains UI-independent."""

from . import __version__

from .i18n import tr
import csv
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from collections import defaultdict
from . import fmt, models
from .ui_common import set_window_icon, bring_to_front, brand_photo, set_theme, apply_ttk_theme
from .themes import THEMES, normalize, effective
from .rounded import RoundedPanel, rounded_button_style
from .currencies import canonical

globals().update(THEMES['Steel'])
FONT=('Helvetica Neue' if __import__('sys').platform == 'darwin' else 'Segoe UI')
MOTION=True

def aggregate(sessions):
    """Project rollups including unassigned time, without double-counting."""
    projects={}
    for s in sessions:
        p=projects.setdefault(s.project,{'total':0.,'timelines':defaultdict(float),'pages':defaultdict(float),'earnings':defaultdict(float),'count':0})
        duration=max(0.,s.duration_sec)
        p['total']+=duration; p['count']+=1; p['earnings'][canonical(s.currency)]+=s.earnings
        # Older imported/manual time may have no timeline. Preserve it as unassigned.
        positive={k:max(0.,v) for k,v in s.timeline_seconds.items() if v>0}
        scale=min(1.,duration/sum(positive.values())) if positive else 1.
        for k,v in positive.items(): p['timelines'][k if k not in ('—','') else 'Unassigned']+=v*scale
        missing=duration-sum(positive.values())*scale
        if missing>0.00001: p['timelines']['Unassigned']+=missing
        for k,v in s.page_seconds.items(): p['pages'][k]+=max(0.,v)
    return projects


def csv_text(value):
    return "'"+value if value.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


def money(values):
    return '  /  '.join(fmt.money(v,k) for k,v in sorted(values.items())) or '—'


def label(parent, text='', size=10, color=None, bold=False, bg=None, **kw):
    return tk.Label(parent,text=text,bg=bg or PANEL,fg=color or TEXT,font=(FONT,size,'bold' if bold else 'normal'),anchor='w',**kw)


def button(parent, text, action, primary=False, selected=False):
    root=parent._root()
    theme=next((n for n,p in THEMES.items() if p['GREEN']==GREEN), 'Steel')
    b=ttk.Button(parent,text=text,command=action,cursor='hand2',width=0,style=rounded_button_style(root,theme,THEMES[theme],primary,selected))
    b._stintory_role=(primary,selected)
    return b


class Dashboard:
    def __init__(self, root, state, history, settings, quit, hide_request=None):
        self.root=root; self.state=state; self.history=history; self.settings=settings; self.quit=quit; self.hide_request=hide_request or self.hide
        self.win=None; self.mini=None; self.selected=None; self._tree_key=None; self._rows={}; self.projects={}; self._compact=False
        self.theme=effective(state.settings.theme)
        self._history_key=None; self._history_projects={}; self._aggregate_key=None; self._chart_key=None; self._row_values={}
        globals().update(THEMES[self.theme]); set_theme(self.theme); apply_ttk_theme(root)

    @property
    def visible(self):
        return bool((self.win and self.win.winfo_exists() and self.win.state() not in ('withdrawn','iconic')) or (self.mini and self.mini.winfo_exists() and self.mini.state() not in ('withdrawn','iconic')))

    def show(self, anchor=None):
        if not self.win or not self.win.winfo_exists(): self._build()
        if self.mini: self.mini.withdraw()
        self._compact=False; bring_to_front(self.win); self.refresh()

    def hide(self):
        if self.win: self.win.withdraw()
        if self.mini: self.mini.withdraw()
        self._compact=False

    def minimize(self):
        # Native taskbar fallback if a tray icon could not be registered.
        target = self.mini if self._compact and self.mini else self.win
        if target and target.winfo_exists(): target.iconify()

    def toggle(self, anchor=None):
        self.hide() if self.visible else self.show()

    def _build(self):
        w=self.win=tk.Toplevel(self.root); w.title('Stintory — Studio'); w.configure(bg=BG)
        w.geometry('1200x790'); w.minsize(1000,700); w.protocol('WM_DELETE_WINDOW',self.hide_request); set_window_icon(w)
        rail=tk.Frame(w,bg=PANEL,width=185); rail.pack(side='left',fill='y'); rail.pack_propagate(False)
        self.brand_image=brand_photo(166); self.brand_label=tk.Label(rail,image=self.brand_image,bg=PANEL,bd=0); self.brand_label.pack(padx=7,pady=(22,22))
        label(rail,tr('WORKSPACE'),9,MUTED,True).pack(fill='x',padx=16,pady=(0,8))
        for text,fn in [(tr('Overview'),self.show),(tr('Session history'),self.history),(tr('Mini timer'),self.compact),(tr('Hide to tray'),self.hide_request),(tr('Preferences'),self.settings)]:
            button(rail,text,fn,selected=(fn==self.show)).pack(fill='x',padx=12,pady=4)
        label(rail,f'v{__version__}',9,MUTED,wraplength=160,justify='left').pack(side='bottom',padx=12,pady=18)
        button(rail,tr('Data folder'),self._folder).pack(side='bottom',fill='x',padx=12,pady=(0,4))
        shell=tk.Frame(w,bg=BG); shell.pack(side='left',fill='both',expand=True,padx=22,pady=(16,10))
        # Persistent brand lockup is a true image of the chosen neon identity.
        header=tk.Frame(shell,bg=BG); header.pack(fill='x',pady=(0,12))
        label(header,tr('STUDIO   /   OVERVIEW'),10,MUTED,True,BG).pack(side='left',pady=8)
        nav=tk.Frame(header,bg=BG); nav.pack(side='right')
        
        self.status=label(nav,'',10,GREEN,True,BG); self.status.pack(side='right',padx=10)
        # A single heading and status hierarchy, not competing cards.
        titlebar=tk.Frame(shell,bg=BG); titlebar.pack(fill='x',pady=(0,12))
        label(titlebar,tr('Overview'),25,TEXT,True,BG).pack(side='left')
        label(titlebar,tr('DaVinci Resolve  /  Local workspace'),10,MUTED,bg=BG).pack(side='right',pady=(10,0))
        self._rounded=[]
        def panel(parent, **layout):
            outer=RoundedPanel(parent,background=BG,fill=PANEL,edge=EDGE,radius=19)
            self._rounded.append(outer)
            return outer
        hero_outer=panel(shell); hero_outer.pack(fill='x',pady=(0,12)); hero=hero_outer.content
        hero.grid_columnconfigure(0,weight=1); hero.grid_columnconfigure(1,weight=0,minsize=300)
        meta=tk.Frame(hero,bg=PANEL); meta.grid(row=0,column=0,sticky='nsew',padx=16,pady=9)
        label(meta,tr('NOW EDITING'),9,GREEN,True).pack(fill='x')
        self.live_project=label(meta,'',21,TEXT,True,wraplength=440,justify='left'); self.live_project.pack(fill='x',pady=(4,0))
        self.live_timeline=label(meta,'',11,MUTED,wraplength=440,justify='left'); self.live_timeline.pack(fill='x',pady=(1,7))
        self.conn=label(meta,'',9,MUTED,wraplength=455,justify='left'); self.conn.pack(fill='x')
        clock=tk.Frame(hero,bg=PANEL); clock.grid(row=0,column=1,sticky='nsew',padx=(8,14),pady=6)
        label(clock,tr('ACTIVE SESSION'),9,MUTED,True).pack(fill='x')
        self.timer=label(clock,'0:00:00',38,TEXT,True); self.timer.configure(font=(('Menlo' if __import__('sys').platform == 'darwin' else 'Consolas'),39,'normal')); self.timer.pack(fill='x')
        self.pause=button(clock,tr('Pause tracking'),self._pause,True); self.pause.pack(fill='x',pady=(1,0))
        # Four scannable metrics, no decorative duplicated timer.
        metrics=tk.Frame(shell,bg=BG); metrics.pack(fill='x',pady=(0,14)); self.metrics={}
        for i,(key,title) in enumerate([('today',tr('TODAY')),('week',tr('THIS WEEK')),('project',tr('PROJECT TOTAL')),('earn',tr('PROJECT EARNINGS'))]):
            metrics.columnconfigure(i,weight=1,uniform='metrics')
            card_outer=panel(metrics); card_outer.grid(row=0,column=i,sticky='nsew',padx=(0,9 if i!=3 else 0)); card=card_outer.content
            label(card,title,9,MUTED,True,wraplength=150,justify='left').pack(fill='x',padx=8,pady=(5,1)); val=label(card,'—',18,TEXT,True); val.pack(fill='x',padx=8,pady=(0,5)); self.metrics[key]=val
        body=tk.Frame(shell,bg=BG); body.pack(fill='both',expand=True); body.grid_columnconfigure(0,weight=3,minsize=420); body.grid_columnconfigure(1,weight=2,minsize=265); body.grid_rowconfigure(0,weight=1)
        project_outer=panel(body); project_outer.grid(row=0,column=0,sticky='nsew',padx=(0,12)); project=project_outer.content
        top=tk.Frame(project,bg=PANEL); top.pack(fill='x',padx=16,pady=(12,7)); label(top,tr('Projects'),16,TEXT,True).pack(side='left'); button(top,tr('Export'),self.export_menu).pack(side='right'); button(top,tr('Rate'),self.rate).pack(side='right',padx=7)
        self.search=tk.StringVar(); search_outer=RoundedPanel(project,background=PANEL,fill=BG,edge=EDGE,radius=12); search_outer.pack(fill='x',padx=12); self._search_panel=search_outer; entry=tk.Entry(search_outer.content,textvariable=self.search,bg=BG,fg=TEXT,insertbackground=TEXT,relief='flat',font=(FONT,11),highlightthickness=0); entry.pack(fill='x',padx=6,ipady=2); entry.bind('<FocusIn>',lambda _:search_outer.set_colors(PANEL,BG,BLUE)); entry.bind('<FocusOut>',lambda _:search_outer.set_colors(PANEL,BG,EDGE)); self.search.trace_add('write',lambda *_:self.refresh()); label(project,tr('Search projects or timelines  ·  Expand a project to see its timelines'),9,MUTED,wraplength=390,justify='left').pack(fill='x',padx=16,pady=(4,8))
        style=ttk.Style(w); style.configure('Stintory.Treeview',background=PANEL,fieldbackground=PANEL,foreground=TEXT,borderwidth=0,relief='flat',lightcolor=EDGE,darkcolor=EDGE,rowheight=32,font=(FONT,10)); style.configure('Stintory.Treeview.Heading',background=BUTTON,foreground=MUTED,borderwidth=0,font=(FONT,9,'bold'),padding=7); style.map('Stintory.Treeview',background=[('selected',SELECTED)],foreground=[('selected',TEXT)])
        table=tk.Frame(project,bg=PANEL); table.pack(fill='both',expand=True,padx=16,pady=(0,14)); self.tree=ttk.Treeview(table,columns=('time','share'),show='tree headings',style='Stintory.Treeview',selectmode='browse'); self.tree.heading('#0',text=tr('PROJECT / TIMELINE'),anchor='w'); self.tree.heading('time',text=tr('TIME'),anchor='e'); self.tree.heading('share',text=tr('SHARE'),anchor='e'); self.tree.column('#0',width=255,minwidth=150); self.tree.column('time',width=100,minwidth=85,anchor='e',stretch=False); self.tree.column('share',width=65,minwidth=60,anchor='e',stretch=False); self.tree.tag_configure('project',foreground=TEXT,font=(FONT,10,'bold')); self.tree.tag_configure('timeline',foreground=MUTED); self.tree.tag_configure('live',foreground=GREEN); self.tree.pack(side='left',fill='both',expand=True); style.configure('Stintory.Vertical.TScrollbar',background=BUTTON,troughcolor=BG,bordercolor=EDGE,arrowcolor=MUTED,lightcolor=BUTTON,darkcolor=BUTTON); scroll=ttk.Scrollbar(table,orient='vertical',command=self.tree.yview,style='Stintory.Vertical.TScrollbar'); scroll.pack(side='right',fill='y'); self.tree.configure(yscrollcommand=scroll.set); self.tree.bind('<<TreeviewSelect>>',self._select)
        details_outer=panel(body); details_outer.grid(row=0,column=1,sticky='nsew'); details=details_outer.content; head=tk.Frame(details,bg=PANEL); head.pack(fill='x',padx=16,pady=(13,4)); label(head,tr('Project insight'),16,TEXT,True).pack(side='left')
        self.detail=label(details,tr('Select a project'),11,MUTED,wraplength=310,justify='left'); self.detail.pack(fill='x',padx=16,pady=(4,0)); self.detail_total=label(details,'',20,GREEN,True); self.detail_total.pack(fill='x',padx=16,pady=(1,6))
        self.invoice_button=button(details,tr('Create PDF invoice'),self.invoice,True); self.invoice_button.pack(side='bottom',fill='x',padx=16,pady=(4,12))
        label(details,tr('TIME BY RESOLVE PAGE'),9,MUTED,True).pack(fill='x',padx=16,pady=(4,2)); self.chart=tk.Canvas(details,bg=PANEL,highlightthickness=0,height=95); self.chart.pack(fill='both',expand=True,padx=16,pady=(0,6)); self.chart.bind('<Configure>',lambda _:self._draw_chart())

    def relocalize(self):
        """Recreate localized widgets, not the tracker or the selected project."""
        if not self.win or not self.win.winfo_exists(): return
        geometry, visibility = self.win.geometry(), self.win.state()
        search = self.search.get()
        expanded = {n: self.tree.item(i, 'open') for n,i in self._rows.items() if self.tree.exists(i)}
        compact = self._compact and self.mini is not None
        mini_geometry = self.mini.geometry() if compact else None
        mini_visibility = self.mini.state() if compact else None
        if self.mini: self.mini.destroy()
        self.win.destroy()
        self.win = self.mini = None
        self._compact = False
        self._tree_key = self._chart_key = None
        self._rows = {}; self._row_values = {}
        self._build(); self.win.geometry(geometry)
        self.search.set(search)
        self.refresh()
        for n, opened in expanded.items():
            if n in self._rows: self.tree.item(self._rows[n], open=opened)
        if compact:
            self.compact(); self.mini.geometry(mini_geometry)
            if mini_visibility == 'iconic': self.mini.iconify()
            elif mini_visibility == 'withdrawn': self.mini.withdraw()
        elif visibility == 'withdrawn': self.win.withdraw()
        elif visibility == 'iconic': self.win.iconify()

    def apply_theme(self, name):
        name=effective(name)
        if name==self.theme:
            return
        old=THEMES[self.theme]; new=THEMES[name]
        replacements={old[key]:new[key] for key in old}
        self.theme=name; self._chart_key=None; self._row_values={}; globals().update(new); set_theme(name); apply_ttk_theme(self.root)
        def recolor(widget):
            if hasattr(widget,'_stintory_role'):
                widget.configure(style=rounded_button_style(self.root,name,new,*widget._stintory_role))
                return
            options={}
            for key in ('background','foreground','activebackground','activeforeground',
                        'highlightbackground','highlightcolor','insertbackground','disabledforeground'):
                if key in widget.keys():
                    value=str(widget.cget(key))
                    if value in replacements:
                        options[key]=replacements[value]
            if options: widget.configure(**options)
            for child in widget.winfo_children(): recolor(child)
        for w in self.root.winfo_children():
            if w and w.winfo_exists(): recolor(w)
        for panel in getattr(self,'_rounded',[]):
            if panel.winfo_exists(): panel.set_colors(BG,PANEL,EDGE)
        if hasattr(self,'_search_panel') and self._search_panel.winfo_exists(): self._search_panel.set_colors(PANEL,BG,EDGE)

        if self.win and self.win.winfo_exists():
            self.brand_image=brand_photo(166); self.brand_label.configure(image=self.brand_image,bg=PANEL)
            style=ttk.Style(self.win)
            style.configure('Stintory.Treeview',background=PANEL,fieldbackground=PANEL,foreground=TEXT,lightcolor=EDGE,darkcolor=EDGE)
            style.configure('Stintory.Treeview.Heading',background=BUTTON,foreground=MUTED)
            style.map('Stintory.Treeview',background=[('selected',SELECTED)],foreground=[('selected',TEXT)])
            style.configure('Stintory.Vertical.TScrollbar',background=BUTTON,troughcolor=BG,bordercolor=EDGE,arrowcolor=MUTED,lightcolor=BUTTON,darkcolor=BUTTON)
            self.tree.tag_configure('project',foreground=TEXT)
            self.tree.tag_configure('timeline',foreground=MUTED)
            self.tree.tag_configure('live',foreground=GREEN)
            self._draw_chart()
        self.refresh()

    def _pause(self):
        self.state.toggle_pause(); self.refresh()

    def _folder(self):
        if hasattr(os,'startfile'): os.startfile(self.state.store_directory)
        else: messagebox.showinfo(tr('Data folder'),self.state.store_directory,parent=self.win)

    def _all(self):
        return list(self.state.sessions)+([self.state.current] if self.state.current is not None else [])

    def refresh(self):
        global MOTION
        st=self.state; MOTION=st.settings.animations; active=st.status.project or st.active_project
        tracking=st.is_actively_tracking
        status=tr('●  TRACKING') if tracking else '●  '+(tr('PAUSED') if st.status.has_project else tr('STANDBY'))
        if self.mini and self._compact:
            self.mini_title.config(text=st.status.project or tr('Waiting for Resolve')); self.mini_time.config(text=fmt.hms(st.elapsed),fg=GREEN if tracking else TEXT); self.mini_status.config(text=status,fg=GREEN if tracking else MUTED); self.mini_pause.config(text=tr('Pause') if st.state==models.TRACKING else tr('Resume'),state='normal' if st.status.has_project else 'disabled')
        if not self.win or self.win.state() in ('withdrawn','iconic'): return
        self.status.config(text=status,fg=GREEN if tracking else AMBER if st.status.running else MUTED); self.live_project.config(text=st.status.project or tr('No project open')); self.live_timeline.config(text=st.status.timeline or tr('Waiting for timeline')); self.timer.config(text=fmt.hms(st.elapsed),fg=GREEN if tracking else TEXT); self.pause.config(text=tr('Pause') if st.state==models.TRACKING else tr('Resume'),state='normal' if st.status.has_project else 'disabled'); self.conn.config(text=(tr('Paused • resumes when you return to editing') if st.state==models.MANUALLY_PAUSED else st.status_line) + ('\n'+st.connection.detail if st.connection.detail else ''))
        # History rollups only when history changes; live session is the only mutable item.
        history_key=st.store.version
        if self._history_key!=history_key:
            self._history_projects=aggregate(st.sessions); self._history_key=history_key; self._aggregate_key=None
        current=st.current
        aggregate_key=(history_key,current.id if current else None,current.duration_sec if current else None,st.status.project)
        if aggregate_key!=self._aggregate_key:
            self._aggregate_key=aggregate_key
            self.projects=dict(self._history_projects)
            if current:
                import copy
                p=copy.deepcopy(self._history_projects.get(current.project,{'total':0.,'timelines':defaultdict(float),'pages':defaultdict(float),'earnings':defaultdict(float),'count':0}))
                q=aggregate([current])[current.project]
                p['total']+=q['total']; p['count']+=q['count']
                for field in ('timelines','pages','earnings'):
                    for k,v in q[field].items(): p[field][k]+=v
                self.projects[current.project]=p
        if st.status.project: self.projects.setdefault(st.status.project,{'total':0.,'timelines':{},'pages':{},'earnings':{},'count':0})
        p=self.projects.get(active,{})
        for k,v in [('today',fmt.hms(st.stats.today_sec)),('week',fmt.hms(st.stats.week_sec)),('project',fmt.hms(p.get('total',0))),('earn',money(p.get('earnings',{})))]: self.metrics[k].config(text=v)
        search=self.search.get().strip().casefold()
        names=[n for n in sorted(self.projects,key=lambda n:(n!=st.status.project,n.casefold())) if not search or search in n.casefold() or any(search in t.casefold() for t in self.projects[n]['timelines'])]
        key=tuple((n,tuple(sorted(self.projects[n]['timelines']))) for n in names)
        if key!=self._tree_key:
            opened={n:self.tree.item(i,'open') for n,i in self._rows.items() if self.tree.exists(i)}; self.tree.delete(*self.tree.get_children()); self._rows={}; self._row_values={}; self._tree_key=key
            for n in names:
                i=self.tree.insert('', 'end',text=n,open=opened.get(n,n==st.status.project or len(names)==1),tags=('project',)); self._rows[n]=i
                for t in sorted(self.projects[n]['timelines'],key=str.casefold): self.tree.insert(i,'end',text=t,tags=('timeline',))
            if self.selected in self._rows: self.tree.selection_set(self._rows[self.selected])
        for n,i in self._rows.items():
            p=self.projects[n]; live=n==st.status.project; self._set_row(i,(fmt.hms(p['total']),'100%' if p['total'] else '—'),('project','live') if live else ('project',))
            for child in self.tree.get_children(i):
                t=self.tree.item(child,'text'); v=p['timelines'][t]; self._set_row(child,(fmt.hms(v),f'{v/p["total"]:.0%}' if p['total'] else '—'),('live',) if live and t==st.status.timeline else ('timeline',))
        if self.selected not in self.projects: self.selected=active if active in self.projects else (names[0] if names else None)
        self._draw_chart()

    def _set_row(self,i,values,tags):
        key=(values,tags)
        if self._row_values.get(i)!=key:
            self.tree.item(i,values=values,tags=tags); self._row_values[i]=key

    def _select(self,event=None):
        selection=self.tree.selection()
        if selection:
            i=selection[0]; self.selected=self.tree.item(self.tree.parent(i) or i,'text'); self._draw_chart()

    def _draw_chart(self):
        if not hasattr(self,'chart'): return
        c=self.chart; p=self.projects.get(self.selected,{})
        key=(self.selected,self.theme,c.winfo_width(),c.winfo_height(),round(p.get('total',0)),tuple(sorted((k,round(v)) for k,v in p.get('pages',{}).items())))
        if self._chart_key==key: return
        self._chart_key=key; c.delete('all')
        self.detail.config(text=self.selected or tr('No project selected')); self.detail_total.config(text=fmt.hms(p.get('total',0)))
        rows=sorted(p.get('pages',{}).items(),key=lambda x:-x[1]); width=max(200,c.winfo_width()); height=max(100,c.winfo_height()); maximum=max([v for _,v in rows]+[1]); step=min(30,(height-6)/max(1,len(rows)))
        if not rows: c.create_text(4,25,text=tr('Tracked page activity will appear here.'),fill=MUTED,anchor='w',font=(FONT,10)); return
        for i,(page,seconds) in enumerate(rows):
            y=12+i*step; end=width-93; start=76; bar=max(1,(end-start)*seconds/maximum)
            c.create_text(0,y,text=models.page_display(page),fill=MUTED,anchor='w',font=(FONT,9)); c.create_line(start,y,end,y,fill=EDGE,width=9,capstyle='round'); c.create_line(start,y,start+bar,y,fill=GREEN if i==0 else BLUE,width=9,capstyle='round'); c.create_text(width-3,y,text=fmt.hms(seconds),fill=TEXT,anchor='e',font=(FONT,9))

    def compact(self):
        if not self.mini:
            m=self.mini=tk.Toplevel(self.root); m.title('Stintory • Mini'); m.configure(bg=PANEL); m.geometry('400x220'); m.resizable(False,False); m.attributes('-topmost',True); m.protocol('WM_DELETE_WINDOW',self.hide_request); set_window_icon(m)
            f=tk.Frame(m,bg=PANEL); f.pack(fill='both',expand=True,padx=15,pady=9); self.mini_title=label(f,'',12,TEXT,True); self.mini_title.pack(fill='x'); self.mini_status=label(f,'',9,GREEN,True); self.mini_status.pack(fill='x'); self.mini_time=label(f,'',27,TEXT,True); self.mini_time.pack(fill='x'); r=tk.Frame(f,bg=PANEL); r.pack(fill='x'); self.mini_pause=button(r,tr('Pause'),self._pause,True); self.mini_pause.pack(side='left'); button(r,tr('Expand'),self.show).pack(side='right'); button(f,tr('Hide to tray'),self.hide_request).pack(fill='x',pady=(5,0))
        self.win.withdraw(); self._compact=True; self.mini.deiconify(); self.refresh()

    def rate(self):
        project=self.selected or self.state.status.project
        if not project: return
        value=simpledialog.askfloat(tr('Project hourly rate'),f'{project}\nHourly rate ({self.state.settings.currency}). Applies to future sessions.',initialvalue=self.state.settings.rate_for(project),minvalue=0,parent=self.win)
        if value is not None:
            rates=dict(self.state.settings.projectRates); rates[project]=value; self.state.update_settings(projectRates=rates)

    def export(self):
        path=filedialog.asksaveasfilename(parent=self.win,defaultextension='.csv',initialfile='stintory-projects.csv',filetypes=[('CSV','*.csv')]);
        if not path: return
        try:
            with open(path,'w',encoding='utf-8-sig',newline='') as f:
                w=csv.writer(f); w.writerow(['Type','Project','Timeline','Seconds','Duration','Share'])
                for n,p in sorted(aggregate(self._all()).items()):
                    w.writerow(['Project',csv_text(n),'',round(p['total'],2),fmt.hms(p['total']),'100%'])
                    for t,v in sorted(p['timelines'].items()): w.writerow(['Timeline',csv_text(n),csv_text(t),round(v,2),fmt.hms(v),f'{v/p["total"]:.2%}' if p['total'] else ''])
        except OSError as e: messagebox.showerror('Export failed',str(e),parent=self.win)

    def export_menu(self):
        from .history_window import HistoryWindow
        menu=tk.Menu(self.win,tearoff=False,bg=PANEL,fg=TEXT,activebackground=SELECTED,activeforeground=TEXT)
        menu.add_command(label=tr('Project & timeline CSV'),command=self.export)
        menu.add_command(label=tr('Session CSV / HTML timesheet'),command=self.history)
        menu.add_command(label=tr('PDF invoice'),command=self.invoice)
        menu.tk_popup(self.win.winfo_pointerx(),self.win.winfo_pointery())

    def invoice(self):
        from .invoice import InvoiceWindow
        InvoiceWindow(self.win,self.state,self.selected or self.state.status.project)
