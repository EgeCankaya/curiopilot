import { useState } from 'react'
import type { BriefingDetail, FeedbackItem } from '@/types'
import { BarChart3, BookOpen, Clock, Filter, Lightbulb, Compass, RefreshCw, Mail, ChevronDown } from 'lucide-react'
import { sendBriefingEmail } from '@/lib/api'
import TopPicks from './TopPicks'
import ReadingProgress from './ReadingProgress'
import SourceBreakdown from './SourceBreakdown'
import TopicDistribution from './TopicDistribution'

interface BriefingOverviewProps {
  detail: BriefingDetail
  onRerun?: (date: string) => void
  isRunning?: boolean
  feedback: Map<number, FeedbackItem>
  onSelectArticle: (articleNumber: number) => void
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number | null }) {
  if (value == null) return null
  return (
    <div className="flex items-center gap-3 rounded-2xl border border-border-subtle/60 bg-bg-card p-4">
      <div className="text-accent">{icon}</div>
      <div>
        <div className="text-lg font-semibold text-text-primary tabular-nums">{value}</div>
        <div className="text-xs text-text-muted">{label}</div>
      </div>
    </div>
  )
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
}

export default function BriefingOverview({ detail, onRerun, isRunning, feedback, onSelectArticle }: BriefingOverviewProps) {
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [emailState, setEmailState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle')
  const [emailDetail, setEmailDetail] = useState('')
  const [conceptsOpen, setConceptsOpen] = useState(false)

  const todayStr = new Date().toISOString().slice(0, 10)
  const isToday = detail.briefing_date === todayStr

  const handleRerunClick = () => setConfirmOpen(true)
  const handleConfirm = () => {
    setConfirmOpen(false)
    onRerun?.(detail.briefing_date)
  }

  const handleSendEmail = async () => {
    setEmailState('sending')
    setEmailDetail('')
    try {
      const res = await sendBriefingEmail(detail.briefing_date)
      setEmailState(res.status === 'sent' ? 'sent' : 'error')
      setEmailDetail(res.detail)
    } catch (err) {
      setEmailState('error')
      setEmailDetail(err instanceof Error ? err.message : String(err))
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-text-primary">
            {formatDate(detail.briefing_date)}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            Daily briefing with {detail.articles.length} articles
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <div className="flex items-center gap-2">
            {isToday && onRerun && (
              <button
                type="button"
                onClick={handleRerunClick}
                disabled={isRunning}
                aria-label="Re-run today's briefing"
                className="flex items-center gap-1.5 rounded-lg border border-border-subtle/60 bg-bg-card px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span className="hidden md:inline">Re-run</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleSendEmail}
              disabled={emailState === 'sending'}
              aria-label="Send briefing email"
              className="flex items-center gap-1.5 rounded-lg border border-border-subtle/60 bg-bg-card px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
            >
              <Mail className="h-3.5 w-3.5" />
              <span className="hidden md:inline">{emailState === 'sending' ? 'Sending…' : 'Send Email'}</span>
            </button>
          </div>
          {emailState !== 'idle' && (
            <p className={`text-xs ${emailState === 'sent' ? 'text-success' : 'text-error'}`}>
              {emailDetail}
            </p>
          )}
        </div>
      </div>

      {/* Confirm dialog */}
      {confirmOpen && (
        <div className="rounded-xl border border-warning/40 bg-warning/5 p-4 text-sm">
          <p className="font-medium text-text-primary">Re-run today's briefing from scratch?</p>
          <p className="mt-1 text-text-secondary">
            This will delete today's articles and re-scrape all sources. The pipeline will run again from the beginning.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={handleConfirm}
              className="rounded-lg bg-warning px-3 py-1.5 text-sm font-medium text-bg-primary transition-opacity hover:opacity-90"
            >
              Yes, re-run
            </button>
            <button
              type="button"
              onClick={() => setConfirmOpen(false)}
              className="rounded-lg border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-text-secondary"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3">
        <StatCard
          icon={<BarChart3 className="h-5 w-5" />}
          label="Articles scanned"
          value={detail.articles_scanned}
        />
        <StatCard
          icon={<Filter className="h-5 w-5" />}
          label="Passed relevance"
          value={detail.articles_relevant}
        />
        <StatCard
          icon={<BookOpen className="h-5 w-5" />}
          label="In briefing"
          value={detail.articles_briefed ?? detail.articles.length}
        />
        <StatCard
          icon={<Clock className="h-5 w-5" />}
          label="Pipeline runtime"
          value={detail.pipeline_runtime}
        />
      </div>

      {/* Top picks */}
      <TopPicks articles={detail.articles} onSelectArticle={onSelectArticle} />

      {/* Reading progress */}
      <ReadingProgress total={detail.articles.length} feedback={feedback} />

      {/* Sources */}
      <SourceBreakdown articles={detail.articles} />

      {/* Topics */}
      <TopicDistribution articles={detail.articles} />

      {/* New Concepts (collapsed by default) */}
      {detail.new_concepts.length > 0 && (
        <section>
          <button
            type="button"
            onClick={() => setConceptsOpen((o) => !o)}
            aria-expanded={conceptsOpen}
            className="flex w-full items-center justify-between rounded-2xl border border-border-subtle/60 bg-bg-card px-4 py-3 text-left transition-colors hover:bg-bg-hover/40"
          >
            <span className="flex items-center gap-2 text-[13px] font-medium text-text-secondary">
              <Lightbulb className="h-3.5 w-3.5 text-text-muted" />
              New concepts
              <span className="rounded-full bg-bg-tertiary px-1.5 py-0.5 text-[10px] font-medium text-text-muted tabular-nums">
                {detail.new_concepts.length}
              </span>
            </span>
            <ChevronDown
              className={`h-4 w-4 text-text-muted transition-transform ${conceptsOpen ? 'rotate-180' : ''}`}
            />
          </button>
          {conceptsOpen && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {detail.new_concepts.map((concept) => (
                <span
                  key={concept}
                  className="rounded-full border border-warning/30 bg-warning/5 px-2.5 py-0.5 text-xs text-warning/90"
                >
                  {concept}
                </span>
              ))}
            </div>
          )}
        </section>
      )}

      {/* Explorations */}
      {detail.explorations.length > 0 && (
        <section>
          <h3 className="mb-2 flex items-center gap-2 text-[13px] font-medium text-text-secondary">
            <Compass className="h-3.5 w-3.5 text-text-muted" />
            Suggested explorations
          </h3>
          <ul className="space-y-1.5 rounded-2xl border border-border-subtle/60 bg-bg-card px-4 py-3">
            {detail.explorations.map((exp, i) => (
              <li
                key={i}
                className="flex items-start gap-2 text-sm text-text-secondary"
              >
                <span className="mt-0.5 text-success">→</span>
                <span>{exp}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}
