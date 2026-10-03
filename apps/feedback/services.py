from apps.feedback.constants import CATEGORIES, DEFAULT_CATEGORY, MAX_STARS
from apps.organizations.services import get_current_organization


def form_payload():
    return {
        "title": "Feedback",
        "rating": {
            "label": "How would you rate your experience?",
            "max_stars": MAX_STARS,
            "value": None,
        },
        "category": {
            "label": "Category",
            "value": DEFAULT_CATEGORY,
            "options": [
                {"category": code, "label": label, "is_selected": code == DEFAULT_CATEGORY}
                for code, label in CATEGORIES
            ],
        },
        "subject": {
            "label": "Subject",
            "placeholder": "Brief summary",
            "required": True,
        },
        "message": {
            "label": "Your Feedback",
            "placeholder": "Tell us what you think...",
            "required": True,
        },
        "submit_label": "Submit Feedback",
    }


def feedback_payload(feedback):
    return {
        "feedback_id": str(feedback.id),
        "rating": feedback.rating,
        "max_stars": MAX_STARS,
        "category": feedback.category,
        "category_label": feedback.get_category_display(),
        "subject": feedback.subject,
        "message": feedback.message,
        "organization_id": str(feedback.organization_id) if feedback.organization_id else None,
        "created_at": feedback.created_at,
    }


def current_organization(user):
    return get_current_organization(user)
