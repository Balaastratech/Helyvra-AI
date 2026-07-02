import { useEffect, useRef, useState } from 'react'
import { useTimeline } from '@/api/hooks'
import { useUi } from '@/store'
import { statusAt } from '@/lib/time'
import { cn } from '@/lib/utils'

const ROT = [-3, 2, -1.5, 3, -2.5, 1.5, -1, 2.5]

/**
 * Photo-reel reveal: each fact is a flash-lit polaroid. Dragging the Rewind
 * slider fires a camera-flash and the cards "develop"; replaced facts get a
 * REDACTED stamp. Status recomputed client-side (real-time with the slider).
 * ponytail: CSS polaroid (white card) rather than compositing inside
 * polaroid-frame.png's unknown transparent window; pushpin + stamp are real assets.
 */
export function FactReel({ onCardClick }: { onCardClick?: (id: string) => void }) {
  const { patientId, asOf } = useUi()
  const { data } = useTimeline(patientId)
  const [flash, setFlash] = useState(false)
  const first = useRef(true)

  useEffect(() => {
    if (first.current) {
      first.current = false
      return
    }
    setFlash(true)
    const t = setTimeout(() => setFlash(false), 280)
    return () => clearTimeout(t)
  }, [asOf])

  const nodes = data?.nodes ?? []
  if (nodes.length === 0) return null

  return (
    <div className="relative">
      {flash && (
        <img
          src="/theme/flash-burst.png"
          alt=""
          aria-hidden
          className="pointer-events-none absolute inset-0 z-10 h-full w-full object-cover opacity-70 mix-blend-screen"
          style={{ transition: 'opacity 280ms' }}
        />
      )}
      <div key={asOf ?? 'now'} className="flex flex-wrap gap-4 pb-2">
        {nodes.map((n, i) => {
          const replaced = statusAt(n, asOf) === 'replaced'
          const future = statusAt(n, asOf) === 'future'
          return (
            <button
              key={n.id}
              onClick={() => onCardClick?.(n.id)}
              style={{ rotate: `${ROT[i % ROT.length]}deg` }}
              className={cn(
                'relative w-44 shrink-0 rounded-sm bg-[#f4f1ea] p-2 pb-7 text-left shadow-lg ring-1 ring-black/20 transition-transform hover:z-20 hover:scale-105 motion-safe:animate-develop',
                (replaced || future) && 'opacity-70 grayscale',
              )}
            >
              <img
                src="/theme/pushpin.png"
                alt=""
                aria-hidden
                className="absolute -top-3 left-1/2 z-10 h-6 w-6 -translate-x-1/2 drop-shadow"
              />
              <div className="flex h-20 flex-col justify-center rounded-sm bg-white px-2 text-center">
                <p className="text-sm font-semibold leading-tight text-slate-900">{n.label}</p>
              </div>
              <p className="mt-1.5 px-1 text-[10px] text-slate-500">
                {n.valid_from} · {n.source}
              </p>
              {replaced && (
                <img
                  src="/theme/stamp-redacted.png"
                  alt="replaced"
                  className="pointer-events-none absolute inset-x-3 top-5 z-10 motion-safe:animate-stamp"
                />
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
