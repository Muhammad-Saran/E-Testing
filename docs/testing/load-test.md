# Load test — concurrent examination delivery

The scope document (§5.3) claims the platform supports many simultaneous examination sessions.
This test measures it.

## Method

`server/scripts/load_test.py` simulates students with one thread each. Every student:

1. signs in (`POST /api/auth/login/`, bcrypt password check);
2. waits at a barrier, so **all students start the exam at the same instant** (worst case);
3. starts the exam (`/start/`, question pool assignment and session key);
4. autosaves three times with a growing set of answers (`/save/`), like the real client;
5. submits (`/submit/`, grading and result notification).

Setup: `python manage.py seed_demo --fast --load-test 300` on a scratch database, served by
`python manage.py serve` (Waitress, 32 threads, `DEBUG=False`), SQLite in WAL mode with
`IMMEDIATE` transactions. Exam: 13 questions (12 objective, 1 short answer).
Machine: Intel Core i5-1145G7 (4 cores), 16 GB RAM, Windows 11, Python 3.14.

## Results

| Concurrent students | Requests | Errors | Throughput | start p95 | autosave median / p95 | submit median / p95 |
|---:|---:|---:|---:|---:|---:|---:|
| 50  | 300  | **0** | 14.8 req/s | 2.9 s | 1.6 s / 7.7 s | 1.4 s / 8.4 s |
| 100 | 600  | **0** | 21.4 req/s | 4.1 s | 2.1 s / 6.5 s | 3.5 s / 7.0 s |
| 200 | 1200 | **0** | 19.9 req/s | 7.7 s | 4.7 s / 10.8 s | 9.7 s / 17.3 s |

(50-student row measured before the autosave optimisation described below.)

## Findings

- **No failed requests** at 50, 100 or 200 simultaneous students: no "database is locked"
  errors, no lost answers, every attempt graded.
- The server sustains about **20 requests per second**. In a real exam the client autosaves
  every 15 s, so 200 students produce about 13 requests per second — within capacity — and they
  do not all press *Start* in the same millisecond as this test forces them to.
- **Sign-in is the slowest step** by design: bcrypt makes each password check deliberately
  expensive (scope doc Module 1), and 200 simultaneous checks queue for the CPU. Students
  normally sign in over several minutes before an exam opens.
- **Optimisation made from this test:** autosave originally wrote each answer in its own
  transaction (one SQLite write lock per question). It now writes all answers in one
  transaction with bulk inserts/updates, which removed the lock contention seen at 50 students.

## Limits and next steps

SQLite allows one writer at a time, so throughput will not grow much beyond this on one machine.
For an institution-wide deployment with several hundred students per sitting the same code can
run on PostgreSQL by changing `DATABASES` (outside this project's SQLite scope), and Waitress can
be scaled out behind a reverse proxy.

## Reproduce

```bash
cd server
set DATABASE_PATH=%TEMP%\load.sqlite3                 # never the real database
python manage.py migrate
python manage.py seed_demo --fast --load-test 300
set THROTTLE_LOGIN=100000/min                          # all simulated users share one IP
python manage.py serve --port 8790 --threads 32        # terminal 1
python scripts/load_test.py --students 100 --base-url http://127.0.0.1:8790             # terminal 2
python scripts/load_test.py --students 200 --offset 100 --base-url http://127.0.0.1:8790
```
