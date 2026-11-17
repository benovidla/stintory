"""Local-font PDF support for complex writing systems, loaded only during PDF export.
Shape non-Latin runs via Pillow/Raqm before drawing them at 288 dpi. Never silently
substitute missing characters. No font files are distributed with Stintory.
"""
from functools import lru_cache
from pathlib import Path
import os
import unicodedata


def complex_text(value):
    return any(0x0590 <= ord(c) <= 0x0DFF or 0x2E80 <= ord(c) <= 0xD7FF or 0xF900 <= ord(c) <= 0xFAFF or 0xFE70 <= ord(c) <= 0xFEFF or 0x20000 <= ord(c) <= 0x2FA1F for c in str(value))


def rtl_text(value):
    return any(unicodedata.bidirectional(c) in ('R','AL') for c in str(value))


def _needed(value):
    return frozenset(ord(c) for c in str(value) if not c.isspace() and unicodedata.category(c) not in ('Cc','Cf'))


@lru_cache(maxsize=96)
def _coverage(path,index):
    from fontTools.ttLib import TTFont
    try:
        f=TTFont(str(path),fontNumber=index,lazy=True)
        try: return frozenset(f.getBestCmap() or {})
        finally: f.close()
    except Exception: return frozenset()


def _font_candidates(language,strong):
    windows=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
    mac=Path('/System/Library/Fonts'); supplemental=mac/'Supplemental'
    linux=Path('/usr/share/fonts')
    user=Path.home()/'Library/Fonts'
    paths=[]
    def add(base, names, indices=(0,)):
        for n in names:
            for i in indices: paths.append((base/n,i))
    # Locale-appropriate fonts first. These paths are probed, never bundled.
    if language in ('zh','ja','ko'):
        w={'zh':['msyhbd.ttc','msyh.ttc','simsun.ttc'],'ja':['meiryob.ttc','meiryo.ttc','msgothic.ttc'],'ko':['malgunbd.ttf','malgun.ttf','gulim.ttc']}[language]
        add(windows,w if strong else list(reversed(w)))
        add(mac,{'zh':['PingFang.ttc','STHeiti Medium.ttc'],'ja':['ヒラギノ角ゴシック W6.ttc','ヒラギノ角ゴシック W3.ttc'],'ko':['AppleSDGothicNeo.ttc']}[language])
        add(supplemental,['Arial Unicode.ttf','Songti.ttc'])
        idx={'zh':2,'ja':0,'ko':1}[language]
        add(linux/'opentype/noto',['NotoSansCJK-Bold.ttc' if strong else 'NotoSansCJK-Regular.ttc'],(idx,))
    elif language in ('hi','bn'):
        add(windows,['NirmalaB.ttf','Nirmala.ttf'] if strong else ['Nirmala.ttf','NirmalaB.ttf']);add(windows,['mangal.ttf','vrinda.ttf'])
        add(mac,['KohinoorDevanagari.ttc','KohinoorBangla.ttc']);add(supplemental,['Devanagari Sangam MN.ttc','Bangla Sangam MN.ttc','Arial Unicode.ttf'])
        add(linux/'truetype/freefont',['FreeSansBold.ttf' if strong else 'FreeSans.ttf','FreeSerif.ttf'])
    elif language in ('ar','ur'):
        add(windows,['arialbd.ttf' if strong else 'arial.ttf','tahoma.ttf','segoeui.ttf']);add(mac,['GeezaPro.ttc','SFArabic.ttf']);add(supplemental,['Arial.ttf','Arial Unicode.ttf'])
    add(windows,['segoeuib.ttf' if strong else 'segoeui.ttf','arialbd.ttf' if strong else 'arial.ttf','Nirmala.ttf','msyh.ttc','meiryo.ttc','malgun.ttf'])
    add(supplemental,['Arial Bold.ttf' if strong else 'Arial.ttf','Arial Unicode.ttf','Devanagari Sangam MN.ttc','Bangla Sangam MN.ttc'])
    add(mac,['PingFang.ttc','KohinoorDevanagari.ttc','KohinoorBangla.ttc','GeezaPro.ttc','AppleSDGothicNeo.ttc'])
    add(linux/'truetype/dejavu',['DejaVuSans-Bold.ttf' if strong else 'DejaVuSans.ttf'])
    add(linux/'truetype/freefont',['FreeSerifBold.ttf' if strong else 'FreeSerif.ttf','FreeSans.ttf'])
    add(linux/'opentype/noto',['NotoSansCJK-Regular.ttc'])
    # User-installed Arial/Noto fonts can repair missing OS language packs.
    extra=os.environ.get('STINTORY_INVOICE_FONT')
    if extra: paths.insert(0,(Path(extra).expanduser(),0))
    if user.is_dir():
        for path in sorted(user.glob('Noto*')):
            if path.suffix.lower() in ('.ttf','.otf','.ttc'): paths.append((path,0))
    for path,index in dict.fromkeys(paths):
        if path.is_file(): yield str(path),index


