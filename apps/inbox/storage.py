from pathlib import Path

from django.core.files.storage import default_storage


def save_uploaded_file(uploaded_file, organization_id, document_id):
    safe_name = Path(uploaded_file.name).name
    storage_key = f"inbox/{organization_id}/{document_id}/{safe_name}"
    if default_storage.exists(storage_key):
        default_storage.delete(storage_key)
    return default_storage.save(storage_key, uploaded_file)


def delete_stored_file(storage_key):
    if storage_key and default_storage.exists(storage_key):
        default_storage.delete(storage_key)
