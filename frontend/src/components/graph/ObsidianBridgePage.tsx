import { useState } from 'react'
import { useObsidian } from '@/hooks/useObsidian'
import {
  Network, ExternalLink, RefreshCw, Copy, Check,
  Loader2, AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'

const CATEGORY_COLORS: Record<string, string> = {
  'AI Models': '#0A84FF',
  'Agentic Systems': '#30D158',
  'Training & Learning': '#FF9F0A',
  'Architecture & Methods': '#BF5AF2',
  'Applications & Tools': '#FF375F',
  'Hardware & Infrastructure': '#64D2FF',
  'Safety & Alignment': '#FF6961',
  'Research & Benchmarks': '#FFD60A',
  'Uncategorized': '#8E8E93',
}

export default function ObsidianBridgePage() {
  const { status, loading, error, reExport, exporting } = useObsidian()
  const [copied, setCopied] = useState(false)
  const [exportSuccess, setExportSuccess] = useState(false)

  const handleCopyPath = async () => {
    if (!status?.vault_path) return
    await navigator.clipboard.writeText(status.vault_path)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExport = async () => {
    setExportSuccess(false)
    await reExport()
    if (!error) {
      setExportSuccess(true)
      setTimeout(() => setExportSuccess(false), 3000)
    }
  }

  const handleOpenObsidian = () => {
    if (!status?.vault_path) return
    const uri = `obsidian://open?path=${encodeURIComponent(status.vault_path + '/Knowledge Graph.md')}`
    window.open(uri, '_blank')
  }

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-text-muted">
        <Loader2 className="h-5 w-5 animate-spin" /> Loading...
      </div>
    )
  }

  if (error && !status) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-danger">
        <AlertCircle className="h-5 w-5" /> {error}
      </div>
    )
  }

  const totalConcepts = status?.total_concepts ?? 0
  const categories = status?.category_summary ?? {}
  const lastExported = status?.last_exported
    ? new Date(status.last_exported).toLocaleDateString('en-US', {
        year: 'numeric', month: 'long', day: 'numeric',
      })
    : null

  // Sum edges from total connections (not available directly, show concepts + briefings)
  return (
    <div className="flex flex-1 items-start justify-center overflow-y-auto p-6 md:p-10">
      <div className="w-full max-w-2xl space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-accent/10 p-2.5 text-accent">
            <Network className="h-6 w-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-text-primary">Your Knowledge Graph</h1>
            <p className="text-sm text-text-muted">Lives in Obsidian</p>
          </div>
        </div>

        {/* Stats summary */}
        <div className="rounded-2xl bg-bg-elevated p-5 shadow-md shadow-border-subtle/30">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <span className="text-2xl font-bold text-text-primary">{totalConcepts}</span>
            <span className="text-sm text-text-muted">concepts</span>
            <span className="text-text-muted">·</span>
            <span className="text-2xl font-bold text-text-primary">{status?.total_briefings ?? 0}</span>
            <span className="text-sm text-text-muted">briefings exported</span>
          </div>
          {lastExported && (
            <p className="mt-2 text-xs text-text-muted">Last exported: {lastExported}</p>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={handleOpenObsidian}
            disabled={!status?.configured}
            className={cn(
              'flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium shadow transition-colors',
              status?.configured
                ? 'bg-accent text-white hover:bg-accent/90'
                : 'cursor-not-allowed bg-bg-tertiary text-text-muted',
            )}
          >
            <ExternalLink className="h-4 w-4" />
            Open in Obsidian
          </button>
          <button
            type="button"
            onClick={handleExport}
            disabled={exporting || !status?.configured}
            className={cn(
              'flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-medium shadow transition-colors',
              'bg-bg-elevated text-text-primary hover:bg-bg-hover',
              (exporting || !status?.configured) && 'cursor-not-allowed opacity-60',
            )}
          >
            {exporting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {exporting ? 'Exporting...' : 'Re-export Vault'}
          </button>
        </div>

        {/* Export success toast */}
        {exportSuccess && (
          <div className="rounded-xl border border-green-500/20 bg-green-500/10 px-4 py-2.5 text-sm text-green-400">
            Vault exported successfully.
          </div>
        )}

        {/* Error display */}
        {error && (
          <div className="rounded-xl border border-danger/20 bg-danger/10 px-4 py-2.5 text-sm text-danger">
            {error}
          </div>
        )}

        {/* Domain breakdown */}
        {Object.keys(categories).length > 0 && (
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-text-secondary">Domain Breakdown</h2>
            <div className="flex flex-wrap gap-2">
              {Object.entries(categories)
                .sort(([, a], [, b]) => b - a)
                .map(([cat, count]) => (
                  <span
                    key={cat}
                    className="inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium"
                    style={{
                      backgroundColor: (CATEGORY_COLORS[cat] ?? '#8E8E93') + '18',
                      color: CATEGORY_COLORS[cat] ?? '#8E8E93',
                      border: `1px solid ${(CATEGORY_COLORS[cat] ?? '#8E8E93')}30`,
                    }}
                  >
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: CATEGORY_COLORS[cat] ?? '#8E8E93' }}
                    />
                    {cat} {count}
                  </span>
                ))}
            </div>
          </div>
        )}

        {/* Vault path */}
        {status?.vault_path && (
          <div className="space-y-1.5">
            <h2 className="text-sm font-semibold text-text-secondary">Vault Path</h2>
            <div className="flex items-center gap-2 rounded-xl bg-bg-elevated px-4 py-2.5">
              <code className="flex-1 truncate text-xs text-text-muted">{status.vault_path}</code>
              <button
                type="button"
                onClick={handleCopyPath}
                className="shrink-0 text-text-muted transition-colors hover:text-text-primary"
              >
                {copied ? <Check className="h-4 w-4 text-green-400" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
          </div>
        )}

        {!status?.configured && (
          <div className="rounded-xl border border-border bg-bg-elevated px-5 py-4 text-sm text-text-muted">
            No vault path configured. Set <code className="rounded bg-bg-tertiary px-1.5 py-0.5 text-xs">obsidian_vault_path</code> in your <code className="rounded bg-bg-tertiary px-1.5 py-0.5 text-xs">config.yaml</code> paths section to enable Obsidian integration.
          </div>
        )}
      </div>
    </div>
  )
}
