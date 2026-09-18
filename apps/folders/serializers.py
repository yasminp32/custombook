from rest_framework import serializers

from apps.files.models import StoredFile
from apps.folders.models import Folder
from apps.organizations.models import Organization


def files_label(count):
    count = int(count or 0)
    if count == 1:
        return "1 file"
    return f"{count} files"


class FolderSerializer(serializers.ModelSerializer):
    folder_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    created_by = serializers.UUIDField(source="created_by_id", read_only=True, allow_null=True)
    file_count = serializers.SerializerMethodField()
    files_label = serializers.SerializerMethodField()

    class Meta:
        model = Folder
        fields = (
            "folder_id",
            "organization_id",
            "name",
            "file_count",
            "files_label",
            "created_by",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_file_count(self, obj):
        counts = self.context.get("file_counts")
        if counts is not None:
            key = (str(obj.organization_id), (obj.name or "").strip().lower())
            return counts.get(key, 0)
        if not obj.organization_id:
            return 0
        return StoredFile.objects.filter(
            organization_id=obj.organization_id,
            folder__iexact=obj.name,
        ).count()

    def get_files_label(self, obj):
        return files_label(self.get_file_count(obj))


class FolderWriteSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    name = serializers.CharField()

    class Meta:
        model = Folder
        fields = (
            "organization_id",
            "name",
        )

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("Folder name is required.")
        if len(name) > 100:
            raise serializers.ValidationError("Folder name is too long.")
        return name

    def validate_organization_id(self, value):
        if value and not Organization.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Organization not found.")
        return value

    def create(self, validated_data):
        validated_data.pop("organization_id", None)
        organization = validated_data.pop("organization", None)
        created_by = validated_data.pop("created_by", None)
        name = validated_data["name"]
        if Folder.objects.filter(organization=organization, name__iexact=name).exists():
            raise serializers.ValidationError(
                {"name": "A folder with this name already exists."}
            )
        return Folder.objects.create(
            organization=organization,
            created_by=created_by,
            name=name,
        )

    def update(self, instance, validated_data):
        validated_data.pop("organization_id", None)
        validated_data.pop("organization", None)
        name = validated_data.get("name")
        if name and Folder.objects.filter(
            organization=instance.organization,
            name__iexact=name,
        ).exclude(pk=instance.pk).exists():
            raise serializers.ValidationError(
                {"name": "A folder with this name already exists."}
            )
        old_name = instance.name
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if name and name != old_name and instance.organization_id:
            StoredFile.objects.filter(
                organization_id=instance.organization_id,
                folder__iexact=old_name,
            ).update(folder=name)
        return instance
