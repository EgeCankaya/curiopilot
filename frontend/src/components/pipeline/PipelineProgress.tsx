import type { PipelineRunState } from '@/hooks/usePipelineRun'
import { AlertCircle, CheckCircle2, Loader2, X } from 'lucide-react'

interface PipelineProgressProps {
  state: PipelineRunState
  onDismiss: () => void
}

export default function PipelineProgress({ state, onDismiss }: PipelineProgressProps) {
  if (!state.showModal) return null

  const { isRunning, progress, result, error } = state
  const pct = progress && progress.total > 0
    ? Math.round((progress.current / progress.total) * 100)
    : 0

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xl">
      <div className="w-full max-w-md rounded-3xl bg-bg-elevated p-6 shadow-2xl shadow-border-subtle/40">
        {/* Header */}
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-text-primary">
            {isRunning ? 'Pipeline Running' : error ? 'Pipeline Failed' : 'Pipeline Complete'}
          </h3>
          {!isRunning && (
            <button
              onClick={onDismiss}
              className="rounded-xl p-1 text-text-muted transition-all duration-200 hover:bg-bg-hover hover:text-text-primary"
            >
              <X className="h-5 w-5" />
            </button>
          )}
        </div>

        {/* Running state */}
        {isRunning && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-sm text-text-secondary">
              <Loader2 className="h-5 w-5 animate-spin text-accent" />
              <span>{progress ? progress.phaseLabel : 'Starting…'}</span>
            </div>

            {progress && progress.total > 0 && (
              <>
                <div className="h-2 overflow-hidden rounded-full bg-bg-tertiary">
                  <div
                    className="h-full rounded-full bg-accent transition-all duration-300"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <p className="text-center text-xs text-text-muted">
                  {progress.current} / {progress.total} ({pct}%)
                </p>
              </>
            )}
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="space-y-4">
            <div className="flex items-start gap-3 rounded-2xl bg-danger/10 p-4">
              <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger" />
              <p className="text-sm text-danger">{error}</p>
            </div>
            <button
              onClick={onDismiss}
              className="w-full rounded-xl bg-bg-tertiary py-2 text-sm font-medium text-text-primary transition-all duration-200 hover:bg-bg-hover active:scale-[0.98]"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Complete state */}
        {!isRunning && !error && result && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 text-success">
              <CheckCircle2 className="h-5 w-5" />
              <span className="text-sm font-medium">Pipeline completed successfully</span>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-2xl bg-bg-tertiary p-3">
                <div className="text-lg font-bold text-text-primary">{result.articles_scanned}</div>
                <div className="text-xs text-text-muted">Scanned</div>
              </div>
              <div className="rounded-2xl bg-bg-tertiary p-3">
                <div className="text-lg font-bold text-text-primary">{result.articles_briefed}</div>
                <div className="text-xs text-text-muted">Briefed</div>
              </div>
              <div className="rounded-2xl bg-bg-tertiary p-3">
                <div className="text-lg font-bold text-text-primary">{result.duration}s</div>
                <div className="text-xs text-text-muted">Duration</div>
              </div>
            </div>
            <button
              onClick={onDismiss}
              className="w-full rounded-xl bg-accent py-2 text-sm font-medium text-white transition-all duration-200 hover:bg-accent-hover active:scale-[0.98]"
            >
              View Briefing
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
