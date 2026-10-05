#!/usr/bin/env python3
import json, re, urllib.request, hashlib
from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote

from icalendar import Calendar

try:
    import recurring_ical_events
except ImportError:
    recurring_ical_events = None

CALENDAR_ID = "c_5f2f898e5112aba62b3c823ee15c2d3c381fed0e2a47196908dc0459427654c9@group.calendar.google.com"
TZ = ZoneInfo("America/Los_Angeles")
PUBLIC_ICS = "https://calendar.google.com/calendar/ical/" + quote(CALENDAR_ID, safe="") + "/public/basic.ics"

def clean(v):
    return str(v or "").strip()

def kind(summary):
    s=summary.lower()
    if "christmas break" in s: return "break"
    if "tentative" in s: return "tentative"
    if "tryout" in s: return "tryout"
    if "practice" in s: return "practice"
    if "open gym" in s: return "open-gym"
    if "basketball @" in s or "basketball vs." in s: return "game"
    return "event"

def web_title(summary):
    s=summary
    if s == "Cascade Basketball Open Gym": return "Open Gym"
    m=re.match(r"(?i)^Cascade boys basketball @ (.*?)(?: \(time TBD\))?$",s)
    if m: return "Varsity @ " + m.group(1)
    m=re.match(r"(?i)^Cascade boys basketball vs\. (.*?)(?: \(time TBD\))?$",s)
    if m: return "Varsity vs. " + m.group(1)
    if s == "Boys Tryouts — Main Gym": return "Boys Tryouts"
    if s == "JV/Varsity Practice — Main Gym": return "JV/Varsity Practice"
    if s == "JV2 Practice — Aux Gym": return "JV2 Practice"
    if s == "TENTATIVE — JV/Varsity Practice — Main Gym": return "TENTATIVE — JV/Varsity Practice"
    if s == "TENTATIVE — JV2 Practice — Aux Gym": return "TENTATIVE — JV2 Practice"
    return s

def web_location(summary, location, k):
    if k=="game":
        return "Away" if " @ " in summary else "Home"
    return location.replace("Cascade High School — ","").strip()

def fmt_clock(dt):
    return dt.astimezone(TZ).strftime("%-I:%M %p")

def fmt_range(start,end):
    a=fmt_clock(start); b=fmt_clock(end)
    ap=a[-2:]; bp=b[-2:]
    if ap==bp: a=a[:-3]
    return f"{a}–{b}"

def as_datetime(v):
    if isinstance(v, datetime):
        if v.tzinfo is None: return v.replace(tzinfo=TZ)
        return v
    return datetime.combine(v,time.min,tzinfo=TZ)

def get_events(cal):
    now=datetime.now(TZ)
    start=datetime(now.year-1,1,1,tzinfo=TZ)
    end=datetime(now.year+2,1,1,tzinfo=TZ)
    if recurring_ical_events:
        return recurring_ical_events.of(cal).between(start,end)
    return [x for x in cal.walk("VEVENT")]

def escape_ics(s):
    return str(s).replace("\\","\\\\").replace("\n","\\n").replace(",","\\,").replace(";","\\;")

with urllib.request.urlopen(PUBLIC_ICS, timeout=30) as resp:
    raw=resp.read()

cal=Calendar.from_ical(raw)
components=get_events(cal)
web=[]
ics_events=[]

for ev in components:
    summary=clean(ev.get("SUMMARY"))
    if not summary: continue
    dtstart=ev.decoded("DTSTART")
    dtend=ev.decoded("DTEND") if ev.get("DTEND") else None
    location=clean(ev.get("LOCATION"))
    k=kind(summary)
    all_day=isinstance(dtstart,date) and not isinstance(dtstart,datetime)

    if all_day:
        d0=dtstart
        d1=dtend if isinstance(dtend,date) and not isinstance(dtend,datetime) else d0+timedelta(days=1)
        if k=="break":
            d=d0
            while d<d1:
                web.append({"date":d.isoformat(),"time":"No Practice","title":"Christmas Break — No Practice","location":"","kind":"break"})
                d+=timedelta(days=1)
        else:
            web.append({"date":d0.isoformat(),"time":"TBD" if "time tbd" in summary.lower() else "All Day","title":web_title(summary),"location":web_location(summary,location,k),"kind":k})
        start_iso=d0.strftime("%Y%m%d")
        end_iso=d1.strftime("%Y%m%d")
        ics_events.append(("date",start_iso,end_iso,summary,location,k))
    else:
        s=as_datetime(dtstart).astimezone(TZ)
        e=as_datetime(dtend).astimezone(TZ) if dtend else s+timedelta(hours=2)
        web.append({"date":s.date().isoformat(),"time":fmt_range(s,e),"title":web_title(summary),"location":web_location(summary,location,k),"kind":k})
        ics_events.append(("time",s.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ"),e.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ"),summary,location,k))

web.sort(key=lambda x:(x["date"],x["time"],x["title"]))
with open("calendar-data.js","w",encoding="utf-8") as f:
    f.write("// Auto-generated from Cascade Boys Basketball Google Calendar.\n")
    f.write("window.CASCADE_CALENDAR_EVENTS = ")
    json.dump(web,f,ensure_ascii=False,separators=(",",":"))
    f.write(";\n")

ics_events.sort(key=lambda x:(x[1],x[3],x[4],x[2]))
stamp="20261005T000000Z"
lines=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Cascade Boys Basketball//Program Calendar//EN","CALSCALE:GREGORIAN","METHOD:PUBLISH","X-WR-CALNAME:Cascade Boys Basketball","X-WR-TIMEZONE:America/Los_Angeles","REFRESH-INTERVAL;VALUE=DURATION:PT6H","X-PUBLISHED-TTL:PT6H"]
for typ,ds,de,summary,location,k in ics_events:
    uid=hashlib.sha1(f"{ds}|{summary}|{location}".encode()).hexdigest()[:20]+"@cascadecougarsbasketball.com"
    lines+=["BEGIN:VEVENT","UID:"+uid,"DTSTAMP:"+stamp]
    if typ=="date":
        lines+=["DTSTART;VALUE=DATE:"+ds,"DTEND;VALUE=DATE:"+de]
    else:
        lines+=["DTSTART:"+ds,"DTEND:"+de]
    lines.append("SUMMARY:"+escape_ics(summary))
    if location: lines.append("LOCATION:"+escape_ics(location))
    desc="Cascade Boys Basketball. Check cascadecougarsbasketball.com for current details and updates."
    if k=="tentative": desc="Tentative gym-sharing slot. Check cascadecougarsbasketball.com for current details and updates."
    if k=="break": desc="Boys basketball Christmas break. No practice Dec. 23–27. Return Dec. 28."
    lines+=["DESCRIPTION:"+escape_ics(desc),"STATUS:"+("TENTATIVE" if k=="tentative" else "CONFIRMED"),"SEQUENCE:0","END:VEVENT"]
lines.append("END:VCALENDAR")
with open("calendar.ics","w",encoding="utf-8",newline="") as f:
    f.write("\r\n".join(lines)+"\r\n")

print(f"Synced {len(web)} website calendar entries from Google Calendar.")
