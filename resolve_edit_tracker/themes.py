"""Semantic color tokens for explicit palettes."""
def dark(accent, secondary, hover, selected, bg='#1b1b1d', panel='#252527', edge='#3b3b3f'):
    return dict(BG=bg,PANEL=panel,EDGE=edge,TEXT='#f0f0ef',MUTED='#b0b0b4',GREEN=accent,BLUE=secondary,AMBER='#f4bf75',BUTTON='#303034',HOVER='#404044',PRIMARY_HOVER=hover,SELECTED=selected)
THEMES={
 'Steel':dark('#86b9e7','#587da5','#b4d5f1','#303d4c'),
 'Emerald':dark('#79ffce','#20c8aa','#acffe2','#203e37'),
 'Amethyst':dark('#ff79bd','#b681f8','#ffb2da','#432b45'),
 'Aurora':dark('#70d9ff','#9a8bff','#b0eaff','#293c55'),
 'Amber':dark('#ffc36e','#f18b72','#ffdfae','#433626'),
 'Ocean':dark('#76baff','#45d5d5','#acd6ff','#263b54'),
 'Lime':dark('#c6ee80','#8fcf91','#e0ffae','#35442b'),
 'Graphite':dark('#e4e9ed','#a0b0c1','#ffffff','#343c46'),
 'Light':dict(BG='#f2f4f7',PANEL='#ffffff',EDGE='#dce2e8',TEXT='#18222d',MUTED='#566575',GREEN='#00795f',BLUE='#426fae',AMBER='#8b5808',BUTTON='#e8edf2',HOVER='#dce4eb',PRIMARY_HOVER='#03694f',SELECTED='#d9eee7'),
}
OPTIONS=list(THEMES)
def normalize(name):
    # Migrate old System selections to the default palette.
    return name if isinstance(name,str) and name in OPTIONS else 'Steel'
def effective(name):
    return normalize(name)
