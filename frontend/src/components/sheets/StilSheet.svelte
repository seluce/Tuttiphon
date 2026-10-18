<!--
  Content of a vibe's side sheet: name, icon, group and all rules (genres, artists, keywords, period, sound,
  hiding in other playlists). s: vibe from S.config (changed directly).
  Opened by openStil(s) in pages/Richtungen.svelte (adds missing fields and provides the footer).
-->
<script>
  import { untrack } from 'svelte'
  import Icon from '../Icon.svelte'
  import Field from '../Field.svelte'
  import Select from '../Select.svelte'
  import Switch from '../Switch.svelte'
  import ChipEditor from '../ChipEditor.svelte'
  import ArtistChips from '../ArtistChips.svelte'
  import GlyphButton from '../GlyphButton.svelte'
  import SoundEditor from '../SoundEditor.svelte'
  import { changed } from '../../lib/state.svelte.js'
  import { toast } from '../../lib/overlay.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'
  import { GROUP_LABEL, stilGroups, genreSuggestions, normMD, showMD } from '../../lib/richtungen.js'

  let { s } = $props()

  const ch = () => changed()
  const f = $derived(s.filters)
  const groups = stilGroups()
  const RATINGS = $derived([['0', t('any')], ['1', '★'], ['2', '★★'], ['3', '★★★'], ['4', '★★★★'], ['5', '★★★★★']])
  // Fold-out sections: open if something is already set there (when the sheet opens)
  const { openTime, openSound, openEx } = untrack(() => {
    const ff = s.filters || {}, ex = s.excludeElsewhere || {}
    return {
      openTime: !!(s.season || ff.years || ff.minRating || ff.addedDays || ff.notPlayedDays || ff.loved),
      openSound: !!s.sound,
      openEx: !!(ex.albums?.length || ex.titles?.length || ex.genres?.length),
    }
  })

  /** Number from an input field (empty → null). */
  const numOf = (e) => (e.currentTarget.value === '' ? null : Number(e.currentTarget.value))
  /** Set a filter – 0, empty or off removes it. */
  const setF = (k) => (v) => {
    if (v == null || v === 0 || v === false) delete f[k]
    else f[k] = v
    ch()
  }

  function seasonFrom(e) {
    const v = e.currentTarget.value.trim()
    const md = normMD(v)
    if (v && !md) { toast(t('Please enter the date as DD.MM., e.g. {example}', { example: '25.11.' }), { error: true }); e.currentTarget.value = showMD(s.season?.[0]); return }
    s.season = md ? [md, s.season?.[1] || md] : null
    e.currentTarget.value = showMD(md)
    ch()
  }
  function seasonTo(e) {
    const v = e.currentTarget.value.trim()
    const md = normMD(v)
    if (v && !md) { toast(t('Please enter the date as DD.MM., e.g. {example}', { example: '06.01.' }), { error: true }); e.currentTarget.value = showMD(s.season?.[1]); return }
    if (s.season) s.season[1] = md || s.season[0]
    e.currentTarget.value = showMD(s.season?.[1])
    ch()
  }
  function yearsFrom(e) {
    const v = numOf(e)
    if (!v) delete f.years
    else f.years = [v, f.years?.[1] || v + 9]
    ch()
  }
  function yearsTo(e) {
    const v = numOf(e)
    if (f.years) f.years[1] = v || f.years[0]
    ch()
  }
</script>

<div class="flex gap-2.5 items-center">
  <GlyphButton value={s.icon} size={24} onpick={(v) => { s.icon = v; ch() }} />
  <input class="input flex-1 min-w-0 font-bold text-[1.1rem]" value={s.name} aria-label={t('Name')}
    onchange={(e) => { s.name = e.currentTarget.value; ch() }} />
  <Select options={groups.map((g) => [g, GROUP_LABEL[g] ?? g])} value={s.group} aria-label={t('Group')} onchange={(v) => { s.group = v; ch() }} />
</div>

{#if s.kind === 'season'}
  <div class="note">{t('This vibe automatically collects all vibes whose season is on right now – Halloween and lantern songs in October, Christmas and winter in December. It changes every time playlists are applied.')}</div>
{:else}
  <Field label={t('Genre contains')}><ChipEditor items={s.genres} suggestions={genreSuggestions()} onchange={ch} /></Field>
  <Field label={t('Bands without matching genre tags')}><ArtistChips items={s.artists} onchange={ch} /></Field>
  <div class="frow">
    <Field label={t('Album title contains')}><ChipEditor items={s.albums} onchange={ch} /></Field>
    <Field label={t('Song title contains')}><ChipEditor items={s.titles} onchange={ch} /></Field>
  </div>

  <details class="fold" open={openTime}>
    <summary><Icon name="clock" size={18} />{t('Period, years, rating')}</summary>
    <div class="in">
      <div class="frow">
        <label class="f">{t('Season from')}
          <input class="input" placeholder={t('e.g. {example}', { example: '25.11.' })} value={showMD(s.season?.[0])} onchange={seasonFrom} />
        </label>
        <label class="f">{t('to')}
          <input class="input" placeholder={t('e.g. {example}', { example: '06.01.' })} value={showMD(s.season?.[1])} onchange={seasonTo} />
        </label>
      </div>
      <div class="frow">
        <label class="f">{t('Years from')} <input class="input" type="number" value={f.years?.[0] ?? ''} onchange={yearsFrom} /></label>
        <label class="f">{t('to')} <input class="input" type="number" value={f.years?.[1] ?? ''} onchange={yearsTo} /></label>
      </div>
      <div class="frow">
        <label class="f">{t('Minimum rating')}
          <Select options={RATINGS} value={f.minRating || 0} onchange={(v) => setF('minRating')(Number(v))} />
        </label>
        <label class="f">{t('new in the last … days')} <input class="input" type="number" value={f.addedDays ?? ''} onchange={(e) => setF('addedDays')(numOf(e))} /></label>
        <label class="f">{t('not played for … days')} <input class="input" type="number" value={f.notPlayedDays ?? ''} onchange={(e) => setF('notPlayedDays')(numOf(e))} /></label>
      </div>
      <Switch checked={!!f.loved} onchange={setF('loved')} label={t('favorites only ♥')} />
    </div>
  </details>

  <details class="fold" open={openSound}>
    <summary><Icon name="waves" size={18} />{t('Sound – mood, energy, tempo')}</summary>
    <div class="in"><SoundEditor obj={s} onchange={ch} /></div>
  </details>

  <details class="fold" open={openEx}>
    <summary><Icon name="ban" size={18} />{t('Hide from all other playlists')}</summary>
    <div class="in">
      <p class="muted small">{t('E.g. no Christmas songs in summer: whatever is listed here only appears in this vibe.')}</p>
      <div class="frow">
        <Field label={t('Album title contains')}><ChipEditor items={s.excludeElsewhere.albums} onchange={ch} /></Field>
        <Field label={t('Song title contains')}><ChipEditor items={s.excludeElsewhere.titles} onchange={ch} /></Field>
      </div>
      <Field label={t('Genre contains')}><ChipEditor items={s.excludeElsewhere.genres} suggestions={genreSuggestions()} onchange={ch} /></Field>
    </div>
  </details>
{/if}
