from apps.quotes.models import QuoteActivity


def log_activity(
    quote,
    message,
    user=None,
    activity_type=QuoteActivity.ActivityType.HISTORY,
):
    return QuoteActivity.objects.create(
        quote=quote,
        activity_type=activity_type,
        message=message,
        created_by=user,
    )


def display_name_for_user(user):
    if not user:
        return ""
    full_name = (user.get_full_name() or "").strip()
    if full_name:
        return full_name
    first = (getattr(user, "first_name", "") or "").strip()
    last = (getattr(user, "last_name", "") or "").strip()
    combined = f"{first} {last}".strip()
    if combined:
        return combined
    return user.email or ""
