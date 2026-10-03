from apps.image_upload.constants import DEFAULT_RESOLUTION, NOTE, RESOLUTIONS
from apps.image_upload.models import ImageUploadResolution


def get_resolution(user):
    preference, _created = ImageUploadResolution.objects.get_or_create(
        user=user,
        defaults={"resolution": DEFAULT_RESOLUTION},
    )
    return preference


def resolution_payload(preference):
    selected = preference.resolution
    return {
        "title": "Image Upload Resolution",
        "description": "Choose the resolution for images uploaded with receipts, expenses, and documents.",
        "resolution": selected,
        "note": NOTE,
        "options": [
            {
                "resolution": row["resolution"],
                "label": row["label"],
                "pixels": row["pixels"],
                "description": row["description"],
                "is_recommended": row["is_recommended"],
                "is_selected": row["resolution"] == selected,
            }
            for row in RESOLUTIONS
        ],
    }
