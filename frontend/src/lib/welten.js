// Music worlds: create new ones (from the scene catalog or empty).
import { S, findWelt, snapshot, changed, save, loadLibrary } from './state.svelte.js'
import { modal, closeModal, toast } from './overlay.svelte.js'
import { go } from './router.svelte.js'
import { slug } from './format.js'
import { t } from './i18n.svelte.js'
import SceneCatalog from '../pages/welten/SceneCatalog.svelte'

/** "New music world" dialog – creates it and opens it. */
export async function addWelt() {
  const linked = new Set(S.config.welten.map((w) => w.scene))
  const list = (S.library?.scenes || []).filter((s) => !linked.has(s.id)).sort((a, b) => b.present.length - a.present.length)
  let chosen = null
  const res = await modal({
    title: t('New music world'),
    text: t('From the scene catalog: the tool knows the typical bands and adds them automatically – even when new ones arrive later.'),
    component: SceneCatalog,
    props: { list, onpick: (s) => { chosen = s; closeModal('pick') } },
    buttons: [{ label: t('Cancel'), value: 'cancel' }, { label: t('Empty music world'), value: 'empty' }],
  })
  let w
  if (res === 'pick' && chosen) w = { id: chosen.id, name: chosen.name, icon: chosen.icon, scene: chosen.id, autoScene: true }
  else if (res === 'empty') {
    const name = prompt(t('Name of the new music world:'))
    if (!name) return
    w = { id: slug(name), name, icon: 'i:sparkles', scene: null, autoScene: false }
  } else return
  while (findWelt(w.id)) w.id += '-2'
  snapshot()
  S.config.welten.push({ artists: [], albums: [], genres: [], excludeTitles: [], excludeAlbums: [], excludedArtists: [], minRating: 3, minDuration: null, separate: false, ...w })
  changed()
  await save()   // save first, then open – the page asks the server for the new world
  toast(t('{name} created', { name: w.name }), { undo: true })
  setTimeout(() => loadLibrary(true).catch(() => {}), 800)
  go(`#/welt/${w.id}`)
}
