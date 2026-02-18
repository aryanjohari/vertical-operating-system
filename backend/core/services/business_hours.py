# backend/core/services/business_hours.py
"""
Business hours and holiday check for bridge calls.
Bridging is allowed only when within configured hours and not on a holiday.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("Apex.BusinessHours")

from zoneinfo import ZoneInfo


def within_business_hours(config: Dict[str, Any], dt: Optional[datetime] = None) -> bool:
    """
    Return True if the given time (or now) is within business hours and not on a holiday.

    Config path: modules.lead_gen.sales_bridge.business_hours and .holidays
    - business_hours: { timezone, start_hour, end_hour, days_of_week?: [1..7] } 1=Mon, 7=Sun
      end_hour is exclusive (18 = up to but not including 6pm).
    - holidays: optional list of date strings "YYYY-MM-DD".

    If business_hours is missing, we allow 24/7 (return True).
    """
    sb = config.get("modules", {}).get("lead_gen", {}).get("sales_bridge", {})
    hours = sb.get("business_hours")
    if not hours:
        return True

    tz_name = hours.get("timezone") or config.get("timezone") or "Pacific/Auckland"
    start_hour = int(hours.get("start_hour", 8))
    end_hour = int(hours.get("end_hour", 18))
    days_of_week = hours.get("days_of_week")
    if isinstance(days_of_week, list) and len(days_of_week) > 0:
        days_of_week = [int(x) for x in days_of_week if isinstance(x, (int, float))]
    else:
        days_of_week = None

    if dt is None:
        dt = datetime.now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    try:
        tz = ZoneInfo(tz_name)
        local = dt.astimezone(tz)
    except Exception as e:
        logger.warning(f"Invalid timezone {tz_name}: {e}; assuming within hours")
        return True

    # Operating days: Python weekday() is Mon=0 .. Sun=6; config uses 1=Mon .. 7=Sun
    if days_of_week:
        py_weekday = local.weekday()  # 0=Mon, 6=Sun
        config_day = py_weekday + 1  # 1=Mon, 7=Sun
        if config_day not in days_of_week:
            return False

    hour = local.hour
    if start_hour <= end_hour:
        if not (start_hour <= hour < end_hour):
            return False
    else:
        # e.g. 22 - 6 (overnight)
        if not (hour >= start_hour or hour < end_hour):
            return False

    # Check holidays (date in project timezone)
    holidays = sb.get("holidays") or []
    if isinstance(holidays, list):
        date_str = local.strftime("%Y-%m-%d")
        if date_str in holidays:
            return False

    return True


def business_hours_message(config: Dict[str, Any]) -> str:
    """Return a human-readable message for 'outside business hours' error."""
    sb = config.get("modules", {}).get("lead_gen", {}).get("sales_bridge", {})
    hours = sb.get("business_hours")
    if not hours:
        return "Bridge is not allowed at this time."
    tz_name = hours.get("timezone") or config.get("timezone") or "Pacific/Auckland"
    start = hours.get("start_hour", 8)
    end = hours.get("end_hour", 18)
    return f"Bridge is only allowed between {start}:00 and {end}:00 ({tz_name})."
