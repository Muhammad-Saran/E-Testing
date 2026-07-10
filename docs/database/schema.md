# e-Testing Service — Database Design & Schema

**DBMS:** SQLite · **ORM:** Django · **Normalization:** 3NF

This document describes the Phase 1 schema (implemented and migrated) and the Phase 2 tables
(designed, to be created as their modules are built).

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

   ── Phase 2 (designed) ──
   Exam ─∞─ ExamQuestion ─∞─ Question
   Exam ─1─∞─ Submission ─1─∞─ Answer
   Submission ─1─1─ Result
   User ─1─∞─ Notification
```

## 2. Implemented tables (Phase 1)

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

## 3. Designed tables (Phase 2)

These are specified now so the schema is complete; they are created with their modules.

- **`exams_exam`** — title, course_id, start_at, duration_minutes, total_marks,
  question_count, randomize (bool), status (`draft`/`scheduled`/`active`/`closed`). *(Module 4)*
- **`exams_examquestion`** — exam_id, question_id, order. Junction selecting bank questions
  into an exam. *(Module 4)*
- **`exams_submission`** — exam_id, student_id, started_at, submitted_at, status. *(Module 5)*
- **`exams_answer`** — submission_id, question_id, selected_option_id / answer_text,
  is_correct, awarded_marks. *(Module 6)*
- **`exams_result`** — submission_id (1:1), score, percentage, per-question JSON,
  computed_at (immutable). *(Module 6)*
- **`notifications_notification`** — user_id, type, message, is_read, created_at. *(Module 9)*

## 4. Design principles applied

- **3NF** — no transitive dependencies; lookup values live in their own rows/tables.
- **Referential integrity** — every relationship is a real FK with an explicit `on_delete`.
- **Auditability** — every business table carries `created_at` / `updated_at`
  (via `TimeStampedModel`).
- **Least surprise for RBAC** — ownership FKs (`instructor_id`, `created_by_id`) drive both
  querysets and object-level permissions.
- **Indexing** — composite indexes on the columns the API filters by most (role/active,
  type/difficulty, instructor/active).
