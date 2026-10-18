// Notifications through the app (web push): subscribe and unsubscribe this device. Server: app/webpush.py.
// Works only over https (or localhost) and with a service worker; on the iPhone only when Tuttiphon is on the home screen.
import { api } from './api.js'
import { t } from './i18n.svelte.js'

export const ios = () => /iphone|ipad|ipod/i.test(navigator.userAgent)
export const supported = () => window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window

const toKey = (b64) => {
  const s = atob(b64.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (b64.length % 4)) % 4))
  return Uint8Array.from(s, (c) => c.charCodeAt(0))
}

async function current() {
  const reg = await navigator.serviceWorker.ready
  return { reg, sub: await reg.pushManager.getSubscription() }
}

/** State on this device: { supported, why, permission, on, devices, enabled } (why: a code, not a text) */
export async function state() {
  if (!supported()) {
    return { supported: false, why: !window.isSecureContext ? 'https' : ios() ? 'homescreen' : 'browser' }
  }
  const info = await api('/api/push/key')
  if (!info.available) return { supported: false, why: 'server' }
  const { sub } = await current()
  const st = await api('/api/push/status', { body: { endpoint: sub?.endpoint || '' } })
  return { supported: true, permission: Notification.permission, on: !!sub && st.known, devices: st.devices, enabled: info.enabled }
}

/** Subscribe this device: asks for permission, registers the subscription with the server. */
export async function enable() {
  const perm = await Notification.requestPermission()
  if (perm !== 'granted') throw new Error(t('Notifications are not allowed for Tuttiphon.'))
  const { key } = await api('/api/push/key')
  const { reg, sub: old } = await current()
  let sub
  try {
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toKey(key) })
  } catch (e) {   // old subscription with a different key: unsubscribe first, then again
    if (!old) throw e
    await old.unsubscribe()
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: toKey(key) })
  }
  await api('/api/push/subscribe', { body: { subscription: sub.toJSON(), origin: location.origin } })
}

/** Unsubscribe this device */
export async function disable() {
  const { sub } = await current()
  if (!sub) return
  await api('/api/push/unsubscribe', { body: { endpoint: sub.endpoint } })
  await sub.unsubscribe()
}

export const test = () => api('/api/push/test', { body: {} })
