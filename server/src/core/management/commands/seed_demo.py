"""
Demo data for presentations and the viva.

    python manage.py seed_demo            # create (or recreate) the demo data
    python manage.py seed_demo --fast     # grade with the rule-based engine (no model loading)
    python manage.py seed_demo --load-test 100   # also 100 students + an open exam for load testing
    python manage.py seed_demo --remove   # delete everything this command created

Every demo account uses an @demo.edu email and the password printed at the end.
"""
import random
from datetime import timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from src.services.accounts.models import User
from src.services.ai.generation import generate_questions
from src.services.ai.models import GenerationJob, JobStatus
from src.services.courses.models import Course, CourseMaterial, Enrollment
from src.services.exams.models import Exam, ExamAttempt, ExamQuestion, ExamStatus, ProctorEvent
from src.services.exams.services import assign_questions, grade_attempt, save_answers
from src.services.notifications.models import NotificationType
from src.services.notifications.services import notify, notify_results_ready
from src.services.questionbank.models import Question, QuestionOption

DOMAIN = 'demo.edu'
PASSWORD = 'Demo@12345'

STUDENT_NAMES = [
    ('Ali', 'Raza'), ('Ayesha', 'Khan'), ('Hamza', 'Ahmed'), ('Fatima', 'Noor'), ('Usman', 'Tariq'),
    ('Zainab', 'Iqbal'), ('Bilal', 'Hussain'), ('Hira', 'Saeed'), ('Saad', 'Malik'), ('Maryam', 'Javed'),
    ('Hassan', 'Shah'), ('Iqra', 'Aslam'), ('Ahmed', 'Farooq'), ('Sana', 'Butt'), ('Omer', 'Qureshi'),
    ('Laiba', 'Anwar'), ('Talha', 'Mirza'), ('Mahnoor', 'Siddiqui'), ('Arslan', 'Akram'), ('Rabia', 'Yousaf'),
    ('Danish', 'Abbasi'), ('Kiran', 'Rehman'), ('Fahad', 'Nawaz'), ('Amna', 'Zafar'),
]

# (text, type, difficulty, answer, wrong options / keywords, marks)
DS_QUESTIONS = [
    ('Which data structure follows the Last In First Out (LIFO) principle?', 'mcq', 'remember', 'Stack',
     ['Queue', 'Linked list', 'Heap']),
    ('What is the worst-case time complexity of binary search on a sorted array of n elements?', 'mcq', 'understand',
     'O(log n)', ['O(n)', 'O(n log n)', 'O(1)']),
    ('Which traversal of a binary search tree visits the keys in sorted order?', 'mcq', 'understand', 'In-order',
     ['Pre-order', 'Post-order', 'Level-order']),
    ('Which data structure is used to implement breadth-first search?', 'mcq', 'apply', 'Queue',
     ['Stack', 'Priority queue', 'Hash table']),
    ('In a max-heap, where is the largest element stored?', 'mcq', 'remember', 'At the root',
     ['In the leftmost leaf', 'In the last array position', 'At any leaf']),
    ('What is the average time complexity of searching a hash table with a good hash function?', 'mcq', 'understand',
     'O(1)', ['O(log n)', 'O(n)', 'O(n^2)']),
    ('Which sorting algorithm has a worst-case time complexity of O(n log n)?', 'mcq', 'analyze', 'Merge sort',
     ['Quick sort', 'Bubble sort', 'Insertion sort']),
    ('How many children can a node in a binary tree have at most?', 'mcq', 'remember', '2', ['1', '3', 'Unlimited']),
    ('A queue removes elements in the same order in which they were inserted.', 'true_false', 'remember', 'true', []),
    ('Inserting an element at the beginning of an array takes constant time.', 'true_false', 'understand', 'false', []),
    ('A doubly linked list node stores references to both the next and the previous node.', 'true_false',
     'remember', 'true', []),
    ('Quick sort always runs in O(n log n) time.', 'true_false', 'analyze', 'false', []),
    ('What does LIFO stand for?', 'short_answer', 'remember', 'Last In First Out', ''),
    ('Explain the difference between a stack and a queue.', 'short_answer', 'understand',
     'A stack removes the most recently added element first (last in first out), while a queue removes the '
     'oldest element first (first in first out).', 'last in first out|lifo, first in first out|fifo'),
    ('Name the data structure that stores key-value pairs and uses a hash function to locate them.', 'short_answer',
     'remember', 'Hash table', ''),
    ('Describe what a balanced binary search tree guarantees.', 'short_answer', 'understand',
     'A balanced binary search tree keeps its height logarithmic in the number of nodes, so search, insertion and '
     'deletion take O(log n) time.', 'height|logarithmic|log n'),
]

