import { useState } from 'react'
import { useDLQ } from '@/hooks/useDLQ'
import { useToast } from '@/components/layout/Toast'
import { Loader2, Trash2, RefreshCw, AlertTriangle, ExternalLink } from 'lucide-react'
import { cn } from '@/lib/utils'

export default function DLQPanel() {
  const { items, stats, loading, error, refresh, remove, clear } = useDLQ()
  const { toast } = useToast()
  const [removing, setRemoving] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)

  const handleRemove = async (url: string) => {
    setRemoving(url)
    try {
      await remove(url)
      toast('success', 'Removed from DLQ')
    } catch {
      toast('error', 'Failed to remove item')
    } finally {
      setRemoving(null)
    }
  }

  const handleClear = async () => {
    if (!confirm('Clear all DLQ items? This cannot be undone.')) return
    setClearing(true)
    try {
      await clear()
      toast('success', 'DLQ cleared')
    } catch {
      toast('error', 'Failed to clear DLQ')
    } finally {
      setClearing(false)
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6 md:p-8">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-text-primary">Dead Letter Queue</h2>
          <p className="text-sm text-text-muted">
            Articles that failed during pipeline processing
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={refresh}
            disabled={loading}
            className="rounded-xl p-2 text-text-muted transition-all hover:bg-bg-hover hover:text-text-primary disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
          </button>
          {items.length > 0 && (
            <button
              onClick={handleClear}
              disabled={clearing}
              className="flex items-center gap-1.5 rounded-xl bg-red-500/15 px-3 py-1.5 text-sm font-medium text-red-500 transition-all hover:bg-red-500/25 disabled:opacity-50"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Clear All
            </button>
          )}
        </div>
      </div>

      {/* Stats summary */}
      {stats && stats.total > 0 && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard label="Total Failed" value={stats.total} />
          {Object.entries(stats.by_phase).map(([phase, count]) => (
            <StatCard key={phase} label={phase} value={count} />
          ))}
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="rounded-xl bg-red-500/10 px-4 py-3 text-sm text-red-500">
          {error}
        </div>
      )}

      {/* Loading state */}
      {loading && items.length === 0 && (
        <div className="flex items-center justify-center gap-2 py-12 text-text-muted">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>Loading DLQ...</span>
        </div>
      )}

      {/* Empty state */}
      {!loading && items.length === 0 && !error && (
        <div className="flex flex-col items-center gap-2 py-16 text-text-muted">
          <AlertTriangle className="h-8 w-8 opacity-40" />
          <p className="text-sm">No failed articles in the queue</p>
        </div>
      )}

      {/* DLQ items */}
      {items.length > 0 && (
        <div className="space-y-2">
          {items.map((item) => (
            <div
              key={item.url}
              className="flex items-start gap-3 rounded-xl bg-bg-elevated p-4 transition-colors hover:bg-bg-hover"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="truncate text-sm font-medium text-text-primary">
                    {item.title || item.url}
                  </h3>
                  <a
                    href={item.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="shrink-0 text-text-muted hover:text-accent"
                  >
                    <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-text-muted">
                  <span className="rounded-md bg-bg-primary px-1.5 py-0.5 font-mono">
                    {item.phase}
                  </span>
                  <span className="rounded-md bg-red-500/10 px-1.5 py-0.5 text-red-400">
                    {item.error_type}
                  </span>
                  {item.source_name && (
                    <span>{item.source_name}</span>
                  )}
                  <span>Retries: {item.retry_count}</span>
                  <span>{new Date(item.failed_at).toLocaleDateString()}</span>
                </div>
                {item.error_message && (
                  <p className="mt-1 truncate text-xs text-text-muted">
                    {item.error_message}
                  </p>
                )}
              </div>
              <button
                onClick={() => handleRemove(item.url)}
                disabled={removing === item.url}
                className="shrink-0 rounded-lg p-1.5 text-text-muted transition-colors hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
                title="Remove from DLQ"
              >
                {removing === item.url ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="h-4 w-4" />
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl bg-bg-elevated p-3">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-lg font-semibold text-text-primary">{value}</p>
    </div>
  )
}
