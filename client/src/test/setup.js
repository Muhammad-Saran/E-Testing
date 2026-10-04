import '@testing-library/jest-dom/vitest'

// jsdom lacks matchMedia (used by the theme provider).
if (!window.matchMedia) {
  window.matchMedia = () => ({ matches: false, addEventListener() {}, removeEventListener() {} })
}