DB_QUESTIONS = [
    ('Which SQL command removes all rows from a table but keeps the table structure?', 'mcq', 'remember', 'TRUNCATE',
     ['DROP', 'ALTER', 'REVOKE']),
    ('Which normal form removes transitive dependencies?', 'mcq', 'understand', 'Third normal form',
     ['First normal form', 'Second normal form', 'Unnormalized form']),
    ('What does the atomicity property of a transaction guarantee?', 'mcq', 'understand',
     'It happens completely or not at all', ['Its data is always encrypted', 'It runs in parallel',
                                            'It never reads stale data']),
    ('Which key uniquely identifies each row in a table?', 'mcq', 'remember', 'Primary key',
     ['Foreign key', 'Secondary index', 'Composite attribute']),
    ('Which JOIN returns only the rows that match in both tables?', 'mcq', 'apply', 'INNER JOIN',
     ['LEFT JOIN', 'FULL OUTER JOIN', 'CROSS JOIN']),
    ('Which SQL clause filters groups after aggregation?', 'mcq', 'apply', 'HAVING', ['WHERE', 'ORDER BY', 'LIMIT']),
    ('A foreign key can reference the primary key of another table.', 'true_false', 'remember', 'true', []),
    ('Adding an index always makes INSERT statements faster.', 'true_false', 'analyze', 'false', []),
    ('SQLite stores an entire database in a single file.', 'true_false', 'remember', 'true', []),
    ('What does SQL stand for?', 'short_answer', 'remember', 'Structured Query Language', ''),
    ('Define normalization.', 'short_answer', 'understand',
     'Normalization organizes tables to reduce data redundancy and improve data integrity.',
     'redundancy|duplicate, integrity|consistency|consistent'),
    ('Explain what a transaction is in a database.', 'short_answer', 'understand',
     'A transaction is a sequence of operations performed as a single unit of work that either completes '
     'entirely or has no effect.', 'unit|all or nothing|completely|entirely'),
]

# Plausible student answers to the short-answer questions: (good, near miss, wrong).
SHORT_ANSWERS = {
    'What does LIFO stand for?': ('last in first out', 'Last in fast out', 'Last input first output'),
    'Explain the difference between a stack and a queue.': (
        'In a stack the last element pushed is removed first (LIFO); a queue serves the earliest added element first (FIFO).',
        'A stack is last in first out but a queue is different.',
        'A stack stores numbers and a queue stores strings.'),
    'Name the data structure that stores key-value pairs and uses a hash function to locate them.':
        ('hash table', 'hashtable map', 'array'),
    'Describe what a balanced binary search tree guarantees.': (
        'It keeps the tree height logarithmic so search, insert and delete run in O(log n).',
        'The tree stays balanced so operations are fast.',
        'All nodes have exactly two children.'),
    'What does SQL stand for?': ('Structured Query Language', 'Structured Question Language', 'Simple Query Logic'),
    'Define normalization.': (
        'Normalization structures tables to remove duplicate data and keep the data consistent.',
        'Normalization reduces data redundancy in tables.',
        'Normalization makes queries faster by adding indexes.'),
    'Explain what a transaction is in a database.': (
        'A transaction is a group of operations treated as one unit of work: either all of them complete or none do.',
        'A transaction is a set of SQL statements.',
        'A transaction is a table that stores payments.'),
}

DS_NOTES = """Lecture 3: Stacks and Queues

A stack is a linear data structure that follows the Last In First Out principle. The push operation adds an element to the top of the stack, and the pop operation removes the element from the top. Stacks are used to implement function calls, undo features and expression evaluation.

A queue is a linear data structure that follows the First In First Out principle. Elements are added at the rear with the enqueue operation and removed from the front with the dequeue operation. Queues are used in breadth-first search, printer spooling and CPU scheduling.

A circular queue reuses the empty space at the front of the array by wrapping the rear pointer around. A priority queue removes the element with the highest priority first and is usually implemented with a binary heap. A binary heap stores the largest element at the root in a max-heap.

Binary search finds an element in a sorted array in logarithmic time by repeatedly halving the search interval. Merge sort divides the array into halves, sorts each half and merges them, giving a worst-case running time of O(n log n). Quick sort is fast on average but takes quadratic time in the worst case.
"""

