// Stop the test server (PID via the port – never pkill -f) and delete the data copy.
import { execSync } from 'node:child_process'
import { readFileSync, rmSync } from 'node:fs'
import { PORT, STATE } from './setup.js'

export default async function teardown() {
  const pid = execSync(`ss -ltnp | grep ':${PORT} ' || true`, { encoding: 'utf8' }).match(/pid=(\d+)/)?.[1]
  if (pid) process.kill(Number(pid))
  try {
    const { work } = JSON.parse(readFileSync(STATE, 'utf8'))
    if (work?.includes('tuttiphon-e2e-')) rmSync(work, { recursive: true, force: true })
    rmSync(STATE, { force: true })
  } catch { /* already gone */ }
}
