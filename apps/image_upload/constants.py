RESOLUTIONS = (
    {
        "resolution": "low",
        "label": "Low (512px)",
        "pixels": 512,
        "description": "Smaller file size, faster uploads. Best for documents.",
        "is_recommended": False,
    },
    {
        "resolution": "medium",
        "label": "Medium (1024px)",
        "pixels": 1024,
        "description": "Good balance between quality and file size. Recommended.",
        "is_recommended": True,
    },
    {
        "resolution": "high",
        "label": "High (2048px)",
        "pixels": 2048,
        "description": "Higher quality images. Larger file sizes.",
        "is_recommended": False,
    },
    {
        "resolution": "original",
        "label": "Original",
        "pixels": None,
        "description": "No compression. Uses the full original resolution.",
        "is_recommended": False,
    },
)

RESOLUTION_CODES = {row["resolution"] for row in RESOLUTIONS}
DEFAULT_RESOLUTION = "medium"
NOTE = "Higher resolution images provide better quality but use more storage and data."
