// Access to the JSON interface of the Python server (app/web.py).
// Errors arrive as an Error with readable text – callers show it directly. Extra fields on the error:
//   status   HTTP status (0: no answer at all)
//   offline  true if Tuttiphon could not be reached (network gone, server stopped, proxy without a server behind it)
import { untrack } from 'svelte'
import { lang, t } from './i18n.svelte.js'

/** The address within the app (#/playlist/…) – carried through the sign-in so it opens there afterwards. */
export const appHash = () => (/^#\/[^\s<>"']*$/.test(location.hash) ? location.hash : '')

function failure(text, status, offline = false) {
  return Object.assign(new Error(text), { status, offline })
}

export async function api(path, opts = {}) {
  let res
  try {
    res = await fetch(path, {
      method: opts.method || (opts.body ? 'POST' : 'GET'),
      // X-Tuttiphon: protection against other websites sending requests to localhost (the server requires it for POST/PUT).
      // X-Lang: language of the messages the server returns (untracked: an $effect calling api() must not rerun on a
      // language switch – reloadTexts() fetches again what depends on it)
      headers: { 'X-Tuttiphon': '1', 'X-Lang': untrack(lang), 'Content-Type': 'application/json' },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    })
  } catch {
    // fetch itself failed (TypeError): no connection to Tuttiphon
    throw failure(t('Tuttiphon cannot be reached right now.'), 0, true)
  }
  if (res.status === 401) {
    location.href = '/login.html' + appHash()
    throw failure(t('Please sign in'), 401)
  }
  if (res.status === 403) {
    const d = await res.json().catch(() => ({}))
    throw failure(d.error || t('Only an administrator account may do this.'), 403)
  }
  const BAD = {}
  const data = await res.json().catch(() => BAD)   // no JSON (empty answer, error page of a proxy)
  if (!res.ok) {
    if (data?.error) throw failure(data.error, res.status)
    // no answer of Tuttiphon itself: a reverse proxy without the server behind it
    if ([502, 503, 504].includes(res.status)) throw failure(t('Tuttiphon cannot be reached right now.'), res.status, true)
    // (the status text is empty over HTTP/2 – and English otherwise)
    throw failure(t('The server reported an error ({status}).', { status: res.status }), res.status)
  }
  return data === BAD ? {} : data
}
