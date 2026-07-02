import { cn } from '@/lib/utils'

/** Calm shimmer placeholder — premium loading without layout shift (UX §6).
 * Uses opacity pulse only (GPU) and is inert for reduced-motion via the media query. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-raised', className)} />
}
