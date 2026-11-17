"""Local PDF invoice draft. Historical rates/currencies are never silently converted."""

from .i18n import tr
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.sax.saxutils import escape
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .ui_common import palette, set_window_icon
from .fmt import hms, money
from .currencies import CURRENCIES, canonical, digits, quantize, currency_label, currency_from_label


def invoice_rows(sessions, project, currency, start=None, end=None, override_rate=None):
    if override_rate is not None:
        override_rate=Decimal(str(override_rate))
        if not override_rate.is_finite() or override_rate<0: raise ValueError(tr("Enter a valid hourly rate."))
    groups=defaultdict(float)
    for s in sessions:
        day=datetime.fromtimestamp(s.start).date()
        if (start and day<start) or (end and day>end): continue
        if s.project==project and s.duration_sec>0 and (override_rate is not None or canonical(s.currency)==canonical(currency)):
            groups[override_rate if override_rate is not None else s.rate]+=s.duration_sec
    return [(rate,seconds,quantize(Decimal(str(seconds))/Decimal(3600)*Decimal(str(rate)),currency)) for rate,seconds in sorted(groups.items())]


def write_invoice(path, fields, rows):
    from .i18n import tr as translate
    tr=lambda key: translate(key,fields.get('language','en'))
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as PDFImage
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    import os
    from .invoice_fonts import complex_text, raster_paragraph, supports_text, allows_pdf_subset
    language=fields.get('language','en')
    regular='Helvetica'; bold='Helvetica-Bold'; font_paths={}
    for base, r, b in [(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts','segoeui.ttf','segoeuib.ttf'),(Path('/System/Library/Fonts/Supplemental'),'Arial.ttf','Arial Bold.ttf'),(Path('/usr/share/fonts/truetype/dejavu'),'DejaVuSans.ttf','DejaVuSans-Bold.ttf')]:
        if (base/r).exists() and (base/b).exists() and allows_pdf_subset(base/r) and allows_pdf_subset(base/b):
            pdfmetrics.registerFont(TTFont('CSRegular',str(base/r)));pdfmetrics.registerFont(TTFont('CSBold',str(base/b)));regular='CSRegular';bold='CSBold';font_paths={regular:base/r,bold:base/b};break
    ink=colors.HexColor('#14222a'); muted=colors.HexColor('#64767b'); green=colors.HexColor('#315d87'); gray=colors.HexColor('#e8eeed')
    def p(value, size=10, strong=False, color=ink):
        font=bold if strong else regular
        if complex_text(value) or (font in font_paths and not supports_text(font_paths[font],value)) or (font not in font_paths and any(ord(c)>255 for c in str(value))):
            return raster_paragraph(value,size,strong,color,language)
        return Paragraph(escape(str(value)).replace('\n','<br/>'),ParagraphStyle('cs',fontName=bold if strong else regular,fontSize=size,leading=size*1.42,textColor=color,spaceAfter=0,splitLongWords=True))
    def table(data,widths,style):
        t=Table(data,colWidths=widths,repeatRows=1 if style=='lines' else 0,hAlign='LEFT'); rules=[('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),12),('RIGHTPADDING',(0,0),(-1,-1),12),('TOPPADDING',(0,0),(-1,-1),10),('BOTTOMPADDING',(0,0),(-1,-1),10)]
        if style=='lines':rules += [('BACKGROUND',(0,0),(-1,0),gray),('LINEBELOW',(0,1),(-1,-1),.5,gray)]
        t.setStyle(TableStyle(rules));return t
    total=sum((x[2] for x in rows),Decimal(0)); cur=fields['currency']; vat=Decimal(fields.get('vat','0')); tax=quantize(total*vat/100,cur)
    import tempfile
    # Build into memory, then atomically replace the destination after success.
    import io
    output=io.BytesIO()
    doc=SimpleDocTemplate(output,pagesize=A4,rightMargin=45,leftMargin=45,topMargin=44,bottomMargin=42,title='Stintory invoice '+fields['number'])
    W=A4[0]-90; story=[PDFImage(str(Path(__file__).parent/'assets'/'brand_light.png'),width=124,height=124*280/920,hAlign='LEFT'),Spacer(1,20),p(tr('INVOICE'),32,True),Spacer(1,6),p(fields['number']+'   /   '+tr('Issued')+' '+fields['issued']+'   /   '+tr('Due')+' '+fields['due'],10,False,muted),Spacer(1,20)]
    if fields.get('period_start') or fields.get('period_end'):
        story += [p(tr('Billing period')+'  /  '+(fields.get('period_start') or '—')+'  –  '+(fields.get('period_end') or '—'),10,False,muted),Spacer(1,12)]
    story += [table([[p(tr('FROM'),9,True,green),p(tr('BILL TO'),9,True,green)],[p(fields['supplier']),p(fields['client'])]],[W/2,W/2],'plain'),Spacer(1,16),p(tr('PROJECT'),9,True,green),p(fields['project'],18,True),Spacer(1,14)]
    data=[[p(tr('SERVICE'),9,True),p(tr('TIME'),9,True),p(tr('RATE / H'),9,True),p(tr('AMOUNT'),9,True)]]
    for rate,seconds,amount in rows:data.append([p(tr('Video editing')),p(hms(seconds)),p(f'{rate:.{max(2,digits(cur))}f} {cur}'),p(money(amount,cur),10,True)])
    story.extend([table(data,[W*.36,W*.20,W*.21,W*.23],'lines'),Spacer(1,20),table([[p(tr('Subtotal')),p(money(total,cur),12,True)],[p(f'{tr("VAT / tax")} ({vat}%)'),p(money(tax,cur),12,True)],[p(tr('TOTAL DUE'),13,True,green),p(money(total+tax,cur),20,True,green)]],[W*.58,W*.42],'plain'),Spacer(1,16),p(tr('PAYMENT DETAILS'),9,True,green),p(fields.get('payment','') or '—'),Spacer(1,14),p(fields.get('note',''),9,False,muted)])
    def footer(c,d):
        c.setStrokeColor(gray);c.line(45,32,A4[0]-45,32);c.setFont(regular,8);c.setFillColor(muted);footer_text=p('Stintory  •  '+tr('Time tracking for creators'),8,False,muted); _,fh=footer_text.wrap(W-35,22); footer_text.drawOn(c,45,20-fh/2); c.drawRightString(A4[0]-45,20,str(d.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    fd,tmp=tempfile.mkstemp(prefix='.stintory-invoice-',suffix='.tmp',dir=str(Path(path).resolve().parent))
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(output.getvalue());f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)


class InvoiceWindow:
    def __init__(self,parent,state,project):
        self.state=state; self.sessions=list(state.sessions); self.win=tk.Toplevel(parent); self.win.title(tr('Stintory — Invoice')); self.win.configure(bg=palette()['bg']); set_window_icon(self.win); self.win.geometry('730x760'); self.win.minsize(630,560)
        outer=ttk.Frame(self.win);outer.pack(fill='both',expand=True)
        canvas=tk.Canvas(outer,bg=palette()['bg'],highlightthickness=0);scroll=ttk.Scrollbar(outer,orient='vertical',command=canvas.yview);scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
        f=ttk.Frame(canvas,padding=20);item=canvas.create_window((0,0),window=f,anchor='nw');f.columnconfigure(1,weight=1);f.bind('<Configure>',lambda _:canvas.configure(scrollregion=canvas.bbox('all')));canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
        self.win.bind('<MouseWheel>',lambda e:canvas.yview_scroll(-int(e.delta/120) if abs(e.delta)>=120 else (-1 if e.delta>0 else 1),'units'))
        self.win.bind('<Button-4>',lambda _:canvas.yview_scroll(-1,'units'));self.win.bind('<Button-5>',lambda _:canvas.yview_scroll(1,'units'))
        ttk.Label(f,text=tr('Create invoice'),font=(('Helvetica Neue' if __import__('sys').platform == 'darwin' else 'Segoe UI'),21,'bold')).grid(row=0,column=0,columnspan=2,sticky='w'); ttk.Label(f,text=tr('Saved sessions only · review before sending'),style='Small.TLabel').grid(row=1,column=0,columnspan=2,sticky='w',pady=(0,12))
        self.vars={};self.texts={}; names=sorted({s.project for s in self.sessions}); self.project=tk.StringVar(value=project if project in names else (names[0] if names else ''));self.currency=tk.StringVar();
        ttk.Label(f,text=tr('Project')).grid(row=2,column=0,sticky='w'); self.projects=ttk.Combobox(f,textvariable=self.project,values=names,state='readonly');self.projects.grid(row=2,column=1,sticky='ew',pady=3);self.projects.bind('<<ComboboxSelected>>',self.update_project)
        ttk.Label(f,text=tr('Currency')).grid(row=3,column=0,sticky='w');self.currencies=ttk.Combobox(f,textvariable=self.currency,state='readonly');self.currencies.grid(row=3,column=1,sticky='ew',pady=3);self.currencies.bind('<<ComboboxSelected>>',self.change_currency)
        today=date.today(); defaults={'number':today.strftime('%Y%m%d')+'-001','issued':today.isoformat(),'due':(today+timedelta(days=14)).isoformat(),'vat':'0','payment':'','note':''}
        for i,(key,title) in enumerate([('number',tr('Invoice number')),('issued',tr('Issue date')),('due',tr('Due date')),('vat',tr('VAT / tax %')),('payment',tr('IBAN / payment')),('note',tr('Note'))],4):
            ttk.Label(f,text=title).grid(row=i,column=0,sticky='w'); v=self.vars[key]=tk.StringVar(value=defaults[key]);ttk.Entry(f,textvariable=v).grid(row=i,column=1,sticky='ew',pady=3)
        for i,(key,title) in enumerate([('supplier',tr('Supplier / legal details')),('client',tr('Client / legal details'))],10):
            ttk.Label(f,text=title,wraplength=155).grid(row=i,column=0,sticky='nw',pady=4); t=self.texts[key]=tk.Text(f,height=4,wrap='word',bg=palette()['card'],fg=palette()['fg'],insertbackground=palette()['fg'],font=(('Helvetica Neue' if __import__('sys').platform == 'darwin' else 'Segoe UI'),10),relief='flat',highlightthickness=1,highlightbackground=palette()['border']);t.grid(row=i,column=1,sticky='ew',pady=4)
        self.period_start=tk.StringVar();self.period_end=tk.StringVar()
        ttk.Label(f,text=tr('Billing period (optional)'),wraplength=155).grid(row=12,column=0,sticky='w')
        period=ttk.Frame(f);period.grid(row=12,column=1,sticky='ew',pady=3)
        ttk.Label(period,text=tr('From')).pack(side='left');ttk.Entry(period,textvariable=self.period_start,width=12).pack(side='left',padx=4)
        ttk.Label(period,text=tr('To')).pack(side='left');ttk.Entry(period,textvariable=self.period_end,width=12).pack(side='left',padx=4)
        ttk.Label(period,text='YYYY-MM-DD',style='Small.TLabel').pack(side='left')
        self.period_start.trace_add('write',lambda *_:self.refresh());self.period_end.trace_add('write',lambda *_:self.refresh())
        from .i18n import LANGUAGES, code_for
        self.lang=tk.StringVar(value=LANGUAGES[state.settings.invoiceLanguage]);ttk.Label(f,text=tr('Invoice language')).grid(row=13,column=0,sticky='w');ttk.Combobox(f,textvariable=self.lang,values=list(LANGUAGES.values()),state='readonly').grid(row=13,column=1,sticky='ew',pady=4)
        self.override=tk.StringVar()
        ttk.Label(f,text=tr('Invoice hourly rate (optional)'),wraplength=155).grid(row=14,column=0,sticky='w')
        ttk.Entry(f,textvariable=self.override).grid(row=14,column=1,sticky='ew',pady=4)
        ttk.Label(f,text=tr('Blank: saved rates in selected currency only. Enter a rate to reprice all saved time in this period, without changing history.'),style='Small.TLabel',wraplength=500).grid(row=15,column=0,columnspan=2,sticky='ew')
        self.summary=ttk.Label(f,text='',wraplength=500,font=(('Helvetica Neue' if __import__('sys').platform == 'darwin' else 'Segoe UI'),12,'bold'));self.summary.grid(row=16,column=0,columnspan=2,sticky='w',pady=12);ttk.Button(f,text=tr('Export PDF invoice'),command=self.export).grid(row=17,column=0,columnspan=2,sticky='ew'); self.override.trace_add('write',lambda *_:self.refresh()); self.update_project()
    def update_project(self,event=None):
        currencies=sorted({canonical(s.currency) for s in self.sessions if s.project==self.project.get()}); self.currencies['values']=[currency_label(c) for c in sorted(set(CURRENCIES)|set(currencies))]; preferred=canonical(self.state.settings.currency); self.currency.set(currency_label(preferred if preferred in currencies or not currencies else currencies[0])); self.override.set(''); self.refresh()
    def change_currency(self,event=None):
        self.override.set(''); self.refresh()
    def _period(self):
        try:
            a=date.fromisoformat(self.period_start.get().strip()) if self.period_start.get().strip() else None
            b=date.fromisoformat(self.period_end.get().strip()) if self.period_end.get().strip() else None
            if a and b and b<a: raise ValueError()
            return a,b
        except ValueError: raise ValueError(tr('Invalid billing period. Use YYYY-MM-DD.'))
    def _rows(self,start,end):
        text=self.override.get().strip().replace(',','.')
        try: rate=Decimal(text) if text else None
        except Exception: raise ValueError(tr('Enter a valid hourly rate.'))
        return invoice_rows(self.sessions,self.project.get(),currency_from_label(self.currency.get()),start,end,rate)
    def refresh(self,event=None):
        try:
            start,end=self._period(); rows=self._rows(start,end)
            note=''
            if not self.override.get().strip() and any(s.project==self.project.get() and canonical(s.currency)!=canonical(currency_from_label(self.currency.get())) and (not start or datetime.fromtimestamp(s.start).date()>=start) and (not end or datetime.fromtimestamp(s.start).date()<=end) for s in self.sessions):
                note='\n'+tr('Other currencies excluded unless you enter an invoice rate.')
            self.summary.config(text=f'{hms(sum(x[1] for x in rows))}  ·  {money(sum((x[2] for x in rows),Decimal(0)),currency_from_label(self.currency.get()))} {tr("before tax")}'+note)
        except (ValueError,ArithmeticError) as e: self.summary.config(text=str(e))
    def export(self):
        try:
            f={k:v.get().strip() for k,v in self.vars.items()};f.update({k:t.get('1.0','end-1c').strip() for k,t in self.texts.items()})
            from .i18n import code_for
            start,end=self._period()
            f.update(project=self.project.get(),currency=currency_from_label(self.currency.get()),language=code_for(self.lang.get()),period_start=start.isoformat() if start else '',period_end=end.isoformat() if end else ''); rows=self._rows(start,end); tax=Decimal(f['vat'].replace(',','.'));f['vat']=str(tax)
            if not tax.is_finite() or not 0<=tax<=100: raise ValueError(tr('Tax must be 0–100%.'))
            if date.fromisoformat(f['due'])<date.fromisoformat(f['issued']):raise ValueError(tr('Due date must be on or after issue date.'))
            if not rows or not all(f[k] for k in ('supplier','client','number')):raise ValueError(tr('Select saved sessions and complete supplier, client and invoice number.'))
            path=filedialog.asksaveasfilename(parent=self.win,defaultextension='.pdf',initialfile='Stintory-invoice.pdf',filetypes=[('PDF','*.pdf')]);
            if path:write_invoice(path,f,rows);messagebox.showinfo(tr('PDF saved'),path,parent=self.win)
        except Exception as e:messagebox.showerror(tr('Invoice'),str(e),parent=self.win)
