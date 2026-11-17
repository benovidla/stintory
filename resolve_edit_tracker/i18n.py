"""UI locale and independent invoice locale. Order: total speakers, not popularity of Stintory."""
from pathlib import Path
import json
# Approximate L1+L2 order among the selected languages (Ethnologue 2026).
LANGUAGES = {
    'en':'English', 'zh':'简体中文 (Chinese)', 'hi':'हिन्दी (Hindi)', 'es':'Español',
    'ar':'العربية (Arabic)', 'fr':'Français', 'bn':'বাংলা (Bengali)', 'pt':'Português',
    'id':'Bahasa Indonesia', 'ur':'اردو (Urdu)', 'ru':'Русский', 'de':'Deutsch',
    'ja':'日本語 (Japanese)', 'vi':'Tiếng Việt', 'tr':'Türkçe', 'ko':'한국어 (Korean)',
    'it':'Italiano', 'pl':'Polski', 'cs':'Čeština', 'sk':'Slovenčina',
}
CATALOG = json.loads((Path(__file__).parent/'assets'/'translations.json').read_text(encoding='utf-8'))
_current = 'en'
def normalize_language(code):
    return code if isinstance(code,str) and code in LANGUAGES else 'en'
def set_language(code):
    global _current
    _current = normalize_language(code)
def tr(key, lang=None):
    return CATALOG.get(normalize_language(lang if lang is not None else _current), {}).get(key,key)
def code_for(name):
    return next((k for k,v in LANGUAGES.items() if v==name),'en')
