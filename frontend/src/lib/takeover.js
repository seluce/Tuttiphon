// Take handmade .nsp playlists over into the tool (playlists page, start page).
import { S, save } from './state.svelte.js'
import { api } from './api.js'
import { modal, toast } from './overlay.svelte.js'
import { t } from './i18n.svelte.js'
import TakeoverChoice from '../components/TakeoverChoice.svelte'

export async function openTakeover(file) {
  let info
  try { info = await api('/api/takeover/preview', { body: { file } }) }
  catch (e) { toast(e.message, { error: true }); return }
  const choice = { mode: 'unveraendert' }
  const res = await modal({
    title: t('Take over “{name}”', { name: info.name }),
    component: TakeoverChoice,
    props: { info, choice },
    buttons: [{ label: t('Cancel'), value: 'cancel' }, { label: t('Take over'), value: 'ok', primary: true }],
  })
  if (res !== 'ok') return
  try {
    await save()
    const r = await api('/api/takeover', { body: { file, mode: choice.mode } })
    S.config = await api('/api/config')
    S.pl = await api('/api/playlists')
    toast(t('“{name}” taken over', { name: info.name }))
    location.hash = `#/playlist/${encodeURIComponent(r.playlist.id)}`
  } catch (e) {
    toast(e.message, { error: true })
  }
}