def _resolve(value,language,strong):
    needed=_needed(value)
    for path,index in _font_candidates(language,strong):
        if needed <= _coverage(path,index): return path,index
    raise RuntimeError('No local font covers the invoice text. Install the appropriate OS language fonts, or set STINTORY_INVOICE_FONT to a compatible font. Text was not exported.')


def _clusters(word):
    """Do not split combining marks or a joined sequence from its previous glyph."""
    clusters=[]
    for char in word:
        if clusters and (unicodedata.category(char).startswith('M') or char in ('\u200d','\u200c') or clusters[-1].endswith(('\u200d','\u094d','\u09cd'))): clusters[-1]+=char
        else: clusters.append(char)
    return clusters


def raster_paragraph(value,size,strong,color,language):
    from PIL import Image,ImageDraw,ImageFont,features
    from reportlab.platypus import Flowable
    from reportlab.lib.utils import ImageReader
    text=str(value)
    if not features.check('raqm') and any(0x0590 <= ord(c) <= 0x0DFF for c in text):
        raise RuntimeError('This invoice requires Pillow with Raqm text shaping. Install a supported Pillow build before exporting.')
    path,index=_resolve(text,language,strong)
    scale=4
    face=ImageFont.truetype(path,max(1,round(size*scale)),index=index,layout_engine=ImageFont.Layout.RAQM if features.check('raqm') else ImageFont.Layout.BASIC)
    direction='rtl' if rtl_text(text) else 'ltr'
    opts={'direction':direction} if features.check('raqm') else {}
    rgba=tuple(round(c*255) for c in (color.red,color.green,color.blue))+(255,)

    class ShapedText(Flowable):
        def wrap(self,available_width,available_height):
            self.width=max(1,available_width)
            max_w=max(1,int(self.width*scale)-4)
            def measure(s): return face.getlength(s,**opts)
            lines=[]
            for para in text.split('\n'):
                current=''
                for word in para.split(' '):
                    trial=(current+' '+word).strip() if current else word
                    if measure(trial)<=max_w: current=trial;continue
                    if current: lines.append(current);current=''
                    if measure(word)<=max_w: current=word;continue
                    for cluster in _clusters(word):
                        if current and measure(current+cluster)>max_w:lines.append(current);current=''
                        current+=cluster
                lines.append(current)
            metrics=[]
            default_h=max(1,int(size*scale*1.45))
            for line in lines:
                bbox=face.getbbox(line or ' ',**opts)
                metrics.append((line,bbox,max(default_h,bbox[3]-bbox[1]+6)))
            height=sum(x[2] for x in metrics)+2
            im=Image.new('RGBA',(max_w+4,height),(255,255,255,0));draw=ImageDraw.Draw(im);y=1
            for line,bb,h in metrics:
                x=(max_w-(bb[2]-bb[0]) if direction=='rtl' else 1)-bb[0]
                draw.text((x,y+(h-bb[3]+bb[1])//2-bb[1]),line,font=face,fill=rgba,**opts);y+=h
            self.picture=ImageReader(im);self.height=height/scale
            return self.width,self.height
        def draw(self):
            self.canv.drawImage(self.picture,0,0,width=self.width,height=self.height,mask='auto')
    return ShapedText()


def supports_text(path,value,index=0):
    return _needed(value) <= _coverage(str(path),index)


@lru_cache(maxsize=32)
def allows_pdf_subset(path):
    """Only embed outline fonts whose OS/2 flags allow preview/print and subsetting.
    This is a technical safeguard, not a substitute for the font's license.
    """
    from fontTools.ttLib import TTFont
    try:
        with TTFont(str(path), lazy=True) as f:
            flags = int(f['OS/2'].fsType)
            return not bool(flags & (0x0002 | 0x0100 | 0x0200))
    except Exception:
        return False
