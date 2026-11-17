import csv
import math
import io

from . import fmt
from .models import Session
from .currencies import canonical, CURRENCIES, ALIASES


def export_csv(sessions):
    """Columns match the original Resolve script: Date, Duration, Earnings, Note."""
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(["Date", "Duration", "Earnings", "Note"])
    for s in sorted(sessions, key=lambda x: x.start):
        w.writerow([fmt.session_date(s.start), fmt.hms(s.duration_sec),
                    fmt.money(s.earnings, s.currency), safe_cell(s.note)])
    return out.getvalue()


def safe_cell(text):
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) or text.startswith(('\t','\r','\n')) else text


def _parse_hms(text):
    parts = []
    for p in text.split(":"):
        try:
            parts.append(float(p))
        except ValueError:
            return float('nan')
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def _money_currency(text, fallback):
    import re
    for k in sorted(set(CURRENCIES)|set(ALIASES),key=len,reverse=True):
        if text.startswith(k) or text.endswith(k): return k
    # Preserve an ambiguous legacy sign rather than guessing USD/CNY.
    for k in ("$", "¥", "₱"):
        if text.startswith(k) or text.endswith(k): return k
    remaining=re.sub(r"[0-9.,+\-\s]", "", text)
    return remaining or fallback

def _parse_money(text):
    cleaned = "".join(c for c in text if c.isdigit() or c in ".-")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def import_csv(text, default_currency):
    """Best effort. Imported rows have no per-page breakdown."""
    out = []
    text = text.lstrip("\ufeff")
    for i, cols in enumerate(csv.reader(io.StringIO(text))):
        cols = [c.strip() for c in cols]
        if i == 0 and cols and cols[0].lower().startswith("date"):
            continue
        if len(cols) < 3:
            continue
        try:
            start = fmt.parse_session_date(cols[0])
        except ValueError:
            continue
        dur = _parse_hms(cols[1])
        earn = _parse_money(cols[2])
        note = cols[3] if len(cols) >= 4 else ""
        if not math.isfinite(dur) or not math.isfinite(earn) or dur<=0 or earn<0: continue
        rate = earn / (dur / 3600.0)
        if not math.isfinite(rate): continue
        try: fmt.session_date(start+dur)
        except (ValueError,OverflowError,OSError): continue
        out.append(Session(project="Imported", start=start, end=start + dur,
                           duration_sec=dur, rate=rate, currency=_money_currency(cols[2],default_currency), note=note))
    return out
