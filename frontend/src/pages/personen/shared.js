// People: shared helpers for overview, profile and assistant.
import { S } from '../../lib/state.svelte.js'
import { api } from '../../lib/api.js'

export const COLORS = ['#8b5cf6', '#ec4899', '#f97316', '#eab308', '#22c55e', '#06b6d4', '#3b82f6', '#ef4444', '#64748b']

let userList = null
/** Navidrome accounts (administrators only) – fetched once, then remembered. If the request fails (Navidrome briefly gone),
 *  nothing is remembered: the next opening asks again, and users.error says why the list is empty. */
export async function users() {
  if (!userList) {
    try {
      const u = await api('/api/users')
      userList = Array.isArray(u) ? u : []
      users.error = ''
    } catch (e) {
      users.error = e.message
      return []
    }
  }
  return userList
}
users.error = ''
/** Ask Navidrome again next time (e.g. after Tuttiphon created the family's account). */
export const forgetUsers = () => { userList = null }

/** Navidrome accounts that already belong to a person (lower case) – except `but` (the person being edited). */
export const takenAccounts = (but = null) => new Set(S.config.personen.filter((x) => x !== but).map((x) => (x.user || '').toLowerCase()))

/** Is a (matching) password stored for this Navidrome account? */
export const pwOk = (user) => (S.status?.env?.users || []).find((u) => u.name.toLowerCase() === (user || '').toLowerCase())?.ok

/** Switch a value in a list on or off (changes the list itself). */
export function toggleIn(arr, id) {
  const i = arr.indexOf(id)
  if (i >= 0) arr.splice(i, 1)
  else arr.push(id)
}

/* Deezer stars per account (settings.deezer.users: a list of accounts – without one, every person's account) */
const sameAccount = (a, b) => String(a).toLowerCase() === String(b).toLowerCase()

/** Accounts for “Who gets stars?”: every person's account (the family's too) and accounts still chosen without a
 *  person – so each one can be switched on and off. */
export function starAccounts(dz) {
  const out = []
  for (const u of [...S.config.personen.map((p) => p.user), ...(Array.isArray(dz?.users) ? dz.users : [])]) {
    if (typeof u === 'string' && u && !out.some((x) => sameAccount(x, u))) out.push(u)
  }
  return out
}

/** Does Deezer set stars for this account? */
export const getsStars = (dz, user) => (Array.isArray(dz?.users) ? dz.users : starAccounts(dz)).some((u) => sameAccount(u, user))

/** Switch Deezer stars for an account on or off – from then on dz.users is a list. */
export function toggleStars(dz, user) {
  const cur = Array.isArray(dz.users) ? dz.users : starAccounts(dz)
  dz.users = getsStars(dz, user) ? cur.filter((u) => !sameAccount(u, user)) : [...cur, user]
}

/** An account goes away (its person is deleted): Deezer no longer rates it – only if there is a list of accounts. */
export function dropStars(dz, user) {
  if (user && Array.isArray(dz?.users)) dz.users = dz.users.filter((u) => !sameAccount(u, user))
}
