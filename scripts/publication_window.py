"""Weekly publication interval; date-only boundary records need source verification."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from research_core import CONFIG, local_zone, safe_public_url


def weekly_window(cutoff_date=None, *, now=None):
    """Resolve the latest completed scheduled interval, or an explicit run date."""
    if CONFIG.get("publication_window") != "between_weekly_cutoffs":
        raise ValueError("未配置周度发表窗口")
    minute, hour, day, month, weekday = CONFIG["schedule"]["cron"].split()
    if (day, month) != ("*", "*") or not weekday.isdigit():
        raise ValueError("发表窗口需要每周固定一天运行")
    target_weekday = (int(weekday) + 6) % 7
    zone = local_zone()
    if cutoff_date:
        target = date.fromisoformat(cutoff_date)
        if target.weekday() != target_weekday:
            raise ValueError("--date 须指定原定周五的日期")
        end = datetime.combine(target, time(int(hour), int(minute)), zone)
    else:
        current = now or datetime.now(zone)
        if current.tzinfo is None:
            raise ValueError("运行时间须包含时区")
        current = current.astimezone(zone)
        target = current.date() - timedelta(days=(current.weekday() - target_weekday) % 7)
        end = datetime.combine(target, time(int(hour), int(minute)), zone)
        if end > current:
            end -= timedelta(days=7)
    start = end - timedelta(days=7)
    return {
        "start": start.date().isoformat(), "end": end.date().isoformat(),
        "start_at": start.isoformat(), "end_at": end.isoformat(),
        "timezone": str(zone), "start_exclusive": True, "end_inclusive": True,
    }


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("发表时刻须为带时区的时间文本")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("发表时刻须注明时区")
    return parsed


def publication_membership(record, window):
    """Classify real publication time, never database update/indexing time."""
    if not window.get("start_at") and not window.get("end_at"):
        return "inside"  # Historical date-only imports retain their existing checks.
    try:
        start, end = timestamp(window["start_at"]), timestamp(window["end_at"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("发表窗口须有带时区的起止时刻")
    if start >= end or window.get("start_exclusive") is not True or window.get("end_inclusive") is not True:
        raise ValueError("发表窗口须为起点之后、截止时刻及以前")
    if record.get("published_at"):
        if not safe_public_url(record.get("published_at_source", "")):
            return "needs_publication_time"
        try:
            published = timestamp(record["published_at"])
        except (TypeError, ValueError):
            return "needs_publication_time"
        return "inside" if start < published <= end else "outside"
    try:
        value = record.get("published_date", "")
        if len(value) != 10:
            return "needs_publication_time"
        published_day = date.fromisoformat(value)
    except (TypeError, ValueError):
        return "needs_publication_time"
    if published_day < start.date() or published_day > end.date():
        return "outside"
    if published_day in (start.date(), end.date()):
        return "needs_publication_time"
    return "inside"
