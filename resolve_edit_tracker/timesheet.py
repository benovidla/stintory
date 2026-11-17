"""Printable HTML timesheet (open in a browser, then Print -> Save as PDF)."""
from datetime import datetime, date, time as dtime, timedelta
from dataclasses import dataclass
from typing import Optional

from . import fmt
from .models import page_display


@dataclass
class ReportRange:
    project: Optional[str]        # None = all projects
    start_day: date
    end_day: date                 # inclusive

    def contains(self, s):
        if self.project is not None and s.project != self.project:
            return False
        lo = datetime.combine(self.start_day, dtime.min).timestamp()
        hi = datetime.combine(self.end_day + timedelta(days=1), dtime.min).timestamp()
        return lo <= s.start < hi


def _escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _day_label(d):
    return "%s %d %s %d" % (d.strftime("%a"), d.day, d.strftime("%b"), d.year)


def _short_date(d):
    return "%d %s %d" % (d.day, d.strftime("%b"), d.year)


def build_html(sessions, rng, currency):
    rows = sorted((s for s in sessions if rng.contains(s)), key=lambda s: s.start)
    by_day = {}
    for s in rows:
        by_day.setdefault(datetime.fromtimestamp(s.start).date(), []).append(s)
    days = sorted(by_day)

    total_sec = sum(s.duration_sec for s in rows)
    from .currencies import money_groups

    def money(v, cur):
        return fmt.money(v, cur)

    def grouped(items):
        return " / ".join(_escape(money(v,"€" if k=="EUR" else k)) for k,v in sorted(money_groups(items).items())) or "—"

    def hours(sec):
        return "%.2f h" % (sec / 3600)

    body = ""
    for day in days:
        day_sessions = sorted(by_day[day], key=lambda s: s.start)
        day_sec = sum(s.duration_sec for s in day_sessions)
        body += "<tr class='day'><td colspan='5'>%s</td></tr>" % _day_label(day)
        for s in day_sessions:
            span = "%s–%s" % (datetime.fromtimestamp(s.start).strftime("%H:%M"),
                              datetime.fromtimestamp(s.end).strftime("%H:%M"))
            note = _escape(s.note) if s.note else ("manual entry" if s.manual else "")
            body += (
                "<tr><td class='t'>%s</td><td>%s</td><td class='r'>%s</td>"
                "<td class='r'>%s/h</td><td class='r'>%s</td></tr>"
            ) % (span, _escape(s.project), hours(s.duration_sec), _escape(money(s.rate,s.currency)), _escape(money(s.earnings,s.currency)))
            if note:
                body += "<tr class='note'><td></td><td colspan='4'>%s</td></tr>" % note
        body += (
            "<tr class='subtotal'><td colspan='2'>%s subtotal</td><td class='r'>%s</td><td></td>"
            "<td class='r'>%s</td></tr>"
        ) % (_day_label(day), hours(day_sec), grouped(day_sessions))

    page_agg, tl_agg = {}, {}
    for s in rows:
        for k, v in s.page_seconds.items():
            page_agg[k] = page_agg.get(k, 0.0) + v
        for k, v in s.timeline_seconds.items():
            tl_agg[k] = tl_agg.get(k, 0.0) + v

    def breakdown(d, transform):
        items = sorted(((k, v) for k, v in d.items() if v >= 1), key=lambda kv: -kv[1])
        return "".join("<li>%s – %s</li>" % (_escape(transform(k)), hours(v)) for k, v in items)

    page_html = breakdown(page_agg, page_display)
    tl_html = breakdown(tl_agg, lambda k: "No timeline" if k == "—" else k)

    title = rng.project or "All projects"
    period = "%s – %s" % (_short_date(rng.start_day), _short_date(rng.end_day))
    generated = datetime.now().strftime("%d.%m.%Y, %H:%M")

    return """<!doctype html><html><head><meta charset="utf-8">
<title>Timesheet – %(title)s</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body { font: 14px/1.5 "Segoe UI", system-ui, Arial, sans-serif; color: #1a1a1a; max-width: 820px; margin: 40px auto; padding: 0 24px; }
  h1 { font-size: 22px; margin: 0 0 2px; }
  .sub { color: #666; margin-bottom: 24px; }
  table { width: 100%%; border-collapse: collapse; margin: 8px 0 28px; }
  th, td { padding: 7px 10px; border-bottom: 1px solid #e6e6e6; text-align: left; vertical-align: top; }
  th { font-size: 11px; letter-spacing: .04em; text-transform: uppercase; color: #888; border-bottom: 2px solid #ccc; }
  td.r, th.r { text-align: right; font-variant-numeric: tabular-nums; }
  td.t { color: #666; font-variant-numeric: tabular-nums; white-space: nowrap; }
  tr.day td { padding-top: 18px; font-weight: 600; border-bottom: none; }
  tr.note td { color: #888; font-size: 12px; padding-top: 0; border-bottom: 1px solid #f0f0f0; }
  tr.subtotal td { font-weight: 600; border-bottom: 2px solid #ccc; }
  .total { display: flex; justify-content: space-between; align-items: baseline; padding: 14px 10px; background: #f6f6f6; border-radius: 8px; font-size: 16px; }
  .total b { font-size: 20px; }
  .cols { display: flex; gap: 40px; margin-top: 24px; }
  .cols h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .04em; color: #888; }
  .cols ul { margin: 6px 0; padding-left: 18px; color: #444; }
  footer { margin-top: 36px; color: #aaa; font-size: 12px; }
  @media print { body { margin: 0; max-width: none; } .total { background: none; border: 1px solid #ccc; } }
</style></head><body>
<h1>%(title)s</h1>
<div class="sub">Timesheet · %(period)s</div>
<table>
  <thead><tr><th>Time</th><th>Project</th><th class="r">Hours</th><th class="r">Rate</th><th class="r">Amount</th></tr></thead>
  <tbody>%(body)s</tbody>
</table>
<div class="total"><span>Total – %(total_h)s</span> <b>%(total_m)s</b></div>
<div class="cols">
  <div><h3>By page</h3><ul>%(pages)s</ul></div>
  <div><h3>By timeline</h3><ul>%(timelines)s</ul></div>
</div>
<footer>Generated %(generated)s by Stintory</footer>
</body></html>
""" % {
        "title": _escape(title),
        "period": period,
        "body": body or "<tr><td colspan='5'>No sessions in this range.</td></tr>",
        "total_h": hours(total_sec),
        "total_m": grouped(rows),
        "pages": page_html or "<li>–</li>",
        "timelines": tl_html or "<li>–</li>",
        "generated": generated,
    }
