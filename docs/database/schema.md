# e-Testing Service — Database Design & Schema

**DBMS:** SQLite · **ORM:** Django · **Normalization:** 3NF

This document describes the complete schema, implemented and migrated, for all nine modules.

---

## 1. Entity–Relationship overview

```
          ┌─────────────┐
          │    User     │  role = instructor | student
          └──────┬──────┘
     instructor  │  student
        ┌────────�┴────────────────────────────┐
        ▼                                       ▼
  ┌───────────┐  1        ∞  ┌────────────┐  ∞      1  ┌───────────┐
  │  Course   │─────────────►│ Enrollment │◄───────────│   User    │
  └─────┬─────┘              └────────────┘  (student)  └───────────┘
        │ 1                                                     
        ├──────────────► ∞ ┌────────────────┐
        │                  │ CourseMaterial │
        │                  └────────────────┘
        │ 1
        ▼ ∞
  ┌───────────┐  1        ∞  ┌────────────────┐
  │ Question  │─────────────►│ QuestionOption │
  └───────────┘              └────────────────┘
        ▲ created_by (instructor)

   Course ─1─∞─ Exam ─1─∞─ ExamQuestion ─∞─1─ Question
   Exam ─1─∞─ ExamAttempt (one per student) ─1─∞─ ExamAnswer ─∞─1─ ExamQuestion
   ExamAttempt ─1─∞─ ProctorEvent
   User ─1─∞─ AuthEvent
   User ─1─∞─ Notification                                   (Module 9)
   User ─1─∞─ GenerationJob ─∞─1─ Course / CourseMaterial    (Module 3)
```

## 2. Implemented tables

### `accounts_user` — application users
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| email | VARCHAR(255) UNIQUE | login field |
| password | VARCHAR(255) | bcrypt hash |
| first_name / last_name | VARCHAR(150) | |
| role | VARCHAR(20) | `instructor` \| `student` |
| registration_number | VARCHAR(50) | student reg # / staff id |
| is_active / is_staff | BOOL | |
| date_joined / last_login | DATETIME | |

Index: `(role, is_active)`.

### `courses_course`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| code | VARCHAR(20) UNIQUE | e.g. CSC336 |
| title | VARCHAR(255) | |
| description | TEXT | |
| instructor_id | FK → user | `on_delete=CASCADE`, role=instructor |
| is_active | BOOL | |
| created_at / updated_at | DATETIME | |

Index: `(instructor, is_active)`.

### `courses_enrollment` — student ↔ course (junction)
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| course_id | FK → course | CASCADE |
| student_id | FK → user | CASCADE, role=student |
| created_at / updated_at | DATETIME | |

**Unique** `(course_id, student_id)` — a student enrols in a course once.

### `courses_coursematerial`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| course_id | FK → course | CASCADE |
| title | VARCHAR(255) | |
| file | VARCHAR (upload path) | PDF / document |
| uploaded_by_id | FK → user | SET NULL |
| created_at / updated_at | DATETIME | |

### `questionbank_question`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| course_id | FK → course (nullable) | SET via CASCADE |
| created_by_id | FK → user | CASCADE, role=instructor |
| text | TEXT | prompt |
| question_type | VARCHAR(20) | `mcq` \| `true_false` \| `short_answer` |
| difficulty | VARCHAR(20) | Bloom tiers: remember…create |
| subject | VARCHAR(120) | topic domain |
| marks | INT | |
| correct_answer_text | TEXT | short-answer / T-F reference |
| required_keywords | VARCHAR(500) | short answers: `term \| alternative, term` |
| is_ai_generated | BOOL | T5 provenance (Module 3) |
| is_active | BOOL | |
| version | INT | question versioning |
| created_at / updated_at | DATETIME | |

Indexes: `(created_by, is_active)`, `(question_type, difficulty)`.

### `questionbank_questionoption`
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| question_id | FK → question | CASCADE |
| text | VARCHAR(500) | |
| is_correct | BOOL | |
| order | SMALLINT | display order |

### `accounts_authevent` — authentication audit trail
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| user_id | FK → user (nullable) | SET NULL |
| email | VARCHAR(255) | kept for failed logins on unknown accounts |
| event | VARCHAR(30) | register / login / login_failed / locked / logout / password_reset_request / password_reset / password_change |
| ip_address | VARCHAR (IP) | |
| created_at | DATETIME | |

Index: `(event, created_at)`. Logout invalidation uses simplejwt's `token_blacklist_*` tables.

### `exams_exam` *(Module 4)*
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| course_id | FK → course | CASCADE |
| created_by_id | FK → user | CASCADE, role=instructor |
| title / description | VARCHAR(255) / TEXT | |
| available_from / available_until | DATETIME | window in which the exam can be started |
| duration_minutes | INT | time limit once started |
| shuffle_questions | BOOL | per-student randomised order |
| shuffle_options | BOOL | per-student MCQ option order |
| questions_per_student | INT (nullable) | question pool: each student gets this many questions |
| require_fullscreen | BOOL | leaving fullscreen is a violation |
| max_violations | INT (nullable) | auto-submit at this many violations |
| status | VARCHAR(20) | `draft` \| `published` \| `closed` |
| created_at / updated_at | DATETIME | |

