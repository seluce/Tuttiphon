<!--
  "From your listening": what Tuttiphon has recognized from plays, favorites and own stars (/api/taste) – with
  taking it over into the preferences. person: id of the person · me: own account without a profile (welcome assistant) ·
  likes: the person's likes object (changed directly) · self: addressed as "you" · name: name for the admin view.
-->
<script>
  import Icon from './Icon.svelte'
  import Avatar from './Avatar.svelte'
  import { openArtist } from '../lib/artist.js'
  import { api } from '../lib/api.js'
  import { t } from '../lib/i18n.svelte.js'

  let { person = null, me = false, likes, self = true, name = '', onchange = () => {} } = $props()

  let taste = $state.raw(null)
  $effect(() => {
    let gone = false
    api(`/api/taste?${me ? 'me=1' : 'person=' + encodeURIComponent(person)}`)
      .then((r) => { if (!gone) taste = r })
      .catch(() => { if (!gone) taste = { available: false, hasAccount: false } })
    return () => { gone = true }
  })

  const pct = (x) => t('{n}%', { n: Math.max(1, Math.round(x * 100)) })
  const has = (kind, id) => (likes?.[kind] || []).includes(id)
  const strong = $derived((taste?.welten || []).filter((w) => w.share >= 0.08))
  const open = $derived(strong.some((w) => !has('welten', w.id)) || (taste?.artists || []).slice(0, 5).some((a) => !has('artists', a.name)))

  function add(kind, id) {
    likes[kind] ??= []
    if (!likes[kind].includes(id)) likes[kind].push(id)
    onchange()
  }
  function addAll() {
    likes.welten ??= []
    likes.artists ??= []
    for (const w of strong) if (!has('welten', w.id)) likes.welten.push(w.id)
    for (const a of taste.artists.slice(0, 5)) if (!has('artists', a.name)) likes.artists.push(a.name)
    onchange()
  }
</script>

{#if taste?.available && taste.enough}
  <div class="card grid gap-4" data-guide="taste">
    <!-- phone: the text takes the row next to the icon, the button goes below it -->
    <div class="flex items-start gap-3 max-mobile:flex-wrap">
      <span class="grid place-items-center size-10 rounded-xl bg-accent text-white shrink-0"><Icon name="sparkles" size={20} /></span>
      <div class="flex-1 min-w-0 max-mobile:basis-[calc(100%-52px)]">
        <h2>{self ? t('From your listening') : t('From {name}’s listening', { name })}</h2>
        <p class="muted small">{self
          ? t('Tuttiphon recognized this from what you listen to in Symfonium, mark as favorite and rate yourself. Your suggestions and mixes are built from it.')
          : t('Recognized from what {name} listens to, marks as favorite and rates. Suggestions and mixes are built from it.', { name })}
          {#if taste.sound}{self ? t('Also learns from the sound of what you play.') : t('Also learns from the sound of what {name} plays.', { name })}{/if}</p>
      </div>
      {#if open && likes}<button class="btn sm primary shrink-0 max-mobile:ml-[52px]" onclick={addAll}><Icon name="plus" size={15} />{t('Add all')}</button>{/if}
    </div>

    {#if taste.welten.length}
      <div class="grid gap-1.5">
        <b class="small">{t('Music worlds')}</b>
        {#each taste.welten as w (w.id)}
          <div class="flex items-center gap-3">
            <span class="w-[150px] max-mobile:w-[110px] ell small">{w.name}</span>
            <div class="progress flex-1"><i style:width="{Math.min(100, w.share * 250)}%"></i></div>
            <span class="tiny muted w-[44px] text-right">{pct(w.share)}</span>
            {#if likes}
              {#if has('welten', w.id)}
                <span class="tiny ok-t w-[110px] text-right">✓ {t('Favorite world')}</span>
              {:else}
                <button class="btn sm w-[110px] px-2.5 gap-1.5" title={t('Remember as favorite world')} onclick={() => add('welten', w.id)}><Icon name="plus" size={14} class="shrink-0" />{t('Remember')}</button>
              {/if}
            {/if}
          </div>
        {/each}
      </div>
    {/if}

    {#if taste.artists.length}
      <div class="grid gap-1.5">
        <b class="small">{self ? t('Your most played bands') : t('Most played bands')}</b>
        <div class="chips">
          {#each taste.artists as a (a.name)}
            <span class="chip has-av">
              <button type="button" class="contents cursor-pointer" onclick={() => openArtist(a.name)}><Avatar name={a.name} size={24} />{a.name}</button>
              {#if likes && !has('artists', a.name)}
                <button type="button" class="x" title={t('Add as favorite band')} aria-label={t('Add “{name}” as favorite band', { name: a.name })} onclick={() => add('artists', a.name)}>+</button>
              {/if}
            </span>
          {/each}
        </div>
      </div>
    {/if}

    {#if taste.moods.length || taste.styles.length}
      <div class="grid gap-1.5">
        <b class="small">{self ? t('This is how what you listen to sounds') : t('This is how what is played sounds')}</b>
        <div class="btns">
          {#each taste.moods as m (m.id)}<span class="pill acc">{m.label}</span>{/each}
          {#each taste.styles as st (st)}<span class="pill">{st}</span>{/each}
        </div>
      </div>
    {/if}
  </div>
{:else if taste?.available && !taste.enough}
  <div class="note flex gap-2.5 items-center" data-guide="taste"><Icon name="sparkles" size={18} class="shrink-0" />
    <span>{self ? t('As soon as you listen more in Symfonium or mark favorites, Tuttiphon recognizes your taste here.') : t('{name} has not listened enough yet to recognize the taste.', { name })}</span>
  </div>
{:else if taste && taste.hasAccount && !taste.available}
  <div class="note flex gap-2.5 items-center" data-guide="taste"><Icon name="key" size={18} class="shrink-0" />
    {#if self}
      <span>{t('Tuttiphon recognizes your taste from what you listen to as soon as statistics & stars are turned on.')} <a class="link" href="#/einstellungen/konto">{t('Turn on →')}</a></span>
    {:else}
      <span>{t('No password is stored for {name}. With a password, Tuttiphon recognizes the taste from what is played.', { name })}</span>
    {/if}
  </div>
{/if}
