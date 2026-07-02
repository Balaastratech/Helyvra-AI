import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium border',
  {
    variants: {
      variant: {
        neutral: 'bg-white/5 text-text-muted border-border',
        active: 'bg-active-soft text-active border-active/30',
        stale: 'bg-danger/15 text-danger border-danger/40',
        timeaware: 'bg-active-soft text-active border-active/30',
        nomemory: 'bg-magenta-soft text-magenta border-magenta/30',
        replaced: 'bg-white/5 text-replaced border-white/10',
        gold: 'bg-amber-400/15 text-amber-300 border-amber-400/30',
      },
    },
    defaultVariants: { variant: 'neutral' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}
