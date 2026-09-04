from calendar import monthrange
from datetime import date, timedelta

DATE_RANGES = (
    "last_30_days",
    "last_60_days",
    "last_90_days",
    "this_month",
    "last_month",
    "this_quarter",
    "this_year",
)

DATE_RANGE_LABELS = {
    "last_30_days": "Last 30 days",
    "last_60_days": "Last 60 days",
    "last_90_days": "Last 90 days",
    "this_month": "This Month",
    "last_month": "Last Month",
    "this_quarter": "This Quarter",
    "this_year": "This Year",
}


def get_date_range(range_key, today=None):
    today = today or date.today()
    range_key = (range_key or "last_30_days").strip().lower()
    if range_key not in DATE_RANGES:
        range_key = "last_30_days"

    if range_key == "last_60_days":
        start = today - timedelta(days=59)
        end = today
    elif range_key == "last_90_days":
        start = today - timedelta(days=89)
        end = today
    elif range_key == "this_month":
        start = today.replace(day=1)
        end = today
    elif range_key == "last_month":
        if today.month == 1:
            start = date(today.year - 1, 12, 1)
        else:
            start = date(today.year, today.month - 1, 1)
        end = date(start.year, start.month, monthrange(start.year, start.month)[1])
    elif range_key == "this_quarter":
        quarter = ((today.month - 1) // 3) + 1
        start_month = 3 * (quarter - 1) + 1
        start = date(today.year, start_month, 1)
        end = today
    elif range_key == "this_year":
        start = date(today.year, 1, 1)
        end = today
    else:
        start = today - timedelta(days=29)
        end = today

    return range_key, DATE_RANGE_LABELS[range_key], start, end


def each_date(start, end):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)
