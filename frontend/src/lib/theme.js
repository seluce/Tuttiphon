// Theme: system | light | dark – saved in the browser (key tuttiphon-theme).
// index.html sets the attribute before the first paint; here it is changed when switching.

export const themeChoice = () => {
  try { return localStorage.getItem('tuttiphon-theme') || 'system' } catch { return 'system' }
}

export function applyTheme(mode = themeChoice()) {
  if (mode === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', mode)
}

export function setTheme(mode) {
  try { localStorage.setItem('tuttiphon-theme', mode) } catch { /* private mode */ }
  applyTheme(mode)
}
