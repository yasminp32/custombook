from apps.opening_screen.constants import DEFAULT_SCREEN, SCREENS
from apps.opening_screen.models import OpeningScreen


def get_opening_screen(user):
    preference, _created = OpeningScreen.objects.get_or_create(user=user, defaults={"screen": DEFAULT_SCREEN})
    return preference


def screen_payload(preference):
    selected = preference.screen
    return {
        "title": "Opening Screen",
        "description": "Choose the screen that opens when you launch the app.",
        "screen": selected,
        "screens": [
            {
                "screen": code,
                "label": label,
                "icon": icon,
                "is_selected": code == selected,
            }
            for code, label, icon in SCREENS
        ],
    }
