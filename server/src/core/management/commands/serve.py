from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Run the app with Waitress, a production WSGI server that works on Windows and Linux. '
            'Unlike `runserver` it is multi-threaded and safe to expose on a network.')

    def add_arguments(self, parser):
        parser.add_argument('--host', default='0.0.0.0')
        parser.add_argument('--port', type=int, default=8000)
        parser.add_argument('--threads', type=int, default=16)
        parser.add_argument('--no-collectstatic', action='store_true')

    def handle(self, *args, **options):
        try:
            from waitress import serve
        except ImportError:
            raise CommandError('Install waitress first: python -m pip install waitress')
        if settings.DEBUG:
            self.stdout.write(self.style.WARNING('DEBUG is on. Set DEBUG=False in server/.env for production.'))
        if not options['no_collectstatic']:
            call_command('collectstatic', interactive=False, verbosity=0)
        from config.wsgi import application
        self.stdout.write(self.style.SUCCESS(
            f"Serving e-Testing on http://{options['host']}:{options['port']} with {options['threads']} threads"))
        serve(application, host=options['host'], port=options['port'], threads=options['threads'])
