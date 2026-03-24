import { useStats } from '@/hooks/useStats'
import { useBriefings } from '@/hooks/useBriefings'
import {
  Globe, Filter, Database, Network, Link2, Hash, BarChart3, Loader2, AlertCircle, TrendingUp,
} from 'lucide-react'

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: string | number }) {
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

export default function StatsDashboard() {
  const { stats, loading, error } = useStats()
  const { briefings } = useBriefings()

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-text-muted">
        <Loader2 className="h-5 w-5 animate-spin" />
        Loading stats...
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center gap-2 py-20 text-danger">
        <AlertCircle className="h-5 w-5" />
        {error}
      </div>
    )
  }

  if (!stats) return null

  // Compute articles-per-date from briefings for a simple chart
  const chartData = briefings.slice(0, 30).reverse()
  const maxArticles = Math.max(1, ...chartData.map((b) => b.article_count))

  return (
    <div className="mx-auto max-w-4xl space-y-8 p-6 md:p-8">
      <div>
        <h2 className="text-2xl font-bold text-text-primary">System Statistics</h2>
        <p className="mt-1 text-sm text-text-secondary">
          Overview of your CurioPilot knowledge base
        </p>
      </div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
        <StatCard
          icon={<Globe className="h-5 w-5" />}
          label="URLs visited"
          value={stats.urls_visited.toLocaleString()}
        />
        <StatCard
          icon={<Filter className="h-5 w-5" />}
          label="Passed relevance"
          value={stats.urls_passed_relevance.toLocaleString()}
        />
        <StatCard
          icon={<Hash className="h-5 w-5" />}
          label="Sources seen"
          value={stats.sources_seen}
        />
        <StatCard
          icon={<Database className="h-5 w-5" />}
          label="Article embeddings"
          value={stats.article_embeddings.toLocaleString()}
        />
        <StatCard
          icon={<Network className="h-5 w-5" />}
          label="Graph nodes"
          value={stats.graph_nodes.toLocaleString()}
        />
        <StatCard
          icon={<Link2 className="h-5 w-5" />}
          label="Graph edges"
          value={stats.graph_edges.toLocaleString()}
        />
        {stats.most_connected_topic && (
          <StatCard
            icon={<TrendingUp className="h-5 w-5" />}
            label={`Most connected (${stats.most_connected_edges} edges)`}
            value={stats.most_connected_topic}
          />
        )}
        <StatCard
          icon={<BarChart3 className="h-5 w-5" />}
          label="Total briefings"
          value={briefings.length}
        />
      </div>

      {/* Articles per briefing chart */}
      {chartData.length > 1 && (
        <section>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-text-muted">
            Articles per Briefing (last {chartData.length})
          </h3>
          <div className="rounded-2xl bg-bg-elevated p-4 shadow-md shadow-border-subtle/30">
            <div className="flex items-end gap-1" style={{ height: '120px' }}>
              {chartData.map((b) => {
                const pct = (b.article_count / maxArticles) * 100
                return (
                  <div
                    key={b.briefing_date}
                    className="group relative flex-1"
                    style={{ height: '100%' }}
                  >
                    <div
                      className="absolute bottom-0 w-full rounded-t bg-accent/60 transition-colors group-hover:bg-accent"
                      style={{ height: `${Math.max(pct, 2)}%` }}
                    />
                    <div className="pointer-events-none absolute -top-7 left-1/2 hidden -translate-x-1/2 whitespace-nowrap rounded bg-bg-tertiary px-2 py-0.5 text-xs text-text-secondary group-hover:block">
                      {b.briefing_date}: {b.article_count}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
