// Own account: sign out, store the password of a Navidrome account.
import { api } from './api.js'
import { modal, toast } from './overlay.svelte.js'
import { passKey, loadStatus, loadLibrary } from './state.svelte.js'
import PasswordForm from '../pages/settings/PasswordForm.svelte'
import { t } from './i18n.svelte.js'

export async function logout() {
  try { await api('/api/logout', { body: {} }) } catch { /* does not matter */ }
  location.href = '/login.html'
}

/**
 * Dialog "Password for <user>": test it and save it in .env (for stars, personal statistics, preview).
 * @returns {Promise<boolean>} true if it was saved
 */
export async function passwordModal(user) {
  const form = { password: '' }
  const res = await modal({
    title: t('Password for “{user}”', { user }),
    component: PasswordForm,
    props: { user, form },
    buttons: [{ label: t('Cancel'), value: 'cancel' }, { label: t('Save'), value: 'save', primary: true }],
  })
  if (res !== 'save' || !form.password) return false
  try {
    await api('/api/env', { method: 'PUT', body: { [passKey(user)]: form.password } })
  } catch (e) {
    toast(e.message, { error: true })
    return false
  }
  toast(t('Saved ✓'))
  await loadStatus()
  loadLibrary(true).catch(() => {})
  return true
}
