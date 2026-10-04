import { expect, test } from '@playwright/test'

const PASSWORD = 'Demo@12345'

async function signIn(page, email) {
  await page.goto('/login')
  await page.getByLabel('Email', { exact: true }).fill(email)
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: /sign in/i }).click()
}

test('student takes the open exam and sees an instant result', async ({ page }) => {
  await signIn(page, 'student@demo.edu')
  await expect(page.getByRole('heading', { name: /Hello, Ali/ })).toBeVisible()

  await page.goto('/exams')
  await page.getByRole('button', { name: /^Start$/ }).first().click()
  await page.getByRole('button', { name: 'Begin exam' }).click()

  // This exam requires fullscreen: the lock screen appears once the exam has loaded.
  await expect(page.locator('.exam-question')).toBeVisible()
  await page.getByRole('button', { name: 'Enter fullscreen' }).click()
  await expect(page.locator('.lock-overlay')).toHaveCount(0)

  // Answer every question, moving with the Next button.
  const total = await page.locator('.nav-q').count()
  for (let i = 0; i < total; i += 1) {
    const box = page.locator('.exam-question textarea')
    if (await box.count()) await box.fill('A transaction is a single unit of work that completes entirely or not at all.')
    else await page.locator('.exam-question .opt-row').first().click()
    if (i < total - 1) await page.getByRole('button', { name: /Next/ }).click()
  }
  await expect(page.locator('.nav-q.answered')).toHaveCount(total)

  await page.getByRole('button', { name: /Review & submit/ }).click()
  await page.getByRole('button', { name: /Submit now/ }).click()

  await expect(page.getByRole('heading', { name: 'Exam result' })).toBeVisible()
  await expect(page.locator('.ring-value')).toContainText('%')
  await expect(page.getByText('Question feedback')).toBeVisible()
})

test('instructor reviews a flagged short answer', async ({ page }) => {
  await signIn(page, 'instructor@demo.edu')
  await expect(page.getByRole('heading', { name: /Ayesha/ })).toBeVisible()

  await page.goto('/results')
  const examSelect = page.locator('.page-head select')
  await expect(examSelect.locator('option', { hasText: 'Trees and Sorting' })).toHaveCount(1)
  const label = (await examSelect.locator('option').allTextContents()).find((t) => t.includes('Trees and Sorting'))
  await examSelect.selectOption({ label })
  await page.getByRole('tab', { name: /Review/ }).click()
  await page.getByRole('button', { name: 'All short answers' }).click()
  const card = page.locator('.review-card').first()
  await expect(card).toBeVisible()
  await card.locator('.marks-picker button').last().click()
  await card.getByPlaceholder(/Note to the student/).fill('Good explanation.')
  await card.getByRole('button', { name: /Save marks|Confirm/ }).click()
  await expect(page.getByText('Marks saved')).toBeVisible()
})

test('instructor dashboard, analytics and dark mode render', async ({ page }) => {
  await signIn(page, 'instructor@demo.edu')
  await expect(page.getByText('Class average by exam')).toBeVisible()
  await page.getByRole('link', { name: 'Results & Analytics' }).click()
  await page.getByRole('tab', { name: /Item analysis/ }).click()
  await expect(page.getByText(/Discrimination/).first()).toBeVisible()
  await page.getByRole('button', { name: /Switch to dark mode/ }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
})
