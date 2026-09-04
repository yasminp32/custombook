from django.core.management.base import BaseCommand

from apps.accounts.services import cleanup_otps


class Command(BaseCommand):
    help = "Delete expired and used OTP records from the database."

    def handle(self, *args, **options):
        deleted_count, _ = cleanup_otps()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {deleted_count} expired/used OTP records.")
        )

    def add_arguments(self, parser):
        parser.epilog = (
            "Schedule this command to run periodically.\n\n"
            "Linux/macOS cron (every hour):\n"
            "  0 * * * * cd /path/to/project && .venv/bin/python manage.py cleanup_otps\n\n"
            "Windows Task Scheduler:\n"
            "  Program: C:\\path\\to\\project\\.venv\\Scripts\\python.exe\n"
            "  Arguments: manage.py cleanup_otps\n"
            "  Start in: C:\\path\\to\\project"
        )
