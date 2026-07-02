import { useUi } from '@/store'

/**
 * App-wide cinematic overlay (theme §11.2): fixed, pointer-events:none.
 * Film grain (~5%), vignette, and optional thin letterbox bars ("Cinema mode").
 * Static (no jitter) so it stays clean under prefers-reduced-motion.
 */
export function CinematicLayer() {
  const cinema = useUi((s) => s.cinemaMode)
  return (
    <div className="pointer-events-none fixed inset-0 z-30">
      {/* film grain */}
      <div
        className="absolute inset-0 opacity-[0.05] mix-blend-multiply"
        style={{
          backgroundImage: 'url(/theme/grain.png)',
          backgroundSize: '320px',
        }}
      />
      {/* vignette */}
      <div
        className="absolute inset-0"
        style={{
          background:
            'radial-gradient(120% 120% at 50% 50%, transparent 60%, rgba(2,6,23,0.18) 100%)',
        }}
      />
      {/* thin letterbox (cinema mode) */}
      {cinema && (
        <>
          <div className="absolute inset-x-0 top-0 h-8 bg-black/90" />
          <div className="absolute inset-x-0 bottom-0 h-8 bg-black/90" />
        </>
      )}
    </div>
  )
}
