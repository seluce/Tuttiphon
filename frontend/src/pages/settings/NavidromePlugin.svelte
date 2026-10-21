<!--
  Settings → Navidrome → "Navidrome plugin": the plugin asks Tuttiphon for similar songs (Instant Mix, song and artist
  radio, "similar songs" in Symfonium) and passes the plays on. Status from GET /api/plugin (key, the plugin's last
  request, the last play received, sound vectors),
  key: POST /api/plugin/key (shown once) and /api/plugin/key/remove, download: /plugin/tuttiphon.ndp, the setup steps.
-->
<script>
  import Icon from '../../components/Icon.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import { api } from '../../lib/api.js'
  import { confirmDialog, toast } from '../../lib/overlay.svelte.js'
  import { fmt, relTime } from '../../lib/format.js'
  import { t } from '../../lib/i18n.svelte.js'

  let st = $state(null)
  let key = $state('')   // a new key – shown only now
  let busy = $state(false)
  const address = location.origin
  // Navidrome's agents with Tuttiphon first – in front of Navidrome's defaults (0.64: deezer,lastfm,listenbrainz)
  const AGENTS = [['navidrome.toml', 'Agents = "tuttiphon,deezer,lastfm,listenbrainz"'],   // i18n-ignore: setting
    ['docker-compose', 'ND_AGENTS=tuttiphon,deezer,lastfm,listenbrainz']]   // i18n-ignore: setting

  async function load() {
    try { st = await api('/api/plugin') } catch (e) { toast(e.message, { error: true }) }
  }
  load()

  async function create() {
    if (st?.key && !await confirmDialog(t('Create a new key?'), t('The old key stops working – enter the new one in Navidrome afterwards.'), t('New key'))) return
    busy = true
    try {
      key = (await api('/api/plugin/key', { body: {} })).key
      await load()
    } catch (e) { toast(e.message, { error: true }) }
    busy = false
  }
  async function remove() {
    if (!await confirmDialog(t('Remove the key?'), t('Navidrome then gets no more answers from Tuttiphon and uses its other sources again.'), t('Remove'), true)) return
    busy = true
    try {
      await api('/api/plugin/key/remove', { body: {} })
      key = ''
      await load()
    } catch (e) { toast(e.message, { error: true }) }
    busy = false
  }
  async function copy(text) {
    try {
      await navigator.clipboard.writeText(text)
      toast(t('Copied'))
    } catch { toast(t('Select the text and copy it'), { error: true }) }
  }
</script>

<Card title={t('Navidrome plugin')} icon="puzzle" guide="plugin">
  <p class="muted small">{t('With the plugin, Navidrome asks Tuttiphon for similar songs: Instant Mix, song and artist radio and “similar songs” in Symfonium then follow the sound of your own music files – also for bands that other services hardly know.')}</p>
  {#if st}
    <Row label={t('Songs with a sound fingerprint')} hint={st.vectors ? '' : t('The AI sound analysis has not run yet – until then the plugin answers with similar bands from Last.fm and the genres.')}>
      <b>{fmt(st.vectors)}</b>
    </Row>
    <Row label={t('Key')} hint={st.key ? t('Created {when}', { when: relTime(st.keyAt) }) : t('Navidrome signs in to Tuttiphon with it.')}>
      <div class="btns">
        <button class={['btn sm', !st.key && 'primary']} disabled={busy} onclick={create}><Icon name="key" size={15} />{st.key ? t('New key') : t('Create key')}</button>
        {#if st.key}<button class="btn sm ghost" disabled={busy} onclick={remove}>{t('Remove')}</button>{/if}
      </div>
    </Row>
    {#if key}
      <div class="note grid gap-2">
        <b>{t('Your key – shown only now:')}</b>
        <div class="flex gap-2 items-center">
          <input class="input flex-1 min-w-0 font-mono" readonly value={key} aria-label={t('Key')} onfocus={(e) => e.currentTarget.select()} />
          <button class="btn sm" onclick={() => copy(key)}><Icon name="copy" size={15} />{t('Copy')}</button>
        </div>
      </div>
    {/if}
    <Row label={t('Plays from Navidrome')} hint={t('Every play as it happens – exact listening times and real skips; for accounts without a stored password also the recap.')}>
      <span class={st.live?.lastEvent ? 'pill ok' : 'pill'}>{st.live?.lastEvent ? t('{when} · {accounts}', { when: relTime(st.live.lastEvent), accounts: st.live.accounts.join(', ') }) : t('none yet')}</span>
    </Row>
    <Row label={t('Last request from Navidrome')} hint={st.lastCall ? t('{n} since Tuttiphon started', { n: fmt(st.calls) }) : ''}>
      <span class={st.lastCall ? 'pill ok' : 'pill'}>{st.lastCall ? relTime(st.lastCall) : t('none yet')}</span>
    </Row>
  {/if}
  <div class="set-row grid gap-2.5 py-3 border-t border-line">
    <b>{t('Setting it up')}</b>
    <ol class="steps grid gap-2 small">
      <li>
        {#if st?.file}
          <a class="btn sm" href="/plugin/tuttiphon.ndp" download><Icon name="download" size={15} />{t('Download the plugin')}</a>
          <span class="muted">tuttiphon.ndp</span><!-- i18n-ignore: file name -->
        {:else}
          {@html t('Download <b>tuttiphon.ndp</b> from the release on <a class="link" href="https://github.com/seluce/tuttiphon/releases" target="_blank" rel="noopener">GitHub</a>.')}
        {/if}
      </li>
      <li>{@html t('Put the file as it is – not unpacked – into Navidrome’s plugins folder (in the Navidrome container <code>/data/plugins</code>) and put “tuttiphon” first in Navidrome’s list of agents, in navidrome.toml or in docker-compose:')}
        {#each AGENTS as [where, line] (where)}
          <div class="flex gap-2 items-center mt-1.5">
            <code class="code flex-1 min-w-0">{line}</code>
            <span class="tiny muted w-[110px] max-mobile:hidden">{where}</span>
            <button class="btn sm ghost" onclick={() => copy(line)} title={t('Copy')}><Icon name="copy" size={15} /></button>
          </div>
        {/each}
        <span class="muted">{t('If there is a list already, put tuttiphon, in front of it – without one these are Navidrome’s defaults. The docker-compose line wins over navidrome.toml. Restart Navidrome afterwards; where Tuttiphon has no answer, Navidrome asks the next ones.')}</span>
      </li>
      <li>{@html t('In Navidrome under <b>Settings → Plugins</b> turn on “Tuttiphon”, enter the address and the key and allow it <b>all users</b> (for the plays). Best the address in the home network, e.g. <code>http://&lt;NAS&gt;:8765</code> – not an https address through a reverse proxy, which may turn Navidrome away. From this browser Tuttiphon is <code>{address}</code>.', { address })}</li>
      <li>{@html t('In Symfonium, turn on <b>“Use similar tracks for Radio Mix”</b> in the settings of the Navidrome server.')}</li>
    </ol>
  </div>
  <div class="hint">{t('Navidrome does not say who is listening: the songs come from the whole library as for the family. Children’s music only comes for children’s songs – and if there is a child profile, songs with explicit lyrics stay out.')}</div>
</Card>

<style>
  .steps { list-style: decimal; padding-left: 1.3em; }
  .steps li { padding-left: .2em; }
  .code { font-family: ui-monospace, monospace; font-size: .85em; background: var(--surface-2); border-radius: 8px; padding: 6px 10px; overflow-x: auto; white-space: nowrap; }
</style>
