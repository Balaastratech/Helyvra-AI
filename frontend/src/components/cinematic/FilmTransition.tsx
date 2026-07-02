import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'

/**
 * Light-leak film wipe (theme §11.3). Plays a 600ms screen-blend sweep whenever
 * `trigger` changes value. `variant` picks the warm/cool leak. Respects
 * prefers-reduced-motion (renders nothing).
 */
export function FilmTransition({
  trigger,
  variant = 'warm',
}: {
  trigger: unknown
  variant?: 'warm' | 'cool'
}) {
  const [show, setShow] = useState(false)
  const first = useRef(true)
  const reduced =
    typeof window !== 'undefined' &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches

  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    if (reduced) return
    setShow(true)
    const t = setTimeout(() => setShow(false), 650)
    return () => clearTimeout(t)
  }, [trigger, reduced])

  const src = variant === 'warm' ? '/theme/lightleak-1.png' : '/theme/lightleak-2.png'

  return (
    <AnimatePresence>
      {show && (
        <motion.img
          src={src}
          alt=""
          aria-hidden
          className="pointer-events-none fixed inset-0 z-[60] h-full w-full object-cover mix-blend-screen"
          initial={{ opacity: 0, x: '-30%' }}
          animate={{ opacity: [0, 0.9, 0], x: '30%' }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.65, ease: 'easeInOut' }}
        />
      )}
    </AnimatePresence>
  )
}
