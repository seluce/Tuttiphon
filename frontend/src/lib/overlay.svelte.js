// Sheet, dialog (modal) and notice (toast) – one of each at a time, drawn in App.svelte.
//
// Content comes either as a snippet (defined in a component with {#snippet name()} … {/snippet} and
// simply passed as a value in <script>) or as a component with props:
//
//   openSheet({ title: t('Edit'), body: editorBody, foot: editorFoot, wide: true })
//   openSheet({ title: name, component: ArtistSheet, props: { name } })
//   const ok = await confirmDialog(t('Delete?'), t('This cannot be undone.'), t('Delete'), true)
//   const v = await modal({ title: t('Apply'), body: choiceSnippet, buttons: [{ label: t('Cancel'), value: 'cancel' }, { label: 'OK', value: 'ok', primary: true }] })
//
import { undo as undoLast } from './state.svelte.js'
import { dropTransient, isLeaving, afterLeaving } from './router.svelte.js'
import { t } from './i18n.svelte.js'

// $state.raw: components, snippets and props are not wrapped in proxies (props from S.config stay
// what they are – reactive objects).

class Overlay {
  sheet = $state.raw(null)
  modal = $state.raw(null)
  toast = $state.raw(null)
}
export const O = new Overlay()

/**
 * Sheet on the right (on the phone from the bottom).
 * @param {{ title?: string, head?: Function, body?: Function, foot?: Function, component?: any, props?: object,
 *           wide?: boolean, onClose?: Function }} opts
 *   head: snippet instead of the title text · body/foot: snippets · component+props: component as content
 */
export function openSheet(opts) {
  hideSheet()
  O.sheet = { ...opts, opener: document.activeElement, id: Math.random() }
  // own history entry (same address): the back button – e.g. on Android – closes the sheet instead of leaving the page.
  // A sheet that replaces another one keeps its entry.
  afterLeaving(() => {
    if (O.sheet && !history.state?.ntSheet) history.pushState({ ...history.state, ntSheet: true }, '')
  })
}
export function closeSheet() {
  if (!hideSheet()) return
  // remove the sheet's entry again – unless something navigated or opened a new sheet right after (same click)
  setTimeout(() => { if (!O.sheet) dropTransient() })
}
function hideSheet() {
  const s = O.sheet
  if (!s) return null
  O.sheet = null
  s.onClose?.()
  if (s.opener?.isConnected) s.opener.focus?.({ preventScroll: true })
  return s
}
export const sheetOpen = () => !!O.sheet

// Back button while a sheet is open: close it (its history entry is already gone)
addEventListener('popstate', () => {
  if (!O.sheet || history.state?.ntSheet || isLeaving()) return
  if (O.modal) closeModal('cancel')
  hideSheet()
})

/**
 * Dialog in the middle. Returns the value of the pressed button ('cancel' for ✕/Esc).
 * The button with primary: true is the default (Enter in an input field triggers it).
 * @param {{ title: string, text?: string, body?: Function, component?: any, props?: object,
 *           buttons?: {label: string, value: string, primary?: boolean, danger?: boolean}[], wide?: boolean }} opts
 */
export function modal(opts) {
  if (O.modal) O.modal.resolve('cancel')
  return new Promise((resolve) => {
    O.modal = { buttons: [{ label: 'OK', value: 'ok', primary: true }], ...opts, resolve }
  })
}
export function closeModal(value = 'cancel') {
  const m = O.modal
  if (!m) return
  O.modal = null
  m.resolve(value)
}
export const modalOpen = () => !!O.modal

export const confirmDialog = async (title, text, yes = t('Yes'), danger = false) =>
  // never make something dangerous the default button – Enter must not delete anything
  (await modal({ title, text, buttons: [{ label: t('Cancel'), value: 'cancel' }, { label: yes, value: 'yes', primary: !danger, danger }] })) === 'yes'

let toastTimer
/**
 * Short notice at the bottom. Errors stay until they are closed.
 * @param {string} msg
 * @param {{ error?: boolean, action?: {label: string, run: Function}, undo?: boolean }} [opts]
 *   undo: "Undo" button (restores the state before the last snapshot())
 */
export function toast(msg, { error = false, action = null, undo = false } = {}) {
  clearTimeout(toastTimer)
  const buttons = []
  if (undo) buttons.push({ label: t('Undo'), run: undoLast })
  if (action) buttons.push(action)
  O.toast = { msg, error, buttons, id: Math.random() }
  // errors stay until they are closed (or replaced by the next notice) – they must not slip by unread
  if (!error) toastTimer = setTimeout(hideToast, buttons.length ? 6500 : 2600)
}
export function hideToast() {
  clearTimeout(toastTimer)
  O.toast = null
}
