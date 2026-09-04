import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import default_storage


def save_uploaded_file(uploaded_file, organization_id, attachment_id):
    safe_name = Path(uploaded_file.name).name
    storage_key = f"attachments/{organization_id}/{attachment_id}/{safe_name}"

    if default_storage.exists(storage_key):
        default_storage.delete(storage_key)

    saved_path = default_storage.save(storage_key, uploaded_file)
    return saved_path


def delete_stored_file(storage_key):
    if storage_key and default_storage.exists(storage_key):
        default_storage.delete(storage_key)
