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

interface SegmentProps<T> {
  value: T
  selected: T | null | undefined
  onChange: (v: T) => void
  children: React.ReactNode
  selectedTone?: 'accent' | 'success' | 'danger' | 'warning' | 'muted'
}

function Segment<T extends string | number | boolean>({
  value,
  selected,
  onChange,
  children,
  selectedTone = 'accent',
}: SegmentProps<T>) {
  const isOn = selected === value
  const tone = {
    accent: 'bg-accent text-white',
    success: 'bg-success/20 text-success',
    danger: 'bg-danger/20 text-danger',
    warning: 'bg-warning/20 text-warning',
    muted: 'bg-bg-hover text-text-primary',
  }[selectedTone]

  return (
    <button
      type="button"
      onClick={() => onChange(value)}
      className={cn(
        'flex flex-1 items-center justify-center gap-1 rounded-md px-2.5 py-1 text-sm transition-colors duration-150',
        isOn ? tone : 'text-text-muted hover:text-text-primary',
      )}
    >
      {children}
    </button>
  )
}

function SegmentedGroup({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-0.5 rounded-lg border border-border-subtle/60 bg-bg-tertiary p-0.5">
      {children}
    </div>
  )
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
    <div className="mt-6 space-y-4 rounded-2xl border border-border-subtle/60 bg-bg-card p-5">
      <h4 className="text-[13px] font-medium text-text-secondary">
        Your feedback
      </h4>

      {/* Read */}
      <div className="flex items-center gap-3">
        <span className="w-16 shrink-0 text-sm text-text-muted">Read</span>
        <SegmentedGroup>
          <Segment value={true} selected={feedback?.read} onChange={handleRead} selectedTone="success">
            Yes
          </Segment>
          <Segment value={false} selected={feedback?.read} onChange={handleRead} selectedTone="danger">
            No
          </Segment>
        </SegmentedGroup>
      </div>

      {/* Interest */}
      <div className="flex items-center gap-3">
        <span className="w-16 shrink-0 text-sm text-text-muted">Interest</span>
        <SegmentedGroup>
          {[1, 2, 3, 4, 5].map((n) => (
            <Segment key={n} value={n} selected={feedback?.interest} onChange={handleInterest}>
              <span className="tabular-nums">{n}</span>
            </Segment>
          ))}
        </SegmentedGroup>
      </div>

      {/* Quality */}
      <div className="flex items-center gap-3">
        <span className="w-16 shrink-0 text-sm text-text-muted">Quality</span>
        <SegmentedGroup>
          <Segment value="like" selected={feedback?.quality} onChange={handleQuality} selectedTone="success">
            <ThumbsUp className="h-3.5 w-3.5" />
            <span>Like</span>
          </Segment>
          <Segment value="meh" selected={feedback?.quality} onChange={handleQuality} selectedTone="muted">
            <Minus className="h-3.5 w-3.5" />
            <span>Meh</span>
          </Segment>
          <Segment value="dislike" selected={feedback?.quality} onChange={handleQuality} selectedTone="danger">
            <ThumbsDown className="h-3.5 w-3.5" />
            <span>Dislike</span>
          </Segment>
          <Segment value="broken" selected={feedback?.quality} onChange={handleQuality} selectedTone="warning">
            <AlertTriangle className="h-3.5 w-3.5" />
            <span>Broken</span>
          </Segment>
        </SegmentedGroup>
      </div>

      {/* Read original */}
      <div className="border-t border-separator pt-3">
        <a
          href={articleUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-accent transition-colors duration-150 hover:text-accent-hover"
        >
          <ExternalLink className="h-4 w-4" />
          Read original article
        </a>
      </div>
    </div>
  )
}
