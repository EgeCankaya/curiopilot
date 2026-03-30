import type { FeedbackItem } from '@/types'
import { submitFeedback } from '@/lib/api'
import { cn } from '@/lib/utils'
import { ExternalLink, ThumbsDown, ThumbsUp, AlertTriangle, Minus } from 'lucide-react'

interface FeedbackControlsProps {
  date: string
  articleNumber: number
  articleUrl: string
  feedback?: FeedbackItem
  onUpdate: (patch: Partial<FeedbackItem>) => void
}

export default function FeedbackControls({
  date,
  articleNumber,
  articleUrl,
  feedback,
  onUpdate,
}: FeedbackControlsProps) {
  const handleRead = (read: boolean) => {
    onUpdate({ read })
    submitFeedback(date, articleNumber, { read }).catch(() => {})
  }

  const handleInterest = (interest: number) => {
    onUpdate({ interest })
    submitFeedback(date, articleNumber, { interest }).catch(() => {})
  }

  const handleQuality = (quality: string) => {
    onUpdate({ quality })
    submitFeedback(date, articleNumber, { quality }).catch(() => {})
  }

  return (
    <div className="mt-6 space-y-4 rounded-2xl border border-border bg-bg-elevated p-5 shadow-md shadow-border-subtle/30">
      <h4 className="text-xs font-semibold uppercase tracking-wider text-text-muted">
        Your Feedback
      </h4>

      {/* Read toggle */}
      <div className="flex items-center gap-3">
        <span className="w-16 text-sm text-text-muted">Read:</span>
        <div className="flex gap-1.5">
          <button
            onClick={() => handleRead(true)}
            className={cn(
              'rounded-xl px-3 py-1 text-sm transition-all duration-200',
              feedback?.read === true
                ? 'bg-success/20 text-success'
                : 'bg-bg-tertiary text-text-muted hover:text-text-primary',
            )}
          >
            Yes
          </button>
          <button
            onClick={() => handleRead(false)}
            className={cn(
              'rounded-xl px-3 py-1 text-sm transition-all duration-200',
              feedback?.read === false
                ? 'bg-danger/20 text-danger'
                : 'bg-bg-tertiary text-text-muted hover:text-text-primary',
            )}
          >
            No
          </button>
        </div>
      </div>

      {/* Interest 1-5 */}
      <div className="flex items-center gap-3">
        <span className="w-16 text-sm text-text-muted">Interest:</span>
        <div className="flex gap-1.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              onClick={() => handleInterest(n)}
              className={cn(
                'h-8 w-8 rounded-xl text-sm font-medium transition-all duration-200',
                feedback?.interest === n
                  ? 'bg-accent text-white'
                  : 'bg-bg-tertiary text-text-muted hover:text-text-primary',
              )}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      {/* Quality */}
      <div className="flex items-center gap-3">
        <span className="w-16 text-sm text-text-muted">Quality:</span>
        <div className="flex gap-1.5">
          <button
            onClick={() => handleQuality('like')}
            className={cn(
              'flex items-center gap-1 rounded-xl px-3 py-1 text-sm transition-all duration-200',
              feedback?.quality === 'like'
                ? 'bg-success/20 text-success'
                : 'bg-bg-tertiary text-text-muted hover:text-text-primary',
            )}
          >
            <ThumbsUp className="h-3.5 w-3.5" />
            Like
          </button>
          <button
            onClick={() => handleQuality('meh')}
            className={cn(
              'flex items-center gap-1 rounded-xl px-3 py-1 text-sm transition-all duration-200',
              feedback?.quality === 'meh'
                ? 'bg-text-muted/20 text-text-secondary'
                : 'bg-bg-tertiary text-text-muted hover:text-text-primary',
            )}
          >
            <Minus className="h-3.5 w-3.5" />
            Meh
          </button>
          <button
            onClick={() => handleQuality('dislike')}
            className={cn(
              'flex items-center gap-1 rounded-xl px-3 py-1 text-sm transition-all duration-200',
              feedback?.quality === 'dislike'
                ? 'bg-danger/20 text-danger'
                : 'bg-bg-tertiary text-text-muted hover:text-text-primary',
            )}
          >
            <ThumbsDown className="h-3.5 w-3.5" />
            Dislike
          </button>
          <button
            onClick={() => handleQuality('broken')}
            className={cn(
              'flex items-center gap-1 rounded-xl px-3 py-1 text-sm transition-all duration-200',
              feedback?.quality === 'broken'
                ? 'bg-warning/20 text-warning'
                : 'bg-bg-tertiary text-text-muted hover:text-text-primary',
            )}
          >
            <AlertTriangle className="h-3.5 w-3.5" />
            Broken
          </button>
        </div>
      </div>

      {/* Read Original */}
      <div className="border-t border-border pt-3">
        <a
          href={articleUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-accent transition-all duration-200 hover:text-accent-hover"
        >
          <ExternalLink className="h-4 w-4" />
          Read Original Article
        </a>
      </div>
    </div>
  )
}