Index: `(course, status)`. `total_marks`, `question_count` and the lifecycle `state`
(draft / scheduled / active / closed) are **derived**, not stored, so they cannot drift (3NF).

### `exams_examquestion` — exam ↔ question (junction)
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| exam_id | FK → exam | CASCADE |
| question_id | FK → question | CASCADE |
| order | SMALLINT | |
| marks | INT | copied from the question when added |

**Unique** `(exam_id, question_id)`.

### `exams_examattempt` — one student's sitting *(Modules 5 & 6)*
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | also seeds the per-student question shuffle |
| exam_id | FK → exam | CASCADE |
| student_id | FK → user | CASCADE, role=student |
| started_at | DATETIME | deadline = started_at + duration |
| submitted_at | DATETIME (nullable) | |
| is_submitted | BOOL | once true the row is immutable |
| auto_submitted | BOOL | submitted by the server |
| submit_reason | VARCHAR(20) | `student` \| `time` \| `violations` \| `closed` |
| score | INT | |
| question_order | JSON | exam-question ids this student received, in order |
| session_key | VARCHAR(64) | the one browser session allowed to save / submit |
| ip_address / user_agent | IP / VARCHAR(255) | where the attempt was last opened from |
| created_at / updated_at | DATETIME | |

**Unique** `(exam_id, student_id)` — one attempt per student.

### `exams_examanswer` *(Module 6)*
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| attempt_id | FK → examattempt | CASCADE |
| exam_question_id | FK → examquestion | CASCADE |
| selected_option_id | FK → questionoption (nullable) | SET NULL |
| answer_text | TEXT | short answers |
| is_correct | BOOL (nullable) | null while autosaved but not yet graded |
| awarded_marks | INT | full, half (near miss) or zero |
| similarity | FLOAT (nullable) | short answers: 0–1 similarity to the reference answer |
| grading_method | VARCHAR(20) | `key` \| `exact` \| `fuzzy` \| `numeric` \| `sentence-t5` \| `lexical` |
| needs_review | BOOL | flagged for the instructor |
| reviewed_by_id / reviewed_at | FK → user / DATETIME | instructor override, if any |
| original_marks / review_note | INT / TEXT | marks before the review, and the instructor's note |

**Unique** `(attempt_id, exam_question_id)`.

### `exams_proctorevent` *(Module 5)*
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| attempt_id | FK → examattempt | CASCADE |
| event_type | VARCHAR(20) | `tab_switch` \| `window_blur` \| `fullscreen_exit` \| `copy_paste` \| `new_session` |
| occurred_at | DATETIME | |

### `notifications_notification` *(Module 9)*
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | |
| user_id | FK → user | CASCADE |
| type | VARCHAR(30) | exam_published / exam_reminder / result_published / answers_released / announcement / exam_results_ready / import_complete / ai_generation_complete / account_activity |
| title / message | VARCHAR(255) / TEXT | |
| link | VARCHAR(255) | in-app route it points to |
| is_read / emailed | BOOL | |
| dedupe_key | VARCHAR(120) | makes scheduled notifications idempotent |
| created_at / updated_at | DATETIME | |

Index: `(user, is_read)`. **Unique** `(user_id, dedupe_key)` where `dedupe_key` is not empty.

### `ai_generationjob` *(Module 3)*
| Column | Type | Notes |
|--------|------|-------|
| id | BIGINT PK | also seeds the generator, so a job is reproducible |
| created_by_id | FK → user | CASCADE — instructor (bank) or student (practice) |
| purpose | VARCHAR(20) | `bank` \| `practice` |
| quality | VARCHAR(20) | `fast` (T5-small) \| `better` (T5-base) |
| course_id | FK → course (nullable) | SET NULL; generated questions are tagged with it |
| material_id | FK → coursematerial (nullable) | SET NULL; source file, if any |
| source_text | TEXT | text the questions are generated from |
| question_type | VARCHAR(20) | `mcq` \| `true_false` \| `short_answer` \| `mixed` |
| difficulty / subject / count | VARCHAR / VARCHAR / SMALLINT | `auto` = Bloom classifier per question |
| status | VARCHAR(20) | `pending` \| `running` \| `done` \| `failed` |
| engine | VARCHAR(20) | `t5` \| `rule` |
| candidates | JSON | generated questions awaiting review |
| error | TEXT | |
| started_at / finished_at | DATETIME | |
| saved_count | INT | how many candidates were committed to the bank |
| practice_result | JSON (nullable) | a student's last checked practice answers and score |
| created_at / updated_at | DATETIME | |

Index: `(created_by, status)`. Committed questions are ordinary `questionbank_question` rows with
`is_ai_generated = true`; the candidates JSON is a review buffer, not a second source of truth.

## 4. Design principles applied

- **3NF** — no transitive dependencies; lookup values live in their own rows/tables.
- **Referential integrity** — every relationship is a real FK with an explicit `on_delete`.
- **Auditability** — every business table carries `created_at` / `updated_at`
  (via `TimeStampedModel`).
- **Least surprise for RBAC** — ownership FKs (`instructor_id`, `created_by_id`) drive both
  querysets and object-level permissions.
- **Indexing** — composite indexes on the columns the API filters by most (role/active,
  type/difficulty, instructor/active).
