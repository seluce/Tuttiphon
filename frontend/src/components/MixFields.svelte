<!-- Settings of a mix (schedule, length in minutes or songs, songs per band, blend, recently played). Changes p.mix, then onchange(). -->
<script>
  import { untrack } from 'svelte'
  import Select from './Select.svelte'
  import { FLAVORS } from '../lib/editor.js'
  import { t, tn } from '../lib/i18n.svelte.js'

  let { p, onchange } = $props()
  untrack(() => (p.mix ??= {}))
  const m = $derived(p.mix ?? {})

  function set(k, v) {
    p.mix ??= {}
    if (v === '' || v == null) delete p.mix[k]
    else p.mix[k] = v
    onchange?.()
  }
  function size(e) {
    const el = e.currentTarget
    const v = el.value ? Math.max(10, Math.min(300, Math.round(Number(el.value)) || 50)) : null
    if (v) el.value = v
    set('size', v)
  }
  const PER = $derived([...[1, 2, 3, 4, 5].map((n) => [String(n), tn(n, '{n} song', '{n} songs')]), ['0', t('any')]])
</script>

<div class="frow">
  <label class="f">{t('Renew')}
    <Select options={[['day', t('daily')], ['week', t('weekly, on Mondays')], ['month', t('monthly, on the 1st')]]} value={m.every || 'day'}
      onchange={(v) => set('every', v === 'day' ? null : v)} />
  </label>
  <label class="f">{t('Length')}
    <Select options={[['', t('by number of songs')], ['20', t('{n} minutes', { n: 20 })], ['30', t('{n} minutes', { n: 30 })], ['45', t('{n} minutes', { n: 45 })], ['60', t('1 hour')], ['90', t('1½ hours')]]}
      value={m.minutes ? String(m.minutes) : ''} onchange={(v) => set('minutes', v ? Number(v) : null)} />
  </label>
  {#if !m.minutes}
    <label class="f">{t('Songs')}
      <input class="input" type="number" min="10" max="300" step="5" value={m.size || ''} placeholder="50" onchange={size} />
    </label>
  {/if}
  <label class="f">{t('At most per band')}
    <Select options={PER} value={String(m.perArtist ?? 3)} onchange={(v) => set('perArtist', Number(v))} />
  </label>
  <label class="f">{t('Blend')}
    <Select options={FLAVORS} value={m.flavor || 'ausgewogen'} onchange={(v) => set('flavor', v)} />
  </label>
  <label class="f">{t('Avoid recently played')}
    <Select options={[['0', t('no')], ['7', t('last {n} days', { n: 7 })], ['14', t('last {n} days', { n: 14 })], ['30', t('last {n} days', { n: 30 })]]} value={String(m.avoidRecent ?? 7)}
      onchange={(v) => set('avoidRecent', Number(v))} />
  </label>
</div>
