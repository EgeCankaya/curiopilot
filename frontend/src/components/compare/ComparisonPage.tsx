import { useState } from 'react'
import { useBriefings } from '@/hooks/useBriefings'
import { useCompare } from '@/hooks/useCompare'
import type { BriefingDetail } from '@/types'
import { cn } from '@/lib/utils'
import { Loader2, ArrowLeftRight } from 'lucide-react'

export default function ComparisonPage() {
  const { briefings } = useBriefings()
  const [dateLeft, setDateLeft] = useState<string | null>(briefings[1]?.briefing_date ?? null)
  const [dateRight, setDateRight] = useState<string | null>(briefings[0]?.briefing_date ?? null)
  const { left, right, diff, loading } = useCompare(dateLeft, dateRight)

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6 md:p-8">
      <div>
        <h2 className="text-2xl font-bold text-text-primary">Compare Briefings</h2>
        <p className="mt-1 text-sm text-text-secondary">See how topics evolved between two briefings</p>
      </div>

      {/* Date pickers */}
      <div className="flex items-center gap-4">
        <select
          value={dateLeft ?? ''}
          onChange={(e) => setDateLeft(e.target.value || null)}
          className="flex-1 rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/40"
        >
          <option value="">Select left briefing...</option>
          {briefings.map((b) => (
            <option key={b.briefing_date} value={b.briefing_date}>
              {b.briefing_date} ({b.article_count} articles)
            </option>
          ))}
        </select>
        <ArrowLeftRight className="h-5 w-5 shrink-0 text-text-muted" />
        <select
          value={dateRight ?? ''}
          onChange={(e) => setDateRight(e.target.value || null)}
          className="flex-1 rounded-xl bg-bg-tertiary px-3 py-2 text-sm text-text-primary focus:outline-none focus:ring-2 focus:ring-accent/40"
        >
          <option value="">Select right briefing...</option>
          {briefings.map((b) => (
            <option key={b.briefing_date} value={b.briefing_date}>
              {b.briefing_date} ({b.article_count} articles)
            </option>
          ))}
        </select>
      </div>

      {loading && (
        <div className="flex items-center justify-center gap-2 py-8 text-text-muted">
          <Loader2 className="h-5 w-5 animate-spin" /> Loading...
        </div>
      )}

      {/* Concept diff */}
      {diff && (
        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wider text-text-muted">
            Concept Evolution
          </h3>
          <div className="grid grid-cols-3 gap-4">
            <ConceptColumn
              title={`Only in ${dateLeft}`}
              concepts={diff.onlyLeft}
              color="bg-danger/10 text-danger"
            />
            <ConceptColumn
              title="Shared"
              concepts={diff.shared}
              color="bg-bg-tertiary text-text-secondary"
            />
            <ConceptColumn
              title={`Only in ${dateRight}`}
              concepts={diff.onlyRight}
              color="bg-success/10 text-success"
            />
          </div>
        </div>
      )}

      {/* Side-by-side articles */}
      {left && right && (
        <div className="grid grid-cols-2 gap-4">
          <BriefingSummary detail={left} label={dateLeft ?? ''} />
          <BriefingSummary detail={right} label={dateRight ?? ''} />
        </div>
      )}
    </div>
  )
}

function ConceptColumn({ title, concepts, color }: { title: string; concepts: string[]; color: string }) {
  return (
    <div className="rounded-2xl bg-bg-elevated p-4">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-text-muted">{title}</h4>
      <div className="flex flex-wrap gap-1.5">
        {concepts.length === 0 && <span className="text-xs text-text-muted">None</span>}
        {concepts.map((c) => (
          <span key={c} className={cn('rounded-full px-2.5 py-0.5 text-xs', color)}>
            {c}
          </span>
        ))}
      </div>
    </div>
  )
}

function BriefingSummary({ detail, label }: { detail: BriefingDetail; label: string }) {
  return (
    <div className="rounded-2xl bg-bg-elevated p-4">
      <h4 className="mb-2 text-sm font-semibold text-text-primary">{label}</h4>
      <p className="mb-3 text-xs text-text-muted">{detail.articles.length} articles</p>
      <div className="space-y-2">
        {detail.articles.map((a) => (
          <div key={a.article_number} className="rounded-xl bg-bg-tertiary p-2.5">
            <p className="line-clamp-1 text-sm font-medium text-text-primary">{a.title}</p>
            <div className="mt-1 flex gap-2 text-xs text-text-muted">
              <span>{a.source_name}</span>
              <span>R:{a.relevance_score}</span>
              <span>N:{Math.round(a.novelty_score * 100)}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
