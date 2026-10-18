<!-- Settings → Playlists: apply automatically, seasons, mixes (learning, smooth transitions), basic rules for all playlists. -->
<script>
  import Field from '../../components/Field.svelte'
  import Select from '../../components/Select.svelte'
  import ChipEditor from '../../components/ChipEditor.svelte'
  import Card from './Card.svelte'
  import Row from './Row.svelte'
  import Toggle from './Toggle.svelte'
  import NumInput from './NumInput.svelte'
  import { S, changed } from '../../lib/state.svelte.js'
  import { t } from '../../lib/i18n.svelte.js'

  S.config.settings.excludeTitles ??= []
  const s = S.config.settings

  function setPattern(e) {
    const el = e.currentTarget
    if (el.value.includes('{')) { s.namePattern = el.value; changed() } else el.value = s.namePattern
  }
</script>

<Card title={t('Apply')} icon="zap">
  <Row label={t('Apply automatically')} hint={t('A few seconds after a change, Tuttiphon writes the playlists and has Navidrome scan briefly. Off = via the “Apply” button.')}>
    <Toggle obj={s} key="autoApply" />
  </Row>
</Card>

<Card title={t('Keep it tidy')} icon="sparkles">
  <Row label={t('Seasonal playlists only in season')} hint={t('Christmas, Halloween, summer … are not in Symfonium outside their season and come back on their own in good time. Single playlists can be shown all year in the edit window.')}>
    <Toggle obj={s} key="seasonRest" />
  </Row>
</Card>

<Card title={t('Mixes that learn')} icon="brain">
  <Row label={t('Learn from listening')} hint={t('Songs that get skipped in a mix come up less often for a while. Songs someone rates with 1 star themselves – e.g. in Symfonium – no longer come into their mixes. Takes effect from the next new mix.')}>
    <Toggle obj={s} key="mixLearn" />
  </Row>
  <Row label={t('Smooth transitions in mixes')} hint={t('One song leads into the next: neighboring songs fit in sound, tempo, key and energy. Needs the AI sound analysis. Takes effect from the next new mix.')}>
    <Toggle obj={s} key="smoothTransitions" />
  </Row>
</Card>

<Card title={t('Basic rules for all playlists')} icon="sliders">
  <Row label={t('Max. songs per playlist')} hint={t('Navidrome shuffles this many out of all matching songs on every request.')}>
    <NumInput obj={s} key="limit" min={10} max={5000} step={10} />
  </Row>
  <Row label={t('Minimum length')} hint={t('Shorter tracks such as intros or skits stay out. In seconds.')}>
    <NumInput obj={s} key="minDuration" min={0} max={600} step={10} />
  </Row>
  <Row label={t('Minimum rating for “All”')} hint={t('For playlists across the whole library.')}>
    <Select options={[['0', t('any')], ['1', '★'], ['2', '★★'], ['3', '★★★'], ['4', '★★★★']]} value={s.allMinRating ?? 0}
      onchange={(v) => { s.allMinRating = Number(v); changed() }} />
  </Row>
  <Row label={t('“Only the hits”')} hint={t('The most popular share of a selection, by stars.')}>
    <Select options={[[0.2, t('top {n}%', { n: 20 })], [0.3, t('top {n}%', { n: 30 })], [0.4, t('top {n}%', { n: 40 })], [0.5, t('top {n}%', { n: 50 })]]} value={s.hitsShare ?? 0.3}
      onchange={(v) => { s.hitsShare = Number(v); changed() }} />
  </Row>
  <Row label={t('Name pattern')} hint={t('{welt} is replaced by the music world, {stil} by the vibe.')}>
    <input class="input w-[220px]" value={s.namePattern} onchange={setPattern} />
  </Row>
  <Field label={t('Always exclude tracks, e.g. live recordings or karaoke')}>
    <ChipEditor items={s.excludeTitles} />
  </Field>
</Card>
