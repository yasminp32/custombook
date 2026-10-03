from apps.about.constants import (
    APP_NAME,
    BUILD,
    COPYRIGHT,
    DESCRIPTION,
    DEVELOPER,
    FRAMEWORK,
    LAST_UPDATED,
    PLATFORM,
    SUPPORT_EMAIL,
    SUPPORT_PHONE,
    VERSION,
)


def about_payload(request):
    return {
        "title": "About",
        "app_name": APP_NAME,
        "version": VERSION,
        "build": BUILD,
        "version_label": f"Version {VERSION} (Build {BUILD})",
        "description": DESCRIPTION,
        "details": [
            {"key": "framework", "label": "Framework", "value": FRAMEWORK},
            {"key": "platform", "label": "Platform", "value": PLATFORM},
            {"key": "last_updated", "label": "Last Updated", "value": LAST_UPDATED},
            {"key": "developer", "label": "Developer", "value": DEVELOPER},
        ],
        "support": {
            "label": "SUPPORT",
            "phone": SUPPORT_PHONE,
            "email": SUPPORT_EMAIL,
        },
        "links": [
            {
                "key": "privacy_policy",
                "label": "Privacy Policy",
                "url": request.build_absolute_uri("/api/privacy-security/privacy-policy/"),
            },
            {
                "key": "terms",
                "label": "Terms of Service",
                "url": request.build_absolute_uri("/api/privacy-security/terms/"),
            },
        ],
        "copyright": COPYRIGHT,
    }
