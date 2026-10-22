<!-- Music worlds: overview with collages. Administrators create new ones here. -->
<script>
  import Icon from '../components/Icon.svelte'
  import Collage from '../components/Collage.svelte'
  import PageHead from '../components/PageHead.svelte'
  import { S, isAdmin, myPerson, canEdit, weltIds } from '../lib/state.svelte.js'
  import { addWelt } from '../lib/welten.js'
  import { plural } from '../lib/format.js'
  import { t, tn } from '../lib/i18n.svelte.js'
  import { loadMyTaste, byRelevance, heardShare } from '../lib/taste.svelte.js'

  const admin = isAdmin()
  const info = $derived(S.library?.weltInfo || {})
  /** Do you like this world? */
  const likedBy = (wid) => (myPerson()?.likes?.welten || []).includes(wid)
  loadMyTaste()
  /** favorite worlds first (administrators: everyone's, users: their own), then what you listen to yourself */
  const sorted = $derived(byRelevance(S.config.welten, new Set((admin ? S.config.personen : [myPerson()].filter(Boolean)).flatMap((p) => p.likes?.welten || []))))
  const usedBy = (w) => S.config.playlists.filter((p) => weltIds(p).includes(w.id) && (p.status || 'aktiv') === 'aktiv' && (admin || canEdit(p))).length
</script>

<div class="page">
  <PageHead title={t('Music worlds')} sub={admin
    ? t('A music world says who plays. Tuttiphon creates them from your library and sorts new bands in on its own – by genres, Last.fm, AI music style, language and decade.')
    : t('Your music sorted by kind. Tap a world to see which bands belong to it – with “Like” you keep a world in mind for your suggestions.')}>
    {#snippet actions()}
      {#if admin}<button class="btn primary" data-guide="welt-neu" onclick={addWelt}><Icon name="plus" size={18} />{t('New music world')}</button>{/if}<!-- i18n-ignore: guide id -->
    {/snippet}
  </PageHead>

  <div class="g-welt">
    {#each sorted as w (w.id)}
      {@const i = info[w.id] || {}}
      {@const used = usedBy(w)}
      <a class="wcard" href="#/welt/{w.id}">
        <Collage artists={i.artists || []} icon={w.icon} title={w.name} sub="{plural(i.members || 0, 'band', 'bands')} · {plural(i.songs || 0, 'song', 'songs')}" />
        <div class="body">
          <div class="btns">
            {#if !admin && likedBy(w.id)}<span class="pill acc"><Icon name="heart" size={13} />{t('you like it')}</span>
            {:else if heardShare(w.id) >= 0.05}<span class="pill acc"><Icon name="headphones" size={13} />{t('you listen to it often')}</span>{/if}
            {#if admin && w.auto}<span class="pill acc"><Icon name="sparkles" size={13} />{t('created by Tuttiphon')}</span>{/if}
            {#if admin && w.scene && w.autoScene && !w.auto}<span class="pill acc"><Icon name="sparkles" size={13} />{t('finds bands on its own')}</span>{/if}
            {#if admin && w.separate}<span class="pill">{t('separate world')}</span>{/if}
            {#if used}<span class="pill">{admin ? plural(used, 'playlist', 'playlists') : tn(used, '{n} playlist of yours', '{n} playlists of yours')}</span>{/if}
          </div>
          <div class="muted small ell">{(i.artists || []).slice(0, 4).map((a) => a[0]).join(' · ')}</div>
        </div>
      </a>
    {/each}
    {#if admin}
      <button class="wcard border-dashed grid place-items-center min-h-[220px] bg-transparent" onclick={addWelt}>
        <div class="grid justify-items-center gap-2 text-muted">
          <Icon name="plus" size={30} />
          <b>{t('New music world')}</b>
          <span class="small">{t('from the scene catalog or empty')}</span>
        </div>
      </button>
    {/if}
  </div>
</div>
