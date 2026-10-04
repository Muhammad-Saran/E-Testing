"""
Question generation pipeline (scope doc, Module 3).

1. Split the source text into sentences.
2. Pick an answer span in each sentence — T5 "extract answers", with a
   heuristic fallback (numbers, proper nouns, key terms).
3. Turn (sentence, answer) into a question:
   * short answer — T5 writes a question for the highlighted answer;
   * MCQ          — the same question, plus distractors drawn from the other
                    answer spans in the text (same kind: numbers with numbers);
   * true/false   — the sentence as a statement, or the sentence with its
                    answer swapped for a distractor (a false statement).
4. Return candidate questions in the question-bank payload format, so the
   instructor can edit them and commit them through QuestionSerializer.

Without the T5 model the same pipeline runs with the heuristic answer picker
and fill-in-the-blank questions (engine "rule").
"""
import random
import re

from src.services.questionbank.bloom import suggest_level
from . import engine

SENTENCE_SPLIT = re.compile(r'(?<=[.!?])\s+(?=["“(\[]?[A-Z0-9])')
NUMBER = re.compile(r'\b\d[\d,]*(?:\.\d+)?%?')
PROPER = re.compile(r'\b[A-Z][\w\-]*(?:\s+(?:of|the|de|van|von|and|for)?\s*[A-Z][\w\-]*)*')


def _drop_headings(text):
    """
    Remove title lines ("Lecture 3: Stacks and Queues") so they do not merge
    into the next sentence. A heading is a short line with no closing
    punctuation that starts a block (first line, or after a finished
    sentence / blank line) and is followed by a capitalised line. Lines that
    a PDF wrapped mid-sentence do not match, because the line before them
    has not finished its sentence.
    """
    lines = (text or '').splitlines()
    kept = []
    for i, raw in enumerate(lines):
        line = raw.strip()
        prev = lines[i - 1].strip() if i else ''
        following = lines[i + 1].strip() if i + 1 < len(lines) else ''
        nxt = next((l.strip() for l in lines[i + 1:] if l.strip()), '')
        words = line.split()
        if line and len(words) <= 10 and line[-1:] not in '.!?,;' and nxt[:1].isupper() \
                and (not prev or prev[-1:] in '.!?:') and (not following or _title_like(line, words)):
            continue
        kept.append(line)
    return '\n'.join(kept)


SMALL_WORDS = {'a', 'an', 'and', 'the', 'of', 'in', 'on', 'to', 'for', 'with', 'vs', 'or', 'at', 'by'}
HEADING_START = re.compile(r'^(lecture|chapter|unit|section|topic|week|part|module|lesson)\b|^\d+(\.\d+)*[.)]?\s', re.I)


def _title_like(line, words):
    if ':' in line or HEADING_START.match(line):
        return True
    content = [w for w in words if w.lower() not in SMALL_WORDS]
    return bool(content) and sum(1 for w in content if w[:1].isupper() or w[:1].isdigit()) / len(content) >= 0.7


def split_sentences(text):
    text = re.sub(r'\s+', ' ', _drop_headings(text)).strip()
    sentences = []
    for s in SENTENCE_SPLIT.split(text):
        s = s.strip(' -•*')
        words = s.split()
        if 6 <= len(words) <= 60 and s[-1:] in '.!?':
            sentences.append(s)
    return sentences


def heuristic_answers(sentence):
    """Candidate answer spans in a sentence, best first."""
    found = []
    found += [m.group().rstrip(',') for m in NUMBER.finditer(sentence)]
    for m in PROPER.finditer(sentence):
        phrase = m.group().strip()
        # Skip the capitalised first word of the sentence unless it is a longer name.
        if m.start() == 0 and ' ' not in phrase:
            continue
        if phrase.lower() not in engine.STOPWORDS and len(phrase) > 2:
            found.append(phrase)
    words = [w.strip('.,;:()"\'') for w in sentence.split()]
    terms = sorted({w for w in words if len(w) >= 6 and w.lower() not in engine.STOPWORDS and w.isalpha()},
                   key=len, reverse=True)
    found += terms[:3]
    seen, ordered = set(), []
    for a in found:
        if a and a.lower() not in seen and a.lower() != sentence.lower():
            seen.add(a.lower())
            ordered.append(a)
    return ordered


