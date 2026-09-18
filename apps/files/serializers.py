from rest_framework import serializers

from apps.files.models import StoredFile
from apps.organizations.models import Organization


def format_file_size(size_bytes):
    size = int(size_bytes or 0)
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    if size >= 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size} B"


class StoredFileSerializer(serializers.ModelSerializer):
    file_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    type = serializers.CharField(source="file_type", read_only=True)
    type_label = serializers.CharField(source="get_file_type_display", read_only=True)
    size_bytes = serializers.IntegerField(source="file_size", read_only=True)
    size_label = serializers.SerializerMethodField()
    folder_label = serializers.SerializerMethodField()
    uploaded_at = serializers.DateTimeField(source="created_at", read_only=True)
    uploaded_label = serializers.SerializerMethodField()
    preview_available = serializers.SerializerMethodField()
    preview_message = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = StoredFile
        fields = (
            "file_id",
            "organization_id",
            "name",
            "type",
            "type_label",
            "mime_type",
            "size_bytes",
            "size_label",
            "folder",
            "folder_label",
            "uploaded_at",
            "uploaded_label",
            "preview_available",
            "preview_message",
            "file_url",
            "share_token",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_size_label(self, obj):
        return format_file_size(obj.file_size)

    def get_folder_label(self, obj):
        return obj.folder or "All documents"

    def get_uploaded_label(self, obj):
        if not obj.created_at:
            return ""
        return obj.created_at.strftime("%d %b %Y")

    def get_preview_available(self, obj):
        return False

    def get_preview_message(self, obj):
        return "Preview will be available once connected."

    def get_file_url(self, obj):
        path = f"/api/files/download/?file_id={obj.id}"
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(path)
        return path


class StoredFileWriteSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField(required=False, allow_blank=True)
    folder = serializers.CharField(required=False, allow_blank=True)

    def validate_name(self, value):
        return (value or "").strip()

    def validate_folder(self, value):
        return (value or "").strip() or "All documents"

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value