DB_NOTES = """Lecture 5: Normalization and Transactions

Normalization is the process of organizing the tables of a relational database to reduce data redundancy and improve data integrity. Edgar F. Codd introduced the relational model in 1970.

A table is in First Normal Form when every column holds atomic values. Second Normal Form removes partial dependencies on a composite primary key. Third Normal Form removes transitive dependencies, so that non-key columns depend only on the primary key.

A transaction is a sequence of operations executed as a single logical unit of work. The ACID properties are atomicity, consistency, isolation and durability. Atomicity guarantees that a transaction is applied completely or not at all. Durability guarantees that committed changes survive a system crash.

SQLite is an embedded database engine that stores an entire database in a single file. The HAVING clause filters groups after aggregation, while the WHERE clause filters rows before grouping.
"""


class Command(BaseCommand):
    help = 'Create realistic demo data (instructor, students, courses, questions, exams with results).'

    def add_arguments(self, parser):
        parser.add_argument('--fast', action='store_true', help='Grade with the rule-based engine (no AI models).')
        parser.add_argument('--load-test', type=int, default=0, metavar='N',
                            help='Also create N students and an open exam for scripts/load_test.py.')
        parser.add_argument('--remove', action='store_true', help='Delete all demo data and stop.')

    def handle(self, *args, **options):
        self.rng = random.Random(2026)
        removed = self.remove()
        if options['remove']:
            self.stdout.write(self.style.SUCCESS(f'Removed {removed} demo accounts and their data.'))
            return
        overrides = {'NOTIFICATION_EMAILS': False}
        if options['fast']:
            overrides['AI_ENGINE'] = 'rule'
        with override_settings(**overrides):
            self.now = timezone.now()
            self.build()
            if options['load_test']:
                self.build_load_test(options['load_test'])
        self.report(options['load_test'])

    # ------------------------------------------------------------------
    def remove(self):
        demo = User.objects.filter(email__iendswith='@' + DOMAIN)
        for material in CourseMaterial.objects.filter(course__instructor__in=demo):
            material.file.delete(save=False)
        count = demo.count()
        demo.delete()
        return count

    @staticmethod
    def code(code):
        """Course codes are unique; avoid clashing with a real course of the same code."""
        return code if not Course.objects.filter(code=code).exists() else f'{code}-DEMO'

    def user(self, email, first, last, role, reg='', **extra):
        u = User.objects.create_user(email=f'{email}@{DOMAIN}', password=PASSWORD, first_name=first,
                                     last_name=last, role=role, registration_number=reg, **extra)
        return u

    def questions(self, course, rows, ai_flags=()):
        made = []
        for i, (text, qtype, difficulty, answer, extra) in enumerate(rows):
            q = Question.objects.create(
                course=course, created_by=self.teacher, text=text, question_type=qtype, difficulty=difficulty,
                subject=course.title, marks=1 if qtype != 'short_answer' else 2,
                correct_answer_text=answer if qtype != 'mcq' else '',
                required_keywords=extra if qtype == 'short_answer' else '',
                is_ai_generated=i in ai_flags,
            )
            if qtype == 'mcq':
                for j, option in enumerate([answer] + extra):
                    QuestionOption.objects.create(question=q, text=option, is_correct=j == 0, order=j)
            elif qtype == 'true_false':
                QuestionOption.objects.create(question=q, text='True', is_correct=answer == 'true', order=0)
                QuestionOption.objects.create(question=q, text='False', is_correct=answer == 'false', order=1)
            made.append(q)
        return made

    def exam(self, course, title, questions, opens, hours=2, duration=20, marks=None, **fields):
        exam = Exam.objects.create(
            course=course, created_by=self.teacher, title=title, status=ExamStatus.PUBLISHED,
            available_from=self.now + opens, available_until=self.now + opens + timedelta(hours=hours),
            duration_minutes=duration, **fields,
        )
        for order, q in enumerate(questions):
            ExamQuestion.objects.create(exam=exam, question=q, order=order, marks=marks or q.marks)
        return exam

    def sit(self, exam, student, ability):
        """Simulate one student taking the exam with a given ability (0..1)."""
        started = exam.available_from + timedelta(minutes=self.rng.randint(0, 40))
        attempt = ExamAttempt.objects.create(exam=exam, student=student, started_at=started)
        attempt.question_order = assign_questions(attempt)
        attempt.save(update_fields=['question_order'])
        payload = []
        from src.services.exams.services import attempt_questions
        for eq in attempt_questions(attempt):
            q = eq.question
            if self.rng.random() < 0.04:
                continue  # skipped
            level_penalty = {'remember': 0, 'understand': 0.05, 'apply': 0.1, 'analyze': 0.18}.get(q.difficulty, 0.1)
            right = self.rng.random() < ability - level_penalty
            if q.question_type == 'short_answer':
                good, near, wrong = SHORT_ANSWERS.get(q.text, (q.correct_answer_text, q.correct_answer_text, 'not sure'))
                text = good if right else (near if self.rng.random() < 0.5 else wrong)
                payload.append({'exam_question_id': eq.id, 'answer_text': text})
            else:
                options = list(q.options.all())
                correct = [o for o in options if o.is_correct]
                wrong_opts = [o for o in options if not o.is_correct]
                choice = correct[0] if right or not wrong_opts else self.rng.choice(wrong_opts)
                payload.append({'exam_question_id': eq.id, 'selected_option_id': choice.id})
        save_answers(attempt, payload)
        for _ in range(self.rng.choice([0, 0, 0, 0, 1, 1, 2, 4])):
            ProctorEvent.objects.create(attempt=attempt, event_type='tab_switch',
                                        occurred_at=started + timedelta(minutes=self.rng.randint(1, 15)))
        timed_out = self.rng.random() < 0.08
        grade_attempt(attempt, auto=timed_out)
        finished = attempt.deadline if timed_out else started + timedelta(minutes=self.rng.randint(6, exam.duration_minutes - 1))
        ExamAttempt.objects.filter(pk=attempt.pk).update(submitted_at=finished)

    # ------------------------------------------------------------------
    @transaction.atomic
    def build(self):
        self.teacher = self.user('instructor', 'Ayesha', 'Malik', 'instructor', 'EMP-1042')
        self.admin = self.user('admin', 'System', 'Admin', 'instructor', is_staff=True, is_superuser=True)
        self.students = [self.user('student' if i == 0 else f'{first.lower()}.{last.lower()}', first, last, 'student',
                                   f'FA22-BCS-{i + 1:03d}')
                         for i, (first, last) in enumerate(STUDENT_NAMES)]
        self.ability = {s.id: self.rng.uniform(0.5, 0.98) for s in self.students}
        self.ability[self.students[0].id] = 0.82  # the account used for live demos

        ds = Course.objects.create(code=self.code('CSC211'), title='Data Structures and Algorithms', instructor=self.teacher,
                                   description='Linear and non-linear data structures, searching and sorting.')
        db = Course.objects.create(code=self.code('CSC371'), title='Database Systems', instructor=self.teacher,
                                   description='Relational model, SQL, normalization and transactions.')
        for s in self.students:
            Enrollment.objects.create(course=ds, student=s)
        for s in self.students[:18]:
            Enrollment.objects.create(course=db, student=s)

        CourseMaterial.objects.create(course=ds, title='Lecture 3 - Stacks and Queues', uploaded_by=self.teacher,
                                      file=ContentFile(DS_NOTES.encode(), name='lecture-3-stacks-and-queues.txt'))
        CourseMaterial.objects.create(course=db, title='Lecture 5 - Normalization and Transactions',
                                      uploaded_by=self.teacher,
                                      file=ContentFile(DB_NOTES.encode(), name='lecture-5-normalization.txt'))

        dsq = self.questions(ds, DS_QUESTIONS, ai_flags=(4, 10))
        dbq = self.questions(db, DB_QUESTIONS, ai_flags=(2, 8))

        d = timedelta
        ds_quiz1 = self.exam(ds, 'Quiz 1 - Linear Structures', [dsq[i] for i in (0, 1, 3, 4, 8, 9, 12, 14)],
                             opens=-d(days=21), duration=15)
        ds_quiz2 = self.exam(ds, 'Quiz 2 - Trees and Sorting', [dsq[i] for i in (2, 5, 6, 7, 10, 11, 13, 15)],
                             opens=-d(days=10), duration=20)
        ds_mid = self.exam(ds, 'Midterm - Data Structures', dsq[:12], opens=-d(days=3), hours=3, duration=30,
                           marks=2, questions_per_student=8, require_fullscreen=True, max_violations=5,
                           description='Each student receives 8 of 12 questions from the pool.')
        db_quiz1 = self.exam(db, 'Quiz 1 - SQL Basics', [dbq[i] for i in (0, 3, 4, 6, 9, 10)],
                             opens=-d(days=14), duration=15)
        db_quiz2 = self.exam(db, 'Quiz 2 - Normalization and Transactions', [dbq[i] for i in (1, 2, 5, 7, 8, 11)],
                             opens=-d(hours=1), hours=50, duration=20, require_fullscreen=True, max_violations=3,
                             description='Open now. Fullscreen is required; 3 violations submit the exam.')
        self.exam(ds, 'Quiz 3 - Hashing and Heaps', [dsq[i] for i in (4, 5, 9, 14)], opens=d(days=3), duration=15)
        draft = self.exam(ds, 'Final Exam (draft)', dsq, opens=d(days=30), duration=60)
        Exam.objects.filter(pk=draft.pk).update(status=ExamStatus.DRAFT)

        for exam, cohort in ((ds_quiz1, self.students), (ds_quiz2, self.students), (ds_mid, self.students),
                             (db_quiz1, self.students[:18])):
            for s in cohort:
                if self.rng.random() < 0.92:  # a few students miss each exam
                    # Students improve a little over the term.
                    boost = 0.05 if exam in (ds_quiz2, ds_mid) else 0
                    self.sit(exam, s, min(0.98, self.ability[s.id] + boost))
            notify_results_ready(exam)
        # Half the class has already taken the open quiz; the demo student has not.
        for s in self.students[1:10]:
            self.sit(db_quiz2, s, self.ability[s.id])

        notify(self.students, NotificationType.ANNOUNCEMENT, 'CSC211: Midterm results are out',
               'Well done everyone. Review the question feedback and bring questions to Thursday\'s class.',
               link='/results')
        notify(self.students[:18], NotificationType.ANNOUNCEMENT, 'CSC371: Quiz 2 is open',
               'Quiz 2 covers normalization and transactions. Fullscreen is required.', link='/exams')

        # An AI generation waiting for the instructor's review.
        candidates, engine_name = generate_questions(DS_NOTES, 'mixed', 6, 'auto', ds.title, seed=7)
        GenerationJob.objects.create(
            created_by=self.teacher, course=ds, source_text=DS_NOTES, question_type='mixed', count=6,
            subject=ds.title, status=JobStatus.DONE, engine=engine_name, candidates=candidates,
            started_at=self.now - d(minutes=5), finished_at=self.now - d(minutes=5),
            material=CourseMaterial.objects.filter(course=ds).first(),
        )
        self.courses = (ds, db)

    @transaction.atomic
    def build_load_test(self, n):
        course = Course.objects.create(code=self.code('LT100'), title='Load Test Course', instructor=self.teacher)
        questions = self.questions(course, DS_QUESTIONS[:12] + DB_QUESTIONS[9:10])
        self.exam(course, 'Load Test Exam', questions, opens=-timedelta(minutes=5), hours=6, duration=60)
        users = [User(email=f'load{i:04d}@{DOMAIN}', first_name='Load', last_name=f'Student {i}', role='student',
                      registration_number=f'LT-{i:04d}') for i in range(1, n + 1)]
        template = User(email='x@x')
        template.set_password(PASSWORD)  # hash once; bcrypt is deliberately slow
        for u in users:
            u.password = template.password
        User.objects.bulk_create(users)
        Enrollment.objects.bulk_create([Enrollment(course=course, student=u)
                                        for u in User.objects.filter(email__startswith='load', email__endswith=DOMAIN)])

    def report(self, load_test):
        line = self.style.SUCCESS
        self.stdout.write(line('\nDemo data ready.  Password for every account: ' + PASSWORD))
        self.stdout.write(f'  Instructor : instructor@{DOMAIN}')
        self.stdout.write(f'  Student    : student@{DOMAIN}   (has results, and one open exam to take)')
        self.stdout.write(f'  Admin      : admin@{DOMAIN}     (Django admin at /admin/)')
        self.stdout.write(f'  + {len(STUDENT_NAMES) - 1} more students, e.g. ayesha.khan@{DOMAIN}')
        if load_test:
            self.stdout.write(f'  Load test  : load0001@{DOMAIN} ... load{load_test:04d}@{DOMAIN} on "Load Test Exam"')
