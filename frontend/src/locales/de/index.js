// German translations: every file in this folder is a dictionary { 'English text': 'German text' }, one per area of
// the interface. They are merged here; tools/i18n-check.mjs reports missing, unused and conflicting entries.
const parts = import.meta.glob(['./*.js', '!./index.js'], { eager: true, import: 'default' })

export default Object.assign({}, ...Object.keys(parts).sort().map((k) => parts[k]))
