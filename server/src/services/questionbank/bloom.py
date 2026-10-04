"""
Bloom's Taxonomy level suggestion from a question's wording.

Bloom's revised taxonomy (Anderson & Krathwohl, 2001) is conventionally
applied by matching the action verb of an assessment item against verb
lists for each cognitive level. The highest level whose verb appears wins,
because "describe and justify" asks for evaluation, not description.
"""
import re

# Highest level first.
LEVELS = [
    ('create', ['design', 'create', 'construct', 'develop', 'formulate', 'propose', 'compose', 'invent',
                'devise', 'plan', 'build', 'generate', 'write a program', 'implement a']),
    ('evaluate', ['evaluate', 'justify', 'assess', 'critique', 'judge', 'defend', 'argue', 'recommend',
                  'which is better', 'appraise', 'prioritize', 'validate', 'is it appropriate']),
    ('analyze', ['analyze', 'analyse', 'compare', 'contrast', 'differentiate', 'distinguish', 'examine',
                 'categorize', 'classify', 'investigate', 'relationship between', 'difference between',
                 'what would happen', 'why does', 'break down', 'trace']),
    ('apply', ['apply', 'calculate', 'compute', 'solve', 'use', 'demonstrate', 'implement', 'execute',
               'illustrate', 'determine', 'find the', 'how many', 'how much', 'convert', 'show how']),
    ('understand', ['explain', 'describe', 'summarize', 'summarise', 'interpret', 'discuss', 'paraphrase',
                    'why', 'how does', 'what is the purpose', 'give an example', 'predict', 'infer',
                    'what does', 'meaning of']),
    ('remember', ['define', 'list', 'name', 'identify', 'state', 'recall', 'who', 'when', 'where',
                  'which', 'what is', 'what are', 'label', 'fill in the blank', 'recognize', 'mention']),
]


def suggest_level(text):
    """Return (level, matched cue) — falls back to ('remember', '') for plain recall."""
    lowered = ' ' + re.sub(r'\s+', ' ', (text or '').lower()) + ' '
    for level, cues in LEVELS:
        for cue in cues:
            if re.search(r'(?<![a-z])' + re.escape(cue) + r'(?![a-z])', lowered):
                return level, cue
    return 'remember', ''
