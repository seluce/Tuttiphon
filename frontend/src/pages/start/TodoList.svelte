<!-- "To review" (start page): notes from /api/inbox with their actions, can be hidden. -->
<script>
  import { untrack } from 'svelte'
  import Icon from '../../components/Icon.svelte'
  import { S, changed, snapshot, runTask, findWelt, save } from '../../lib/state.svelte.js'
  import { O, toast } from '../../lib/overlay.svelte.js'
  import { go } from '../../lib/router.svelte.js'
  import { api } from '../../lib/api.js'
  import { openArtist } from '../../lib/artist.js'
  import { openTakeover } from '../../lib/takeover.js'
  import { openEnvModal } from '../../lib/settings-info.js'
  import { cache } from './cache.svelte.js'
  import { t, tn } from '../../lib/i18n.svelte.js'

  const ICONS = { cred: 'lock', deezer: 'star', hand: 'folder', new: 'sparkles', auto: 'check', scenes: 'globe', low: 'alert', gone: 'trash', untagged: 'sliders',
    unused: 'pause', dup: 'copy', autowelt: 'globe', autowelten: 'globe' }
  const kind = (k) => k.split(/[|-]/)[0]
  const items = $derived(cache.inbox || [])
  const list = $derived(items.slice(0, cache.todoAll ? 99 : 5))

  function hide(it) {
    S.config.ignored.push(it.key)
    changed()
    cache.inbox = items.filter((x) => x !== it)
  }

  // After the band's window ("Assign music world …") closes: ask again – a band put into a world is no longer "new"
  let refresh = false
  $effect(() => {
    if (O.sheet || !refresh) return
    refresh = false
    untrack(() => save().then(() => api('/api/inbox')).then((d) => (cache.inbox = d)).catch(() => {}))
  })

  function act(a) {
    if (a.do === 'settings') return openEnvModal()
    if (a.do === 'artist') {
      openArtist(a.artist)
      refresh = true
      return
    }
    if (a.do === 'task') return runTask(a.steps)
    if (a.do === 'takeover') return openTakeover(a.file)
    if (a.do === 'goto') return go(a.href || { vorschlaege: '#/entdecken', welten: '#/welten', richtungen: '#/richtungen' }[a.tab] || '#/')
    if (a.do === 'edit') return go(`#/playlist/${encodeURIComponent(a.id)}`)
    if (a.do === 'pause' || a.do === 'pauseAll') {   // take unused playlists out of Symfonium – they stay here
      const ids = new Set(a.ids || [a.id])
      const list = S.config.playlists.filter((p) => ids.has(p.id) && (p.status || 'aktiv') === 'aktiv')
      if (!list.length) return
      snapshot()
      for (const p of list) p.status = 'pausiert'
      changed()
      toast(tn(list.length, 'Paused', '{n} playlists paused'), { undo: true })
      cache.inbox = (cache.inbox || []).filter((x) => !(x.actions || []).includes(a))
    }
    if (a.do === 'addToWelt') {
      const w = findWelt(a.welt)
      if (!w) { toast(t('This music world no longer exists'), { error: true }); return }
      snapshot()
      w.artists ??= []
      if (!w.artists.includes(a.artist)) w.artists.push(a.artist)
      changed()
      toast(`${a.artist} → ${w.name}`, { undo: true })
      cache.inbox = (cache.inbox || []).filter((x) => x.key !== `new|${a.artist}`)
    }
    if (a.do === 'undoAssign') {   // take an automatically classified band out again – and keep it out
      const w = findWelt(a.welt)
      if (w) {
        snapshot()
        w.artists = (w.artists || []).filter((x) => x !== a.artist)
        w.excludedArtists ??= []
        if (!w.excludedArtists.includes(a.artist)) w.excludedArtists.push(a.artist)
        changed()
        toast(t('{artist} is no longer in {world}', { artist: a.artist, world: w.name }), { undo: true })
      }
      cache.inbox = (cache.inbox || []).filter((x) => x.key !== `auto|${a.artist}`)
    }
    if (a.do === 'removeGone') {
      const w = findWelt(a.welt)
      if (w) {
        snapshot()
        w.artists = (w.artists || []).filter((x) => !a.artists.includes(x))
        changed()
        toast(t('Cleaned up'), { undo: true })
      }
      cache.inbox = (cache.inbox || []).filter((x) => !(x.actions || []).includes(a))
    }
  }
</script>

{#if !cache.inbox}
  <div class="skel h-[76px]"></div>
{:else}
  <div class="todo">
    {#each list as it (it)}
      <div class="todo-item {it.level}">
        <div class="ic"><Icon name={ICONS[kind(it.key)] || 'inbox'} size={18} /></div>
        <div class="min-w-0">
          <b>{it.title}</b>
          <div class="t">{it.text}</div>
          <div class="btns">
            {#each it.actions as a, i (i)}
              <button class="btn sm" onclick={() => act(a)}>{a.label}</button>
            {/each}
            <button class="btn sm ghost ml-auto" title={t('Don’t show again')} onclick={() => hide(it)}>{t('hide')}</button>
          </div>
        </div>
      </div>
    {:else}
      <div class="todo-item">
        <div class="ic bg-[rgba(34,197,94,.15)] text-ok"><Icon name="check" size={18} /></div>
        <div><b>{t('All good')}</b><div class="t">{t('Nothing to do right now.')}</div></div>
      </div>
    {/each}
    {#if items.length > 5}
      <button class="link" onclick={() => (cache.todoAll = !cache.todoAll)}>{cache.todoAll ? t('show less') : t('show {n} more', { n: items.length - 5 })}</button>
    {/if}
  </div>
{/if}
