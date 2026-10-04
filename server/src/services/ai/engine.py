"""
Model access for the AI features.

* Question generation (Module 3) — a T5 model fine-tuned for answer-aware
  question generation (default `valhalla/t5-small-qa-qg-hl`). The same
  multitask model extracts answer spans ("extract answers:") and writes a
  question for a highlighted answer ("generate question:").
* Semantic short-answer grading (Module 6) — Sentence-T5
  (`sentence-transformers/sentence-t5-base`) embeds the reference and the
  student's answer; the cosine similarity decides the marks.

Models are loaded lazily, once per process, and inference runs server-side
only. If the libraries are not installed, the model cannot be downloaded, or
AI_ENGINE=rule, every caller transparently falls back to a rule-based engine.
"""
import difflib
import logging
import re
import threading

from django.conf import settings

logger = logging.getLogger('etesting.ai')

_lock = threading.Lock()
_qg = {}              # model name -> (tokenizer, model)
_qg_failed = set()    # model names that could not be loaded
_sim = None           # SentenceT5 once loaded
_sim_failed = False

STOPWORDS = set('''
a an the and or but if of in on at to for from by with as is are was were be been being this that these
those it its into than then there their them they he she his her you your we our i me my not no do does
did so such can could should would may might will shall also which who whom whose what when where why how
all any each few more most other some only own same too very just about over under again further once
'''.split())


def _wants_t5():
    return settings.AI_ENGINE in ('auto', 't5')


def libraries_available():
    if not _wants_t5():
        return False
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# T5 question generation
# ---------------------------------------------------------------------------
QUALITY_MODELS = {
    # "fast" — t5-small (60M parameters): a few seconds per batch on a CPU.
    'fast': lambda: settings.AI_QG_MODEL,
    # "better" — t5-base (220M parameters): better questions, roughly 3x slower.
    'better': lambda: settings.AI_QG_MODEL_BETTER,
}


def model_for(quality):
    return QUALITY_MODELS.get(quality, QUALITY_MODELS['fast'])()


def get_qg_model(name=None):
    """(tokenizer, model) for T5 question generation, or None if unavailable."""
    name = name or settings.AI_QG_MODEL
    if name in _qg or name in _qg_failed or not libraries_available():
        return _qg.get(name)
    with _lock:
        if name not in _qg and name not in _qg_failed:
            try:
                import torch
                from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
                tokenizer = AutoTokenizer.from_pretrained(name)
                # float32: T5 is numerically unstable in fp16.
                model = AutoModelForSeq2SeqLM.from_pretrained(name, dtype=torch.float32)
                model.eval()
                _qg[name] = (tokenizer, model)
                logger.info('Loaded question-generation model %s', name)
            except Exception:
                _qg_failed.add(name)
                logger.exception('Could not load %s — using the rule-based generator', name)
    return _qg.get(name)


def t5_generate(prompts, max_length=64, name=None):
    """Run a T5 model on a batch of text prompts and return the decoded outputs."""
    tokenizer, model = get_qg_model(name)
    import torch

    outputs = []
    for start in range(0, len(prompts), 8):
        batch = prompts[start:start + 8]
        enc = tokenizer(batch, max_length=512, truncation=True, padding=True, return_tensors='pt')
        with torch.no_grad():
            generated = model.generate(
                input_ids=enc['input_ids'], attention_mask=enc['attention_mask'],
                max_length=max_length, num_beams=4, early_stopping=True,
            )
        for ids in generated:
            text = tokenizer.decode(ids, skip_special_tokens=False)
            text = text.replace('<pad>', '').replace('</s>', '')
            outputs.append(' '.join(text.split()))
    return outputs


# ---------------------------------------------------------------------------
# Semantic similarity for short answers
# ---------------------------------------------------------------------------
class SentenceT5:
    """
    Sentence-T5 encoder: T5 encoder -> mean pooling -> dense projection ->
    L2 normalisation, the same stack the `sentence-transformers` package
    builds, implemented on plain `transformers` to keep dependencies small.
    """

    def __init__(self, name):
        import torch
        from transformers import AutoTokenizer, T5EncoderModel

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(name)
        self.model = T5EncoderModel.from_pretrained(name, dtype=torch.float32)
        self.model.eval()
        self.dense = self._load_dense(name)

    def _load_dense(self, name):
        from huggingface_hub import hf_hub_download

        for filename in ('2_Dense/model.safetensors', '2_Dense/pytorch_model.bin'):
            try:
                path = hf_hub_download(name, filename)
            except Exception:
                continue
            if filename.endswith('.safetensors'):
                from safetensors.torch import load_file
                weights = load_file(path)
            else:
                weights = self.torch.load(path, map_location='cpu', weights_only=True)
            return weights['linear.weight'].float()
        logger.warning('%s has no dense layer; using pooled encoder output', name)
        return None

    def encode(self, texts):
        enc = self.tokenizer(texts, padding=True, truncation=True, max_length=256, return_tensors='pt')
        with self.torch.no_grad():
            hidden = self.model(**enc).last_hidden_state
        mask = enc['attention_mask'].unsqueeze(-1).to(hidden.dtype)
        emb = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
        if self.dense is not None:
            emb = emb @ self.dense.T
        return self.torch.nn.functional.normalize(emb, dim=-1)

    def similarity(self, a, b):
        emb = self.encode([a, b])
        return float((emb[0] * emb[1]).sum())


