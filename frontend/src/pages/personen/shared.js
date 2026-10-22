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
