"""Billing currency preferences, not an exchange-rate service."""
import math
from decimal import Decimal, ROUND_HALF_UP

LANGUAGE_CURRENCIES = dict(en='USD', zh='CNY', hi='INR', es='EUR', ar='SAR', fr='EUR', bn='BDT', pt='BRL', id='IDR', ur='PKR', ru='RUB', de='EUR', ja='JPY', vi='VND', tr='TRY', ko='KRW', it='EUR', pl='PLN', cs='CZK', sk='EUR')
REGION_CURRENCIES = dict(US='USD', GB='GBP', AU='AUD', CA='CAD', NZ='NZD', IE='EUR', IN='INR', ZA='ZAR', CN='CNY', TW='TWD', HK='HKD', SG='SGD', ES='EUR', MX='MXN', AR='ARS', CL='CLP', CO='COP', PE='PEN', SA='SAR', AE='AED', EG='EGP', QA='QAR', KW='KWD', BH='BHD', OM='OMR', JO='JOD', FR='EUR', BE='EUR', CH='CHF', DE='EUR', AT='EUR', BR='BRL', PT='EUR', BD='BDT', ID='IDR', PK='PKR', RU='RUB', JP='JPY', VN='VND', TR='TRY', KR='KRW', IT='EUR', PL='PLN', CZ='CZK', SK='EUR', NL='EUR', SE='SEK', NO='NOK', DK='DKK', FI='EUR', HU='HUF', RO='RON', UA='UAH', IL='ILS', TH='THB', MY='MYR', PH='PHP', NG='NGN', KE='KES', MA='MAD', IS='ISK', KZ='KZT', GE='GEL')
CURRENCIES = tuple(sorted(set(REGION_CURRENCIES.values()) | set(LANGUAGE_CURRENCIES.values())))
ALIASES = {'€':'EUR','Kč':'CZK','KČ':'CZK','£':'GBP','zł':'PLN','₹':'INR','₽':'RUB','₩':'KRW','₫':'VND','₺':'TRY'}
# $ and ¥ are ambiguous and deliberately not mapped in legacy records.
def canonical(value):
    value=str(value or '').strip()
    return ALIASES.get(value, value.upper() if value.upper() in CURRENCIES else value)

# Display only: ISO codes remain the source of truth for billing and storage.
SYMBOLS = dict(AED='د.إ', ARS='$', AUD='A$', BDT='৳', BHD='د.ب', BRL='R$',
    CAD='C$', CHF='Fr', CLP='$', CNY='¥', COP='$', CZK='Kč', DKK='kr', EGP='£',
    EUR='€', GBP='£', GEL='₾', HKD='HK$', HUF='Ft', IDR='Rp', ILS='₪', INR='₹',
    ISK='kr', JOD='د.أ', JPY='¥', KES='KSh', KRW='₩', KWD='د.ك', KZT='₸',
    MAD='د.م.', MXN='Mex$', MYR='RM', NGN='₦', NOK='kr', NZD='NZ$', OMR='ر.ع.',
    PEN='S/', PHP='₱', PKR='₨', PLN='zł', QAR='ر.ق', RON='lei', RUB='₽',
    SAR='ر.س', SEK='kr', SGD='S$', THB='฿', TRY='₺', TWD='NT$', UAH='₴',
    USD='$', VND='₫', ZAR='R')

def currency_label(value):
    code = canonical(value)
    symbol = SYMBOLS.get(code)
    return f'{code} ({symbol})' if symbol else code

_LABEL_CODES = {currency_label(code): code for code in CURRENCIES}

def currency_from_label(value):
    # Never infer a code from an ambiguous $ or ¥ symbol.
    return _LABEL_CODES.get(value, canonical(value))

def default_currency(language, system_locale=None):
    if system_locale is None:
        import locale
        try: system_locale=locale.getlocale()[0] or ''
        except (ValueError,TypeError): system_locale='' 
    parts=system_locale.replace('-','_').split('_')
    if len(parts)>1 and parts[0].lower()==language:
        region=parts[-1].split('.')[0].upper()
        if region in REGION_CURRENCIES: return REGION_CURRENCIES[region]
    return LANGUAGE_CURRENCIES.get(language,'USD')

def digits(currency):
    code=canonical(currency)
    return 0 if code in {'JPY','KRW','VND','CLP','ISK'} else 3 if code in {'KWD','BHD','OMR','JOD'} else 2

def quantize(amount,currency):
    return Decimal(str(amount)).quantize(Decimal(1).scaleb(-digits(currency)),rounding=ROUND_HALF_UP)

def money_groups(sessions):
    out={}
    for s in sessions:
        k=canonical(s.currency)
        out[k]=out.get(k,0)+s.earnings
    return out

def clean_profiles(value):
    out={}
    if not isinstance(value,dict): return out
    for k,p in value.items():
        if not isinstance(p,dict): continue
        try:
            rate=float(p['rate']); rates={str(n):float(v) for n,v in p.get('projectRates',{}).items()}
            if not math.isfinite(rate) or rate<0: continue
            out[canonical(k)]={'rate':rate,'projectRates':{n:v for n,v in rates.items() if math.isfinite(v) and v>=0}}
        except (KeyError,ValueError,TypeError,OverflowError,AttributeError): continue
    return out

def billing_changes(old, changes):
    """Switch currency without carrying a numerical rate into a different denomination."""
    changes=dict(changes)
    mode=changes.get('currencyMode',old.currencyMode)
    target=(default_currency(changes.get('language',old.language)) if mode=='auto' else changes.get('currency',old.currency))
    if canonical(target)!=canonical(old.currency):
        profiles=clean_profiles(old.currencyProfiles)
        profiles[canonical(old.currency)]={'rate':old.rate,'projectRates':dict(old.projectRates)}
        profile=profiles.get(canonical(target),{'rate':0.0,'projectRates':{}})
        changes.update(currency=canonical(target),currencyProfiles=profiles)
        changes.setdefault('rate',profile['rate']); changes.setdefault('projectRates',dict(profile['projectRates']))
    elif mode=='auto': changes['currency']=target
    return changes