def get_similarity_model():
    global _sim, _sim_failed
    if _sim is not None or _sim_failed or not libraries_available():
        return _sim
    with _lock:
        if _sim is None and not _sim_failed:
            try:
                _sim = SentenceT5(settings.AI_SIMILARITY_MODEL)
                logger.info('Loaded similarity model %s', settings.AI_SIMILARITY_MODEL)
            except Exception:
                _sim_failed = True
                logger.exception('Could not load %s — using lexical similarity', settings.AI_SIMILARITY_MODEL)
    return _sim


def normalize(text):
    return ' '.join(re.sub(r'[^\w\s]', ' ', (text or '').lower()).split())


def _stem(word):
    for suffix in ('ing', 'edly', 'ed', 'es', 's', 'ly'):
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[:-len(suffix)]
    return word


def _content_words(text):
    return {_stem(w) for w in normalize(text).split() if w not in STOPWORDS}


def lexical_similarity(reference, answer):
    """0..1 score from word overlap plus character similarity (typo tolerant)."""
    ref, ans = normalize(reference), normalize(answer)
    if not ref or not ans:
        return 0.0
    ratio = difflib.SequenceMatcher(None, ref, ans).ratio()
    ref_words, ans_words = _content_words(ref), _content_words(ans)
    if not ref_words:
        return ratio
    recall = len(ref_words & ans_words) / len(ref_words)
    precision = len(ref_words & ans_words) / len(ans_words) if ans_words else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return max(ratio, f1)


def answer_similarity(reference, answer):
    """
    Score a short answer against its reference. Returns (score 0..1, method).

    Very short references (one to three words — names, terms, numbers) are
    factual: embeddings rate "Karachi" close to "Islamabad", so these are
    matched lexically, which still forgives typos and spacing. Longer,
    descriptive references are compared semantically with Sentence-T5.
    """
    ref_norm, ans_norm = normalize(reference), normalize(answer)
    if not ans_norm:
        return 0.0, 'empty'
    if ref_norm == ans_norm:
        return 1.0, 'exact'
    # Articles carry no meaning here: "a queue" == "queue".
    ref_norm = ' '.join(w for w in ref_norm.split() if w not in ('a', 'an', 'the')) or ref_norm
    ans_norm = ' '.join(w for w in ans_norm.split() if w not in ('a', 'an', 'the')) or ans_norm
    if ref_norm == ans_norm:
        return 1.0, 'exact'
    if len(ref_norm.split()) <= 3:
        # Numbers must match exactly — "1991" is not "nearly" "1992".
        if re.findall(r'\d+', ref_norm) != re.findall(r'\d+', ans_norm):
            return 0.0, 'numeric'
        score = difflib.SequenceMatcher(None, ref_norm, ans_norm).ratio()
        ref_words, ans_words = ref_norm.split(), ans_norm.split()
        # "Islamabad city" for "Islamabad": the whole reference plus a word or two.
        if set(ref_words) <= set(ans_words) and len(ans_words) <= len(ref_words) + 2:
            score = max(score, 0.9)
        return round(score, 4), 'fuzzy'

    model = get_similarity_model()
    if model is not None:
        try:
            score = max(0.0, min(1.0, model.similarity(reference, answer)))
            # Embeddings rate vague one-liners ("It is a protocol") close to the
            # reference, so answers much shorter than it are scaled down: an
            # answer with under half the reference's content words loses up to
            # half its score.
            ref_words, ans_words = _content_words(reference), _content_words(answer)
            coverage = min(1.0, len(ans_words) / max(1.0, 0.5 * len(ref_words)))
            return round(score * (0.5 + 0.5 * coverage), 4), 'sentence-t5'
        except Exception:
            logger.exception('Semantic similarity failed — falling back to lexical')
    return round(lexical_similarity(reference, answer), 4), 'lexical'


