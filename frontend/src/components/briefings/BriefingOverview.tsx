import { useState } from 'react'
import type { BriefingDetail } from '@/types'
import { BarChart3, BookOpen, Clock, Filter, Lightbulb, Network, Compass, RefreshCw } from 'lucide-react'

interface BriefingOverviewProps {
  detail: BriefingDetail
  onRerun?: (date: string) => void
  isRunning?: boolean
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number | null }) {
  if (value == null) return null
  return (
    <div className="flex items-center gap-3 rounded-2xl bg-bg-elevated p-4 shadow-md shadow-border-subtle/30">
      <div className="text-accent">{icon}</div>
      <div>
        <div className="text-lg font-semibold text-text-primary">{value}</div>
        <div className="text-xs text-text-muted">{label}</div>
      </div>
    </div>
  )
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr + 'T00:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })
}

export default function BriefingOverview({ detail, onRerun, isRunning }: BriefingOverviewProps) {
  const graphStats = detail.graph_stats as Record<string, unknown> | null
  const [confirmOpen, setConfirmOpen] = useState(false)

  const todayStr = new Date().toISOString().slice(0, 10)
  const isToday = detail.briefing_date === todayStr

  const handleRerunClick = () => setConfirmOpen(true)
  const handleConfirm = () => {
    setConfirmOpen(false)
    onRerun?.(detail.briefing_date)
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold text-text-primary">
            {formatDate(detail.briefing_date)}
          </h2>
          <p className="mt-1 text-sm text-text-secondary">
            Daily briefing with {detail.articles.length} articles
          </p>
        </div>
        {isToday && onRerun && (
          <button
            type="button"
            onClick={handleRerunClick}
            disabled={isRunning}
            className="flex shrink-0 items-center gap-1.5 rounded-lg border border-border bg-bg-elevated px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-accent hover:text-accent disabled:opacity-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Re-run
          </button>
        )}
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

      {/* New Concepts */}
      {detail.new_concepts.length > 0 && (
        <section>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-text-muted">
            <Lightbulb className="h-4 w-4 text-warning" />
            New Concepts
          </h3>
          <div className="flex flex-wrap gap-2">
            {detail.new_concepts.map((concept) => (
              <span
                key={concept}
                className="rounded-full bg-warning/10 px-3 py-1 text-sm text-warning"
              >
                {concept}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Graph Stats */}
      {graphStats && (
        <section>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-text-muted">
            <Network className="h-4 w-4 text-accent" />
            Knowledge Graph Update
          </h3>
          <div className="rounded-2xl bg-bg-elevated p-4 text-sm text-text-secondary shadow-md shadow-border-subtle/30">
            {graphStats.nodes_before != null && (
              <p>Nodes: {String(graphStats.nodes_before)} → {String(graphStats.nodes_after)}</p>
            )}
            {graphStats.edges_before != null && (
              <p>Edges: {String(graphStats.edges_before)} → {String(graphStats.edges_after)}</p>
            )}
            {graphStats.new_concepts != null && Array.isArray(graphStats.new_concepts) && (
              <p className="mt-1">New: {(graphStats.new_concepts as string[]).join(', ')}</p>
            )}
          </div>
        </section>
      )}

      {/* Explorations */}
      {detail.explorations.length > 0 && (
        <section>
          <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-text-muted">
            <Compass className="h-4 w-4 text-success" />
            Suggested Explorations
          </h3>
          <ul className="space-y-1.5">
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
