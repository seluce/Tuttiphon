<!--
  Settings → Navidrome → "Navidrome plugin": the plugin asks Tuttiphon for similar songs (Instant Mix, song and artist
  radio, the smart queue in Symfonium) and passes the plays on. Status from GET /api/plugin (key, the plugin's last
  request and for whom it was answered, the last play received, sound vectors),
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
  const addressHtml = address.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])   // into {@html}
  // for whom the last similar songs were chosen – with its own time: other requests (cover, biography) are for nobody
  const forWhom = $derived(!st?.lastForAt ? ''
    : !st.lastFor ? t('{when} · for everyone', { when: relTime(st.lastForAt) })
      : st.lastGuess ? t('{when} · probably for {name}', { when: relTime(st.lastForAt), name: st.lastFor })
        : t('{when} · for {name}', { when: relTime(st.lastForAt), name: st.lastFor }))
  // Navidrome's agents with Tuttiphon first – in front of Navidrome's defaults (0.64: deezer,lastfm,listenbrainz)
  const AGENTS = [['navidrome.toml', 'Agents = "tuttiphon,deezer,lastfm,listenbrainz"'],   // i18n-ignore: setting
    ['docker-compose', 'ND_AGENTS=tuttiphon,deezer,lastfm,listenbrainz']]   // i18n-ignore: setting

  async function load(quiet = false) {
    try { st = await api('/api/plugin') } catch (e) { if (!quiet) toast(e.message, { error: true }) }
  }
  load()
  $effect(() => {   // the plays and requests as they come
    const timer = setInterval(() => load(true), 30000)
    return () => clearInterval(timer)
  })

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
    if (!await confirmDialog(t('Remove the key?'), t('Navidrome then gets no more answers from Tuttiphon and uses its other sources again – turn the plugin off in Navidrome as well.'), t('Remove'), true)) return
    busy = true
    try {
      await api('/api/plugin/key/remove', { body: {} })
      key = ''
      await load()
    } catch (e) { toast(e.message, { error: true }) }
    busy = false
  }
  /** Copy – the clipboard of the browser exists only with https (or localhost); otherwise the old way. */
  async function copy(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text)
      else {
        // not read-only and 16 px: Safari on the iPhone selects nothing in a read-only field and zooms into small ones
        const area = Object.assign(document.createElement('textarea'), { value: text })
        area.style.cssText = 'position:fixed;top:0;opacity:0;font-size:16px'
        document.body.append(area)
        area.select()
        area.setSelectionRange(0, text.length)
        const ok = document.execCommand('copy')
        area.remove()
        if (!ok) throw new Error()
      }
      toast(t('Copied'))
    } catch { toast(t('Select the text and copy it'), { error: true }) }
  }
</script>

<Card title={t('Navidrome plugin')} icon="puzzle" guide="plugin">
  <p class="muted small">{t('With the plugin, Navidrome asks Tuttiphon for similar songs and passes every play on: Instant Mix, song and artist radio and the smart queue in Symfonium then follow the sound of your own music files – also for bands that other services hardly know. Needs Navidrome 0.64 or later.')}</p>
  {#if st}
    <Row label={t('Songs with a sound vector')} hint={st.vectors ? '' : t('No sound vectors yet – the AI sound analysis of the Docker image adds them night by night. Until then the plugin answers with similar bands from Last.fm and the genres.')}>
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
          <button class="btn sm" onclick={() => copy(key)} aria-label={t('Copy {what}', { what: t('Key') })}><Icon name="copy" size={15} />{t('Copy')}</button>
        </div>
      </div>
    {/if}
    <Row label={t('Plays from Navidrome')} hint={st.live?.lastEvent ? t('Every play as it happens – exact listening times and real skips; for accounts without a stored password also the recap.') : t('Nothing yet? Put the new plugin file into Navidrome, restart it and allow the plugin all users.')}>
      <span class={['pill whitespace-normal', st.live?.lastEvent && 'ok']}>{st.live?.lastEvent ? t('{when} · {accounts}', { when: relTime(st.live.lastEvent), accounts: st.live.accounts.join(', ') }) : t('none since Tuttiphon started')}</span>
    </Row>
    <Row label={t('Last request from Navidrome')} hint={st.lastCall ? t('{n} since Tuttiphon started', { n: fmt(st.calls) }) : ''}>
      <span class={['pill whitespace-normal', st.lastCall && 'ok']}>{st.lastCall ? relTime(st.lastCall) : t('none since Tuttiphon started')}</span>
    </Row>
    {#if st.lastForAt}
      <Row label={t('Last answer with similar songs')}>
        <span class="pill ok whitespace-normal">{forWhom}</span>
      </Row>
    {/if}
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
      <li>{@html t('Put the file as it is – not unpacked and named exactly <b>tuttiphon.ndp</b>, Navidrome takes the name for its list of agents – into Navidrome’s plugins folder (in the Navidrome container <code>/data/plugins</code>) and put “tuttiphon” first in that list, in navidrome.toml or in docker-compose:')}
        {#each AGENTS as [where, line] (where)}
          <div class="flex flex-wrap gap-x-2 gap-y-1 items-center mt-1.5">
            <span class="tiny muted w-[110px] max-mobile:w-full">{where}</span>
            <input class="input code flex-1 min-w-0" readonly value={line} aria-label={where} onfocus={(e) => e.currentTarget.select()} />
            <button class="btn sm ghost" onclick={() => copy(line)} title={t('Copy')} aria-label={t('Copy {what}', { what: where })}><Icon name="copy" size={15} /></button>
          </div>
        {/each}
        <span class="muted">{t('If there is a list already, put “tuttiphon,” in front of it – without one these are Navidrome’s defaults. The docker-compose line wins over navidrome.toml. Restart Navidrome afterwards; where Tuttiphon has no answer, Navidrome asks the next ones.')}</span>
      </li>
      <li>{@html t('In Navidrome under <b>Settings → Plugins</b> turn on “Tuttiphon”, enter the address and the key and allow it <b>all users</b> (for the plays). Ideally the address in the home network, e.g. <code>http://&lt;NAS&gt;:8765</code> – not an https address through a reverse proxy, which may turn Navidrome away. This browser reaches Tuttiphon at <code>{address}</code>.', { address: addressHtml })}</li>
      <li>{@html t('In Symfonium, turn on <b>“Use similar tracks for Radio Mix”</b> for the Navidrome server (Manage media providers → the server) and choose <b>“Sonic Analysis”</b> for the smart queue in the player.')}</li>
    </ol>
  </div>
  <div class="hint">{t('Navidrome does not say who is asking. If the song is playing on exactly one account – or only one account is playing – the answer is for that person: without their dislikes, without what they just heard or rated 1 star, what they often skip comes later, and after two songs of a band other bands come first. Otherwise for the family – without a family for everyone. Children’s music only for children’s songs, and without songs with explicit lyrics as soon as a person has kid-safe mode or is a child profile.')}</div>
</Card>

<style>
  .steps { list-style: decimal; padding-left: 1.3em; }
  .steps li { padding-left: .2em; }
  .code { font-family: ui-monospace, monospace; font-size: .85em; }
</style>
