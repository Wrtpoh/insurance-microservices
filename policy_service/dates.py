import calendar
from datetime import date, timedelta


def add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def policy_end(start: date, term_months: int) -> date:
    """Договор действует включительно по день, предшествующий дате окончания срока."""
    return add_months(start, term_months) - timedelta(days=1)
