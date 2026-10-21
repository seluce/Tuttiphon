// Draft of the setup assistant: the settings it asks about, copied from S.config.settings when it opens. The steps
// change only the draft; applyDraft() writes it back with “Finish” (nothing is saved before that).

/** Steps of “Update everything” in their fixed order (ids – data). */
export const PIPELINE = ['flac', 'lyrics', 'cover', 'analyse', 'playlists', 'scan', 'deezer']
const PROVIDERS = ['lrclib', 'netease']

/** The draft from the settings – with the values that apply when a key is missing. */
export function draftFrom(st) {
  const op = st.opus || {}, ly = st.lyrics || {}, an = st.analysis || {}, dz = st.deezer || {}, wt = st.watch || {}
  const night = an.night || {}
  const providers = (ly.providers || []).filter((p) => PROVIDERS.includes(p.id)).map((p) => ({ id: p.id, on: !!p.on }))
  for (const id of PROVIDERS) if (!providers.some((p) => p.id === id)) providers.push({ id, on: id === 'lrclib' })
  return {
    opus: {
      enabled: op.enabled ?? true, codec: op.codec === 'aac' ? 'aac' : 'opus', original: op.original || 'archive',
      bitrate: op.bitrate || 160, aacBitrate: op.aacBitrate || 224,   // shown only – changed under Settings → Conversion
    },
    lyrics: {
      fetch: ly.fetch ?? true, savePlain: ly.savePlain ?? true, upgradePlain: ly.upgradePlain ?? true,
      cleanup: ly.cleanup ?? true, providers,
    },
    analysis: {
      enabled: an.enabled ?? true, ml: an.ml ?? true, depth: an.depth || 'standard', fingerprints: an.fingerprints ?? true,
      night: { enabled: night.enabled ?? true, from: night.from || '01:00', to: night.to || '05:00' },
    },
    deezer: {
      on: (Array.isArray(st.pipeline) ? st.pipeline : PIPELINE).includes('deezer'),
      users: Array.isArray(dz.users) ? [...dz.users] : null,   // null = the accounts of all people
      overwriteManual: !!dz.overwriteManual,
    },
    language: st.language || 'en',   // of the server: names in Navidrome, notifications
    dailyMode: st.dailyMode || 'playlists',
    dailyAt: st.dailyAt || '05:30',
    watch: { enabled: !!wt.enabled, interval: wt.interval || 15 },
  }
}

/** Steps of “Update everything” after the draft (Deezer on or off). */
export function pipelineOf(st, d) {
  const pipe = new Set(Array.isArray(st.pipeline) ? st.pipeline : PIPELINE)
  if (d.deezer.on) pipe.add('deezer')
  else pipe.delete('deezer')
  if (!pipe.size) for (const x of ['playlists', 'scan']) pipe.add(x)
  return PIPELINE.filter((x) => pipe.has(x))
}

/** Write the draft (a plain copy) into the settings and mark the assistant as done. before: the draft as it was when
 *  the assistant opened – the nightly Deezer refresh and the folder watch's Deezer step follow the switch only when
 *  it was changed (so a deliberate choice under Settings stays). */
export function applyDraft(st, d, before, day) {
  st.opus ??= {}
  Object.assign(st.opus, { enabled: d.opus.enabled, codec: d.opus.codec, original: d.opus.original })
  st.lyrics ??= {}
  Object.assign(st.lyrics, {
    fetch: d.lyrics.fetch, savePlain: d.lyrics.savePlain, upgradePlain: d.lyrics.upgradePlain, cleanup: d.lyrics.cleanup,
    providers: d.lyrics.providers.map((p) => ({ id: p.id, on: p.on })),
  })
  st.analysis ??= {}
  Object.assign(st.analysis, { enabled: d.analysis.enabled, ml: d.analysis.ml, depth: d.analysis.depth, fingerprints: d.analysis.fingerprints })
  st.analysis.night = { ...(st.analysis.night || {}), ...d.analysis.night }
  st.pipeline = pipelineOf(st, d)
  st.deezer ??= {}
  st.deezer.users = d.deezer.users
  st.deezer.overwriteManual = d.deezer.overwriteManual
  st.watch ??= {}
  if (d.deezer.on !== before.deezer.on) {
    st.deezer.refresh = d.deezer.on
    st.watch.deezer = d.deezer.on
  }
  st.language = d.language
  st.dailyMode = d.dailyMode
  st.dailyAt = d.dailyAt
  st.watch.enabled = d.watch.enabled
  st.watch.interval = d.watch.interval
  st.setup = { done: true, at: day }
}
