// Starts a test server with a copy of data/ (sign-in on, auto-apply off) and remembers the sessions.
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export const PORT = 8790
export const STATE = join(tmpdir(), 'tuttiphon-e2e.json')

export default async function setup() {
  const work = mkdtempSync(join(tmpdir(), 'tuttiphon-e2e-'))
  const out = execFileSync('tools/testserver.sh', [String(PORT), work, '--auth', '--family'], { encoding: 'utf8' })
  const cookie = (role) => out.match(new RegExp(`${role}-cookie:\\s+tuttiphon=(\\S+)`))[1]
  const cfg = JSON.parse(readFileSync(join(work, 'data', 'config.json'), 'utf8'))
  // Warm up like a server that is already running: load the library and lists once (otherwise the first pages
  // all wait for the NAS at the same time and run into the timeout)
  const headers = { Cookie: `tuttiphon=${cookie('admin')}`, 'X-Tuttiphon': '1' }
  for (const path of ['/api/library', '/api/playlists', '/api/inbox', '/api/suggestions', '/api/home']) {
    await fetch(`http://127.0.0.1:${PORT}${path}`, { headers, signal: AbortSignal.timeout(180_000) }).catch(() => {})
  }
  // which account each cookie belongs to (the tour and the welcome assistant remember "seen" per account)
  const account = async (role) => {
    const me = await fetch(`http://127.0.0.1:${PORT}/api/me`, { headers: { Cookie: `tuttiphon=${cookie(role)}`, 'X-Tuttiphon': '1' } })
      .then((r) => r.json()).catch(() => ({}))
    return (me.user || '').toLowerCase()
  }
  writeFileSync(STATE, JSON.stringify({
    work,
    admin: cookie('admin'),
    user: cookie('user'),
    adminAccount: await account('admin'),
    userAccount: await account('user'),
    playlist: cfg.playlists.find((p) => (p.status || 'aktiv') === 'aktiv')?.id,
    welt: cfg.welten[0]?.id,
    person: (cfg.personen.find((p) => !p.family) ?? cfg.personen[0])?.id,   // a person's profile shows more than the family's
    personName: (cfg.personen.find((p) => !p.family) ?? cfg.personen[0])?.name,
  }))
}