# ---------------------------------------------------------------------------
# Required keywords for short answers
# ---------------------------------------------------------------------------
def keyword_groups(spec):
    """'last in first out|LIFO, stack' -> [['last in first out', 'lifo'], ['stack']]"""
    groups = []
    for part in (spec or '').split(','):
        alternatives = [normalize(a) for a in part.split('|') if normalize(a)]
        if alternatives:
            groups.append(alternatives)
    return groups


def _contains(answer_norm, phrase):
    """Phrase present in the answer — whole words, typo tolerant for single words."""
    if f' {phrase} ' in f' {answer_norm} ':
        return True
    words = answer_norm.split()
    if ' ' in phrase:
        return False
    stem = _stem(phrase)
    return any(_stem(w) == stem or (len(phrase) >= 5 and difflib.SequenceMatcher(None, w, phrase).ratio() >= 0.85)
               for w in words)


def missing_keywords(spec, answer):
    """The keyword groups (first alternative of each) that the answer does not contain."""
    answer_norm = normalize(answer)
    return [group[0] for group in keyword_groups(spec) if not any(_contains(answer_norm, alt) for alt in group)]


# ---------------------------------------------------------------------------
# Question similarity search (duplicate detection in the question bank)
# ---------------------------------------------------------------------------
_embedding_cache = {}   # (question id, version) -> embedding tensor


def _embed_questions(questions, model):
    import torch

    missing = [q for q in questions if (q.id, q.version) not in _embedding_cache]
    for start in range(0, len(missing), 32):
        batch = missing[start:start + 32]
        for q, emb in zip(batch, model.encode([q.text for q in batch])):
            _embedding_cache[(q.id, q.version)] = emb
    if not questions:
        return torch.empty(0)
    return torch.stack([_embedding_cache[(q.id, q.version)] for q in questions])


def similar_questions(text, questions, threshold, limit=5):
    """
    Bank questions whose wording is close to `text`, best first:
    [(question, score)]. Sentence-T5 when available, lexical otherwise.
    """
    questions = list(questions)
    if not questions or not normalize(text):
        return []
    model = get_similarity_model()
    if model is not None:
        bank = _embed_questions(questions, model)
        scores = (bank @ model.encode([text])[0]).tolist()
    else:
        scores = [lexical_similarity(text, q.text) for q in questions]
    ranked = sorted(((q, round(s, 4)) for q, s in zip(questions, scores) if s >= threshold),
                    key=lambda pair: -pair[1])
    return ranked[:limit]


def duplicate_pairs(questions, threshold, limit=50):
    """Pairs of near-identical questions within the bank: [(q1, q2, score)]."""
    questions = list(questions)[:600]
    if len(questions) < 2:
        return []
    model = get_similarity_model()
    pairs = []
    if model is not None:
        bank = _embed_questions(questions, model)
        matrix = (bank @ bank.T).tolist()
        for i in range(len(questions)):
            for j in range(i + 1, len(questions)):
                if matrix[i][j] >= threshold:
                    pairs.append((questions[i], questions[j], round(matrix[i][j], 4)))
    else:
        for i in range(len(questions)):
            for j in range(i + 1, len(questions)):
                score = lexical_similarity(questions[i].text, questions[j].text)
                if score >= threshold:
                    pairs.append((questions[i], questions[j], round(score, 4)))
    pairs.sort(key=lambda p: -p[2])
    return pairs[:limit]


def similarity_engine():
    return 'sentence-t5' if get_similarity_model() is not None else 'lexical'


def status():
    """What the AI features will use right now (for the UI and admins)."""
    available = libraries_available()
    return {
        'engine_setting': settings.AI_ENGINE,
        'question_generation': {
            'model': settings.AI_QG_MODEL,
            'available': available and settings.AI_QG_MODEL not in _qg_failed,
            'loaded': settings.AI_QG_MODEL in _qg,
            'models': {
                quality: {'model': model_for(quality), 'loaded': model_for(quality) in _qg,
                          'available': available and model_for(quality) not in _qg_failed}
                for quality in QUALITY_MODELS
            },
        },
        'answer_grading': {
            'model': settings.AI_SIMILARITY_MODEL,
            'available': available and not _sim_failed,
            'loaded': _sim is not None,
            'threshold': settings.SHORT_ANSWER_THRESHOLD,
            'partial_threshold': settings.SHORT_ANSWER_PARTIAL_THRESHOLD,
        },
    }
