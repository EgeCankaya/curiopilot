import { cn } from '@/lib/utils'
import type { BriefingListItem } from '@/types'
import { Calendar, MessageSquare } from 'lucide-react'

interface BriefingListProps {
  briefings: BriefingListItem[]
  selectedDate: string | null
  onSelectDate: (date: string) => void
  loading?: boolean
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function BriefingList({ briefings, selectedDate, onSelectDate, loading }: BriefingListProps) {
  if (loading) {
    return <div className="p-3 text-sm text-text-muted">Loading briefings…</div>
  }

  if (briefings.length === 0) {
    return <div className="p-3 text-sm text-text-muted">No briefings yet.</div>
  }

  return (
    <div className="p-1.5">
      <div className="px-2 py-1.5 text-xs font-medium uppercase tracking-wider text-text-muted">
        Briefings
      </div>
      {briefings.map((b) => (
        <button
          key={b.briefing_date}
          onClick={() => onSelectDate(b.briefing_date)}
          className={cn(
            'flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-left text-sm transition-all duration-200',
            selectedDate === b.briefing_date
              ? 'bg-bg-active text-text-primary'
              : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
          )}
        >
          <div className="flex items-center gap-2">
            <Calendar className="h-3.5 w-3.5 shrink-0" />
            <span>{formatDate(b.briefing_date)}</span>
          </div>
          <div className="flex items-center gap-2">
            {b.has_feedback && (
              <MessageSquare className="h-3 w-3 text-success" />
            )}
            <span className="text-xs text-text-muted">{b.article_count}</span>
          </div>
        </button>
      ))}
    </div>
  )
}
