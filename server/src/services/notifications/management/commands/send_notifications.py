from django.core.management.base import BaseCommand

from src.services.notifications.services import dispatch_scheduled


class Command(BaseCommand):
    help = ('Send due exam reminders and results-ready notifications. '
            'Schedule it every few minutes (cron / Windows Task Scheduler); the web app '
            'also triggers it while users are online.')

    def handle(self, *args, **options):
        counts = dispatch_scheduled()
        self.stdout.write(self.style.SUCCESS(
            f"Sent {counts['reminders']} reminder(s); {counts['results_ready']} exam(s) marked results-ready."
        ))
