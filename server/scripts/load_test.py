"""
Concurrent exam load test (scope doc §5.3 — "scalable and concurrent examination delivery").

Every simulated student signs in, starts the "Load Test Exam", autosaves its
answers three times (as the real client does), and submits. All students run
at the same time. The script reports throughput, latency percentiles and errors
per step. Standard library only.

    cd server
    python manage.py seed_demo --fast --load-test 100      # on a scratch database!
    python manage.py serve --port 8000                    # Waitress (multi-threaded)
    python scripts/load_test.py --students 100 --base-url http://127.0.0.1:8000
"""
import argparse
import json
import statistics
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

PASSWORD = 'Demo@12345'


class Client:
    def __init__(self, base):
        self.base = base.rstrip('/') + '/api'
        self.headers = {'Content-Type': 'application/json'}

    def call(self, method, path, body=None):
        req = urllib.request.Request(self.base + path, method=method, headers=self.headers,
                                     data=json.dumps(body).encode() if body is not None else None)
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as res:
                data = json.loads(res.read() or b'null')
                status = res.status
        except urllib.error.HTTPError as exc:
            data, status = None, exc.code
        except Exception as exc:  # connection refused / reset / timeout
            data, status = str(exc), 0
        return status, data, (time.perf_counter() - start) * 1000


def find_exam(client):
    status, exams, _ = client.call('GET', '/exams/available/')
    if status != 200:
        raise SystemExit(f'Could not list exams ({status}).')
    exam = next((e for e in exams if e['title'] == 'Load Test Exam' and e['is_open']), None)
    if not exam:
        raise SystemExit('No open "Load Test Exam" — run: python manage.py seed_demo --fast --load-test N')
    return exam['id']


def student_run(base, email, exam_id, barrier, timings, errors, lock):
    c = Client(base)

    def step(name, method, path, body=None, ok=(200, 201)):
        status, data, ms = c.call(method, path, body)
        with lock:
            timings[name].append(ms)
            if status not in ok:
                errors[name].append(status)
        return status, data

    status, data = step('login', 'POST', '/auth/login/', {'email': email, 'password': PASSWORD})
    if status != 200:
        return
    c.headers['Authorization'] = f'Bearer {data["access"]}'
    barrier.wait()  # everyone starts the exam at the same moment
    status, data = step('start', 'POST', f'/exams/{exam_id}/start/', {})
    if status != 200:
        return
    c.headers['X-Exam-Session'] = data['session_key']
    answers = []
    for q in data['questions']:
        if q['question_type'] == 'short_answer':
            answers.append({'exam_question_id': q['id'], 'answer_text': 'Structured Query Language'})
        else:
            answers.append({'exam_question_id': q['id'], 'selected_option_id': q['options'][0]['id']})
    for i in range(3):  # progressive autosaves
        part = answers[: max(1, len(answers) * (i + 1) // 3)]
        step('autosave', 'POST', f'/exams/{exam_id}/save/', {'answers': part})
    step('submit', 'POST', f'/exams/{exam_id}/submit/', {'answers': answers})


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--students', type=int, default=50)
    parser.add_argument('--offset', type=int, default=0,
                        help='Skip this many load-test accounts (each account can sit the exam only once).')
    args = parser.parse_args()

    probe = Client(args.base_url)
    status, data, _ = probe.call('POST', '/auth/login/', {'email': 'load0001@demo.edu', 'password': PASSWORD})
    if status != 200:
        raise SystemExit(f'Login failed for load0001@demo.edu ({status}). Seed the load-test data first.')
    probe.headers['Authorization'] = f'Bearer {data["access"]}'
    exam_id = find_exam(probe)

    timings, errors, lock = defaultdict(list), defaultdict(list), threading.Lock()
    barrier = threading.Barrier(args.students, timeout=600)
    emails = [f'load{i:04d}@demo.edu' for i in range(args.offset + 1, args.offset + args.students + 1)]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.students) as pool:
        for email in emails:
            pool.submit(student_run, args.base_url, email, exam_id, barrier, timings, errors, lock)
    elapsed = time.perf_counter() - started

    total_requests = sum(len(v) for v in timings.values())
    print(f'\n{args.students} concurrent students, {total_requests} requests in {elapsed:.1f} s '
          f'({total_requests / elapsed:.1f} req/s)\n')
    print(f'{"step":<10}{"requests":>9}{"errors":>8}{"median ms":>11}{"p95 ms":>9}{"max ms":>9}')
    for name in ('login', 'start', 'autosave', 'submit'):
        values = timings.get(name, [])
        if not values:
            continue
        print(f'{name:<10}{len(values):>9}{len(errors.get(name, [])):>8}{statistics.median(values):>11.0f}'
              f'{pct(values, 95):>9.0f}{max(values):>9.0f}')
    failed = {k: sorted(set(v)) for k, v in errors.items() if v}
    print('\nErrors (HTTP status codes):', failed or 'none')


if __name__ == '__main__':
    main()
