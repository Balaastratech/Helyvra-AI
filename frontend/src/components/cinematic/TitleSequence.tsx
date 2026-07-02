import { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Power, SkipForward } from 'lucide-react'

/**
 * Cold-open title sequence (theme §11.1). ~6s, skippable, plays once per session.
 * Beats: letterbox in -> studio card -> neon logo flicker -> taglines ->
 * [Wake it up] -> record-scratch + light-leak wipe + lights-on -> dashboard.
 */
export function TitleSequence({ onComplete }: { onComplete: () => void }) {
  const [waking, setWaking] = useState(false)
  const reduced = useReducedMotion()

  function wake() {
    if (reduced) {
      onComplete()
      return
    }
    setWaking(true)
    setTimeout(onComplete, 850) // matches .animate-lights-on (800ms)
  }

  return (
    <motion.div
      className="fixed inset-0 z-[100] flex flex-col items-center justify-center overflow-hidden bg-noir-bg bg-cover bg-center"
      style={{ backgroundImage: 'url(/theme/coldopen-bg.png)' }}
      initial={{ opacity: 1 }}
      exit={{ opacity: 0 }}
    >
      {/* letterbox bars slide in to ~2.39:1 */}
      <motion.div
        className="absolute inset-x-0 top-0 bg-black"
        initial={reduced ? false : { height: 0 }}
        animate={{ height: '12vh' }}
        transition={{ duration: reduced ? 0 : 0.3 }}
      />
      <motion.div
        className="absolute inset-x-0 bottom-0 bg-black"
        initial={reduced ? false : { height: 0 }}
        animate={{ height: '12vh' }}
        transition={{ duration: reduced ? 0 : 0.3 }}
      />

      {/* skip */}
      <button
        onClick={onComplete}
        className="absolute right-4 top-[14vh] z-10 flex items-center gap-1 rounded-full border border-white/20 px-3 py-1 text-xs text-noir-muted hover:text-noir-text"
      >
        <SkipForward className="h-3 w-3" /> Skip intro
      </button>

      <div className="relative flex flex-col items-center gap-5 px-6 text-center">
        {/* studio card */}
        <motion.p
          className="text-xs uppercase tracking-[0.3em] text-noir-muted"
          initial={reduced ? false : { opacity: 0 }}
          animate={reduced ? { opacity: 1 } : { opacity: [0, 1, 1, 0] }}
          transition={reduced ? { duration: 0 } : { duration: 1.6, delay: 0.8, times: [0, 0.2, 0.8, 1] }}
        >
          A WeMakeDevs × Cognee Production
        </motion.p>

        {/* neon logo */}
        <motion.img
          src="/theme/logo-neon.png"
          alt="Total Recall"
          className="w-[min(70vw,560px)] motion-safe:animate-flicker"
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reduced ? 0 : 0.4, delay: reduced ? 0 : 2.0 }}
        />

        <motion.p
          className="font-display text-3xl tracking-wide text-noir-text md:text-4xl"
          initial={reduced ? false : { opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduced ? 0 : 0.5, delay: reduced ? 0 : 3.4 }}
        >
          Your AI woke up with no memory of last night.
        </motion.p>
        <motion.p
          className="font-display text-xl text-neon-cyan md:text-2xl"
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: reduced ? 0 : 0.5, delay: reduced ? 0 : 4.4 }}
        >
          It still thinks the patient is allergic to penicillin.
        </motion.p>

        <motion.button
          onClick={wake}
          initial={reduced ? false : { opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: reduced ? 0 : 0.4, delay: reduced ? 0 : 4.9 }}
          className="mt-2 inline-flex items-center gap-2 rounded-xl bg-neon-magenta px-6 py-3 text-base font-semibold text-white shadow-[0_0_24px_rgba(255,45,149,0.6)] transition-transform hover:scale-105"
        >
          <Power className="h-5 w-5" /> Wake it up
        </motion.button>
      </div>

      {/* light-leak sweep + lights-on whiteout on wake */}
      <AnimatePresence>
        {waking && (
          <>
            <motion.img
              src="/theme/lightleak-1.png"
              alt=""
              aria-hidden
              className="pointer-events-none absolute inset-0 h-full w-full object-cover mix-blend-screen"
              initial={{ opacity: 0, x: '-30%' }}
              animate={{ opacity: [0, 1, 0], x: '30%' }}
              transition={{ duration: 0.7 }}
            />
            <div className="pointer-events-none absolute inset-0 animate-lights-on bg-white" />
          </>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
