from rest_framework import serializers

from apps.projects.models import Project
from apps.timer.models import TimerSession


class TimerSerializer(serializers.ModelSerializer):
    timer_id = serializers.UUIDField(source="id", read_only=True)
    organization_id = serializers.UUIDField(read_only=True, allow_null=True)
    user_id = serializers.UUIDField(read_only=True, allow_null=True)
    project_id = serializers.UUIDField(read_only=True, allow_null=True)
    project_name = serializers.SerializerMethodField()
    status_label = serializers.CharField(source="get_status_display", read_only=True)
    elapsed_seconds = serializers.SerializerMethodField()
    elapsed_display = serializers.SerializerMethodField()
    hours = serializers.SerializerMethodField()
    minutes = serializers.SerializerMethodField()
    can_start = serializers.SerializerMethodField()
    can_stop = serializers.SerializerMethodField()

    class Meta:
        model = TimerSession
        fields = (
            "timer_id",
            "organization_id",
            "user_id",
            "project_id",
            "project_name",
            "task_name",
            "notes",
            "status",
            "status_label",
            "started_at",
            "elapsed_seconds",
            "elapsed_display",
            "hours",
            "minutes",
            "can_start",
            "can_stop",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_project_name(self, obj):
        return obj.project.name if obj.project else ""

    def get_elapsed_seconds(self, obj):
        return obj.elapsed_seconds()

    def get_elapsed_display(self, obj):
        return obj.elapsed_display()

    def get_hours(self, obj):
        hours, _minutes = obj.to_hours_minutes()
        return hours

    def get_minutes(self, obj):
        _hours, minutes = obj.to_hours_minutes()
        return minutes

    def get_can_start(self, obj):
        return obj.status != TimerSession.Status.RUNNING

    def get_can_stop(self, obj):
        return obj.elapsed_seconds() > 0 or obj.status == TimerSession.Status.RUNNING


class TimerWriteSerializer(serializers.Serializer):
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    project_id = serializers.UUIDField(required=False, allow_null=True)
    task_name = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_task_name(self, value):
        return (value or "").strip()

    def validate_notes(self, value):
        return (value or "").strip()

    def validate_project_id(self, value):
        if value and not Project.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Project not found.")
        return value