def _window(sentences, i, highlight):
    """Sentence i with `highlight` applied, plus one sentence of context each side."""
    parts = sentences[max(0, i - 1):i] + [highlight] + sentences[i + 1:i + 2]
    return ' '.join(parts)


def _valid_answer(answer, sentence):
    words = answer.split()
    return (answer and 1 <= len(words) <= 8 and answer.lower() in sentence.lower()
            and answer.lower() != sentence.lower().rstrip('.!?'))


def _highlight(sentence, answer):
    idx = sentence.lower().find(answer.lower())
    return sentence[:idx] + '<hl> ' + sentence[idx:idx + len(answer)] + ' <hl>' + sentence[idx + len(answer):]


def _blank(sentence, answer):
    idx = sentence.lower().find(answer.lower())
    return sentence[:idx] + '_____' + sentence[idx + len(answer):]


ARTICLE = re.compile(r'^(?:the|a|an)\s+', re.I)


def _strip_article(text):
    return ARTICLE.sub('', text).strip()


def _kind(text):
    """Rough answer category so options look alike: number, proper noun, or term."""
    if NUMBER.fullmatch(text):
        return 'number'
    return 'proper' if text[:1].isupper() else 'term'


def _same_kind(a, b):
    return _kind(_strip_article(a)) == _kind(_strip_article(b))


def _numeric_distractors(answer, rng, n):
    raw = answer.replace(',', '').rstrip('%')
    try:
        value = float(raw)
    except ValueError:
        return []
    is_int = '.' not in raw
    suffix = '%' if answer.endswith('%') else ''
    # Years stay plausible years; other numbers move by a proportion.
    if is_int and 1000 <= value <= 2100:
        deltas = [-10, -5, -2, -1, 1, 2, 5, 10]
    else:
        step = max(1, abs(value) * 0.25)
        deltas = [-2 * step, -step, step, 2 * step, 3 * step]
    rng.shuffle(deltas)
    out = []
    for d in deltas:
        v = value + d
        if v < 0 or v == value:
            continue
        text = (f'{int(round(v)):,}' if ',' in answer else str(int(round(v)))) if is_int else f'{v:.2f}'
        text += suffix
        if text not in out and text != answer:
            out.append(text)
        if len(out) == n:
            break
    return out


def pick_distractors(answer, pool, rng, n=3):
    """Wrong options for `answer`: other answers of the same kind, closest in length first."""
    answer = _strip_article(answer)
    a = answer.lower()
    pool = sorted({_strip_article(p) for p in pool})  # sorted: reproducible with a seed
    choices = [p for p in pool
               if p and p.lower() != a and a not in p.lower() and p.lower() not in a and _same_kind(p, answer)]
    rng.shuffle(choices)
    choices.sort(key=lambda p: abs(len(p.split()) - len(answer.split())))
    out = []
    for c in choices:
        if c.lower() not in {o.lower() for o in out}:
            out.append(c)
        if len(out) == n:
            break
    if len(out) < n and NUMBER.fullmatch(answer):
        out += [d for d in _numeric_distractors(answer, rng, n) if d not in out][:n - len(out)]
    return out


def _clean_question(text):
    text = text.replace('<hl>', '').replace('<sep>', '').strip()
    text = re.sub(r'^(question:|q:)\s*', '', text, flags=re.I)
    if text and not text.endswith('?'):
        text = text.rstrip('.') + '?'
    return text[:1].upper() + text[1:] if text else text


def _extract_items(sentences, use_t5, limit, model_name=None):
    """[(sentence_index, answer)] — one answer per sentence, up to `limit`."""
    items = []
    if use_t5:
        prompts = ['extract answers: ' + _window(sentences, i, f'<hl> {s} <hl>') + ' </s>'
                   for i, s in enumerate(sentences[:limit])]
        for i, out in enumerate(engine.t5_generate(prompts, max_length=48, name=model_name)):
            answers = [a.strip(' .') for a in out.split('<sep>') if a.strip(' .')]
            answer = next((a for a in answers if _valid_answer(a, sentences[i])), None)
            if answer:
                items.append((i, answer))
    covered = {i for i, _ in items}
    for i, s in enumerate(sentences[:limit]):
        if i in covered:
            continue
        answer = next((a for a in heuristic_answers(s) if _valid_answer(a, s)), None)
        if answer:
            items.append((i, answer))
    items.sort()
    return items


