// Motion that follows the system setting “reduce motion”: smooth scrolling only if it is not turned on.
const reduced = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches

/** 'smooth' – or 'auto' (jump) if the system asks for less motion. For scrollTo/scrollBy/scrollIntoView. */
export const smooth = () => (reduced() ? 'auto' : 'smooth')
