// Theme: system | light | dark – saved in the browser (key nt-theme, as before).
// index.html sets the attribute before the first paint; here it is changed when switching.

export const themeChoice = () => {
  try { return localStorage.getItem('nt-theme') || 'system' } catch { return 'system' }
}

export function applyTheme(mode = themeChoice()) {
  if (mode === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', mode)
}

export function setTheme(mode) {
  try { localStorage.setItem('nt-theme', mode) } catch { /* private mode */ }
  applyTheme(mode)
}
