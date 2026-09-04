import os

from decouple import config

env = config("DJANGO_ENV", default="development")

if env == "production":
    from .production import *  # noqa: F401, F403
else:
    from .development import *  # noqa: F401, F403
