// End-to-end tests against the real Django server + built React app.
// `npm run e2e` builds the client, seeds a throw-away database and runs the
// tests in the system's Google Chrome (no browser download needed).
import os from 'node:os'
import path from 'node:path'
import { defineConfig } from '@playwright/test'

const PORT = 8799
const DB = path.join(os.tmpdir(), 'etesting-e2e.sqlite3')

export default defineConfig({
  testDir: './e2e',
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: 'chrome',
    headless: true,
    viewport: { width: 1366, height: 860 },
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `python manage.py migrate --noinput && python manage.py seed_demo --fast && python manage.py runserver 127.0.0.1:${PORT} --noreload`,
    cwd: path.resolve('..', 'server'),
    url: `http://127.0.0.1:${PORT}/api/health/`,
    timeout: 240_000,
    reuseExistingServer: false,
    env: { ...process.env, DATABASE_PATH: DB, AI_ENGINE: 'rule', THROTTLE_LOGIN: '1000/min', NOTIFICATION_EMAILS: 'False' },
  },
})
