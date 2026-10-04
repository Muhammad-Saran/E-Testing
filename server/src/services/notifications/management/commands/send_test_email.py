from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Send a test email to check the SMTP settings in server/.env (e.g. Gmail with an app password).'

    def add_arguments(self, parser):
        parser.add_argument('to', help='Recipient email address')

    def handle(self, *args, **options):
        backend = settings.EMAIL_BACKEND.rsplit('.', 1)[-1]
        self.stdout.write(f'Backend: {settings.EMAIL_BACKEND}')
        if 'smtp' in settings.EMAIL_BACKEND:
            self.stdout.write(f'SMTP: {settings.EMAIL_HOST}:{settings.EMAIL_PORT} as {settings.EMAIL_HOST_USER or "-"} '
                              f'(TLS={settings.EMAIL_USE_TLS})')
        try:
            send_mail('e-Testing test email',
                      'This is a test email from the e-Testing Service. If you can read it, email works.',
                      settings.DEFAULT_FROM_EMAIL, [options['to']], fail_silently=False)
        except Exception as exc:
            raise CommandError(f'Sending failed: {exc}')
        where = 'printed above' if backend.startswith('console') else f'sent to {options["to"]}'
        self.stdout.write(self.style.SUCCESS(f'Test email {where}.'))