def generate_questions(text, question_type='mixed', count=5, difficulty='auto', subject='', seed=None,
                       model_name=None):
    """
    Generate up to `count` candidate questions from `text` with the T5 model
    `model_name` (default: settings.AI_QG_MODEL). difficulty='auto' lets the
    Bloom classifier label each question from its wording.
    Returns (candidates, engine_name).
    """
    rng = random.Random(seed)
    sentences = split_sentences(text)
    if not sentences:
        return [], 'rule'

    use_t5 = engine.get_qg_model(model_name) is not None
    # Look at more sentences than needed: some will not yield a usable question.
    items = _extract_items(sentences, use_t5, limit=max(count * 3, 12), model_name=model_name)
    if not items:
        return [], 't5' if use_t5 else 'rule'

    pool = [a for _, a in items]
    for s in sentences:
        pool += heuristic_answers(s)[:2]

    # Spread the questions across the whole text, not just its first paragraph.
    if len(items) > count * 2:
        step = len(items) / (count * 2)
        items = [items[int(k * step)] for k in range(count * 2)]

    types = (['mcq', 'short_answer', 'true_false'] if question_type == 'mixed' else [question_type])

    questions_text = {}
    if use_t5:
        prompts = ['generate question: ' + _window(sentences, i, _highlight(sentences[i], a)) + ' </s>'
                   for i, a in items]
        for (i, a), out in zip(items, engine.t5_generate(prompts, max_length=64, name=model_name)):
            q = _clean_question(out)
            if len(q.split()) >= 3 and a.lower() not in q.lower():
                questions_text[(i, a)] = q

    def build(qtype, sentence, answer, question):
        base = {
            'question_type': qtype, 'difficulty': difficulty, 'subject': subject, 'marks': 1,
            'source_sentence': sentence, 'answer': answer,
        }
        if qtype == 'mcq':
            distractors = pick_distractors(answer, pool, rng)
            if len(distractors) < 2:
                return None  # not enough plausible wrong options
            options = ([{'text': _strip_article(answer), 'is_correct': True}]
                       + [{'text': d, 'is_correct': False} for d in distractors])
            rng.shuffle(options)
            return {**base, 'text': question, 'options': options, 'correct_answer_text': ''}
        if qtype == 'true_false':
            distractor = next(iter(pick_distractors(answer, pool, rng, n=1)), None)
            make_false = distractor is not None and rng.random() < 0.5
            statement = sentence
            if make_false:
                idx = sentence.lower().find(answer.lower())
                statement = sentence[:idx] + distractor + sentence[idx + len(answer):]
            truth = 'false' if make_false else 'true'
            return {
                **base, 'text': f'True or False: {statement}', 'correct_answer_text': truth,
                'options': [{'text': 'True', 'is_correct': truth == 'true'},
                            {'text': 'False', 'is_correct': truth == 'false'}],
            }
        return {**base, 'text': question, 'options': [], 'correct_answer_text': _strip_article(answer)}

    candidates, seen = [], set()
    for i, answer in items:
        if len(candidates) >= count:
            break
        sentence = sentences[i]
        question = questions_text.get((i, answer)) or f'Fill in the blank: {_blank(sentence, answer)}'
        qtype = types[len(candidates) % len(types)]
        item = build(qtype, sentence, answer, question)
        if item is None and question_type == 'mixed':
            item = build('short_answer', sentence, answer, question)
        if item is None or item['text'].lower() in seen:
            continue
        seen.add(item['text'].lower())
        if difficulty == 'auto':
            item['difficulty'] = suggest_level(item['text'])[0]
        candidates.append(item)

    return candidates, 't5' if use_t5 else 'rule'
