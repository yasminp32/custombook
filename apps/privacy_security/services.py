from django.utils import timezone

from apps.privacy_security.constants import (
    AUTO_LOCK_LABELS,
    AUTO_LOCK_OPTIONS,
    COMPANY_NAME,
    CONTACT_EMAIL,
    CONTACT_PHONE,
    LAST_UPDATED,
    PRIVACY_SECTIONS,
    TERMS_SECTIONS,
)
from apps.privacy_security.models import PrivacySecurity


def get_privacy_security(user):
    preference, _created = PrivacySecurity.objects.get_or_create(user=user)
    return preference


def document_payload(title, sections):
    return {
        "title": title,
        "last_updated": LAST_UPDATED,
        "sections": [
            {"number": index, "title": heading, "body": body}
            for index, (heading, body) in enumerate(sections, start=1)
        ],
        "contact": {
            "email": CONTACT_EMAIL,
            "phone": CONTACT_PHONE,
            "company": COMPANY_NAME,
        },
    }


def screen_payload(preference):
    app_lock_items = [
        {
            "key": "enable_app_lock",
            "label": "Enable App Lock",
            "description": "Require authentication to open the app",
            "type": "toggle",
            "icon": "lock",
            "enabled": preference.enable_app_lock,
        }
    ]
    if preference.enable_app_lock:
        app_lock_items.extend(
            [
                {
                    "key": "biometric_unlock",
                    "label": "Biometric Unlock",
                    "description": "Use fingerprint or face to unlock",
                    "type": "toggle",
                    "icon": "fingerprint",
                    "enabled": preference.biometric_unlock,
                },
                {
                    "key": "lock_on_app_exit",
                    "label": "Lock on App Exit",
                    "description": "Automatically lock when you leave the app",
                    "type": "toggle",
                    "icon": "exit",
                    "enabled": preference.lock_on_app_exit,
                },
                {
                    "key": "auto_lock_after",
                    "label": "Auto-Lock After",
                    "type": "select",
                    "icon": "timer",
                    "value": preference.auto_lock_after,
                    "value_label": AUTO_LOCK_LABELS[preference.auto_lock_after],
                    "options": [
                        {"value": value, "label": label, "is_selected": value == preference.auto_lock_after}
                        for value, label in AUTO_LOCK_OPTIONS
                    ],
                },
            ]
        )
    return {
        "title": "Privacy & Security",
        "enable_app_lock": preference.enable_app_lock,
        "biometric_unlock": preference.biometric_unlock,
        "lock_on_app_exit": preference.lock_on_app_exit,
        "auto_lock_after": preference.auto_lock_after,
        "auto_lock_after_label": AUTO_LOCK_LABELS[preference.auto_lock_after],
        "hide_amounts_on_dashboard": preference.hide_amounts_on_dashboard,
        "sections": [
            {"section": "app_lock", "label": "APP LOCK", "items": app_lock_items},
            {
                "section": "data_privacy",
                "label": "DATA PRIVACY",
                "items": [
                    {
                        "key": "hide_amounts_on_dashboard",
                        "label": "Hide Amounts on Dashboard",
                        "description": "Mask financial figures until you tap to reveal",
                        "type": "toggle",
                        "icon": "eye_off",
                        "enabled": preference.hide_amounts_on_dashboard,
                    }
                ],
            },
            {
                "section": "data_storage",
                "label": "DATA & STORAGE",
                "items": [
                    {
                        "key": "clear_cache",
                        "label": "Clear Cache",
                        "description": "Free up space by clearing temporary files",
                        "type": "action",
                        "icon": "cache",
                    },
                    {
                        "key": "privacy_policy",
                        "label": "Privacy Policy",
                        "description": "Read our privacy policy",
                        "type": "link",
                        "icon": "shield",
                    },
                    {
                        "key": "terms",
                        "label": "Terms of Service",
                        "description": "Read our terms of service",
                        "type": "link",
                        "icon": "document",
                    },
                ],
            },
        ],
    }


def clear_cache(preference):
    preference.cache_cleared_at = timezone.now()
    preference.save(update_fields=["cache_cleared_at", "updated_at"])
    return preference
