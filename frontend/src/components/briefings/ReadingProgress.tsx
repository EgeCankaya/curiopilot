import { CheckCircle2 } from 'lucide-react'
import type { FeedbackItem } from '@/types'

interface ReadingProgressProps {
  total: number
  feedback: Map<number, FeedbackItem>
}

export default function ReadingProgress({ total, feedback }: ReadingProgressProps) {
  if (total === 0) return null
  let read = 0
  for (const f of feedback.values()) if (f.read) read++
  const pct = total > 0 ? Math.round((read / total) * 100) : 0

  return (
    <section>
      <h3 className="mb-2 flex items-center gap-2 text-[13px] font-medium text-text-secondary">
        <CheckCircle2 className="h-3.5 w-3.5 text-text-muted" />
        Reading progress
      </h3>
      <div className="rounded-2xl border border-border-subtle/60 bg-bg-card px-4 py-3">
        <div className="flex items-baseline justify-between">
          <span className="text-sm text-text-primary tabular-nums">
            {read} <span className="text-text-muted">of {total} read</span>
          </span>
          <span className="text-xs text-text-muted tabular-nums">{pct}%</span>
        </div>
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-bg-tertiary">
          <div
            className="h-full rounded-full bg-success transition-all duration-500"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </section>
  )
}
