<!-- Playlist card in the grid: picture, name, state, count, person. Leads to the playlist page. -->
<script>
  import Icon from './Icon.svelte'
  import PlaylistArt from './PlaylistArt.svelte'
  import StateDot from './StateDot.svelte'
  import { plStatus, findPerson, defaultPerson, mixWording } from '../lib/state.svelte.js'
  import { plName } from '../lib/playlist.js'
  import { plural } from '../lib/format.js'
  import { t } from '../lib/i18n.svelte.js'

  let { p, onclick = undefined } = $props()
  const st = $derived(plStatus(p.id) || {})
  const person = $derived(findPerson(p.person || defaultPerson()))
  const off = $derived((p.status || 'aktiv') !== 'aktiv')
</script>

<a class="pcard" class:dim={off} href="#/playlist/{encodeURIComponent(p.id)}" {onclick}>
  <div class="art">
    <PlaylistArt {p} {st} />
    {#if p.type === 'mix'}<span class="badge-mix" title={t('Mix – {when}', { when: mixWording(p)[1] })}>{t('Mix')}</span>{/if}
    <div class="play"><Icon name="right" size={22} /></div>
  </div>
  <div>
    <div class="t">{plName(p)}</div>
    <div class="s">
      <StateDot state={st.state || p.status} />
      <span class="ell">{st.count != null ? plural(st.count, 'song', 'songs') : '…'} · {person?.name || ''}</span>
    </div>
  </div>
</a>
