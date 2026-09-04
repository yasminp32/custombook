from calendar import monthrange
from datetime import date

PERIOD_CHOICES = (
    "this_fiscal_year",
    "this_year",
    "this_month",
    "last_month",
    "last_fiscal_year",
)

PERIOD_LABELS = {
    "this_fiscal_year": "This Fiscal Year",
    "this_year": "This Year",
    "this_month": "This Month",
    "last_month": "Last Month",
    "last_fiscal_year": "Last Fiscal Year",
}


def fiscal_year_start_month(country_code):
    if (country_code or "").upper() == "IN":
        return 4
    return 1


def fiscal_year_bounds(today, start_month):
    if today.month >= start_month:
        start_year = today.year
    else:
        start_year = today.year - 1
    start = date(start_year, start_month, 1)
    end_year = start_year + 1 if start_month > 1 else start_year
    end_month = start_month - 1 if start_month > 1 else 12
    end = date(end_year, end_month, monthrange(end_year, end_month)[1])
    return start, end


def get_period_range(period, country_code="IN", today=None):
    today = today or date.today()
    period = (period or "this_fiscal_year").strip().lower()
    if period not in PERIOD_CHOICES:
        period = "this_fiscal_year"

    start_month = fiscal_year_start_month(country_code)
    label = PERIOD_LABELS[period]

    if period == "this_month":
        start = today.replace(day=1)
        end = date(today.year, today.month, monthrange(today.year, today.month)[1])
    elif period == "last_month":
        if today.month == 1:
            start = date(today.year - 1, 12, 1)
        else:
            start = date(today.year, today.month - 1, 1)
        end = date(start.year, start.month, monthrange(start.year, start.month)[1])
    elif period == "this_year":
        start = date(today.year, 1, 1)
        end = date(today.year, 12, 31)
    elif period == "last_fiscal_year":
        current_start, _ = fiscal_year_bounds(today, start_month)
        previous_today = date(current_start.year - 1, current_start.month, 1)
        start, end = fiscal_year_bounds(previous_today, start_month)
    else:
        start, end = fiscal_year_bounds(today, start_month)

    return period, label, start, end


def month_points_for_year(year):
    return month_points_for_range(date(year, 1, 1), date(year, 12, 31))


def month_points_for_range(start, end):
    points = []
    year, month = start.year, start.month
    last = date(end.year, end.month, 1)
    while date(year, month, 1) <= last:
        month_start = date(year, month, 1)
        month_end = date(year, month, monthrange(year, month)[1])
        points.append(
            {
                "month": month,
                "month_label": month_start.strftime("%b"),
                "year": year,
                "start": month_start,
                "end": month_end,
            }
        )
        if month == 12:
            year += 1
            month = 1
        else:
            month += 1
    return points
