from datetime import datetime, date, time as dtime, timedelta

from .models import Stats

SESSION_DATE_FMT = "%Y-%m-%d %H:%M"


def hms(seconds):
    total = int(round(seconds))
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return "%d:%02d:%02d" % (h, m, s)


def money(amount, currency):
    symbol_first = not (len(currency) > 1 and currency[0].isalpha())
    from .currencies import digits, quantize
    value = f"{quantize(amount,currency):.{digits(currency)}f}"
    return currency + value if symbol_first else "%s %s" % (value, currency)


def session_date(ts):
    return datetime.fromtimestamp(ts).strftime(SESSION_DATE_FMT)


def parse_session_date(text):
    return datetime.strptime(text.strip(), SESSION_DATE_FMT).timestamp()


def start_of_day(ts):
    d = datetime.fromtimestamp(ts).date()
    return datetime.combine(d, dtime.min).timestamp()


def start_of_week(ts):
    """Weeks start on Monday."""
    d = datetime.fromtimestamp(ts).date()
    monday = d - timedelta(days=d.weekday())
    return datetime.combine(monday, dtime.min).timestamp()


def build_stats(sessions, current, project, now):
    allsessions = list(sessions)
    if current is not None:
        allsessions.append(current)
    day0 = start_of_day(now)
    week0 = start_of_week(now)
    week1 = week0 + 7 * 86400
    st = Stats(project=project)
    totals = {}
    for s in allsessions:
        if s.start >= day0:
            st.today_sec += s.duration_sec
        if week0 <= s.start < week1:
            st.week_sec += s.duration_sec
        if project and s.project == project:
            st.project_total_sec += s.duration_sec
            from .currencies import canonical
            k=canonical(s.currency)
            st.project_money[k]=st.project_money.get(k,0)+s.earnings
            for page, sec in s.page_seconds.items():
                totals[page] = totals.get(page, 0.0) + sec
    st.project_earnings = next(iter(st.project_money.values())) if len(st.project_money)==1 else 0.0
    st.breakdown = sorted(((p, v) for p, v in totals.items() if v >= 1), key=lambda x: -x[1])
    return st
