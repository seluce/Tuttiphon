<!-- Edit the sound filter (moods, instruments and themes of the AI + energy/tempo/danceability, and from the AI how easy
     to listen to and how much for close listening). Sets obj.sound or removes it. -->
<script>
  import Field from './Field.svelte'
  import Seg from './Seg.svelte'
  import SoundPicker from './SoundPicker.svelte'
  import { MOODS } from '../lib/state.svelte.js'
  import { soundCatalog } from '../lib/sound.svelte.js'
  import { t } from '../lib/i18n.svelte.js'

  let { obj, onchange } = $props()
  const RANGES = $derived({
    energy: [['', t('any')], ['0-0.35', t('low')], ['0.3-0.7', t('medium')], ['0.6-1', t('high')]],
    bpm: [['', t('any')], ['0-95', t('slow')], ['90-125', t('medium')], ['120-220', t('fast')]],
    dance: [['', t('any')], ['0.5-1', t('very danceable')], ['0-0.55', t('not for dancing')]],
    // AI (ml_worker.SCORES) – the delivered vibes “In the background” (approachable 0.6–1, engaging 0–0.6) and
    // “For listening closely” (engaging 0.75–1) use exactly these ranges
    approachable: [['', t('any')], ['0-0.45', t('low')], ['0.6-1', t('high')]],
    engaging: [['', t('any')], ['0-0.6', t('low')], ['0.75-1', t('high')]],
  })
  const snd = $derived(obj.sound || {})
  // the AI values only once the AI has analyzed songs (the sound catalog says so) – or if already chosen
  const cat = soundCatalog()
  const ai = $derived(cat.available || !!snd.approachable || !!snd.engaging)
  const FIELDS = $derived([['energy', t('Energy')], ['bpm', t('Tempo')], ['dance', t('Danceability')],
    ...(ai ? [['approachable', t('Easy to listen to')], ['engaging', t('For close listening')]] : [])])

  function save(next) {
    const clean = Object.fromEntries(Object.entries(next).filter(([, v]) => (Array.isArray(v) ? v.length : v != null)))
    if (Object.keys(clean).length) obj.sound = clean
    else delete obj.sound
    onchange?.()
  }
  function current(key) {
    const cur = snd[key] ? `${snd[key][0]}-${snd[key][1]}` : ''
    return RANGES[key].some(([v]) => v === cur) ? cur : ''
  }
  function toggleMood(id) {
    const m = new Set(snd.moods || [])
    if (m.has(id)) m.delete(id)
    else m.add(id)
    save({ ...snd, moods: [...m] })
  }
</script>

<div class="grid gap-3.5">
  <Field label={t('Mood – one of them is enough')}>
    <div class="toggles">
      {#each Object.entries(MOODS) as [id, label] (id)}
        <button type="button" class="toggle" class:on={(snd.moods || []).includes(id)} onclick={() => toggleMood(id)}>{label}</button>
      {/each}
    </div>
  </Field>
  <SoundPicker value={snd.instruments || []} onchange={(ids) => save({ ...snd, instruments: ids })} />
  <SoundPicker kind="themes" value={snd.themes || []} onchange={(ids) => save({ ...snd, themes: ids })} />
  <div class="frow">
    {#each FIELDS as [key, label] (key)}
      <Field {label}>
        <Seg options={RANGES[key]} value={current(key)} onchange={(v) => save({ ...snd, [key]: v ? v.split('-').map(Number) : null })} />
      </Field>
    {/each}
  </div>
  <div class="hint">{t('Detected by the sound analysis, adjustable under Settings → Intelligence. Because Navidrome does not know the sound, playlists by sound are only available as a mix.')}</div>
</div>
