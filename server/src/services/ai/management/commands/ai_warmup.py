from django.conf import settings
from django.core.management.base import BaseCommand

from src.services.ai import engine


class Command(BaseCommand):
    help = ('Download (first run) and load the T5 question-generation and Sentence-T5 grading '
            'models, so the first generation request or exam submission is not slow.')

    def add_arguments(self, parser):
        parser.add_argument('--better', action='store_true',
                            help=f'Also load the larger "better quality" model ({settings.AI_QG_MODEL_BETTER}).')

    def handle(self, *args, **options):
        models = [('Question generation, fast (T5-small)', settings.AI_QG_MODEL)]
        if options['better']:
            models.append(('Question generation, better (T5-base)', settings.AI_QG_MODEL_BETTER))
        results = []
        for label, name in models:
            self.stdout.write(f'Loading {name}...')
            results.append((label, engine.get_qg_model(name)))
        self.stdout.write('Loading answer-similarity model...')
        results.append(('Short-answer grading (Sentence-T5)', engine.get_similarity_model()))
        for label, ok in results:
            style = self.style.SUCCESS if ok else self.style.WARNING
            self.stdout.write(style(f'{label}: {"ready" if ok else "unavailable - rule-based fallback in use"}'))
