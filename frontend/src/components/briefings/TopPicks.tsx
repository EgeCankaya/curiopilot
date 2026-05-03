import { Sparkles, ChevronRight } from 'lucide-react'
import type { ArticleListItem } from '@/types'

interface TopPicksProps {
  articles: ArticleListItem[]
  onSelectArticle: (articleNumber: number) => void
}

function score(a: ArticleListItem): number {
  return a.relevance_score * 0.6 + a.novelty_score * 0.4
}

export default function TopPicks({ articles, onSelectArticle }: TopPicksProps) {
  if (articles.length === 0) return null
  const picks = [...articles].sort((a, b) => score(b) - score(a)).slice(0, 3)

  return (
    <section>
      <h3 className="mb-2 flex items-center gap-2 text-[13px] font-medium text-text-secondary">
        <Sparkles className="h-3.5 w-3.5 text-text-muted" />
        Top picks
      </h3>
      <div className="overflow-hidden rounded-2xl border border-border-subtle/60 bg-bg-card">
        {picks.map((a, i) => (
          <button
            key={a.article_number}
            type="button"
            onClick={() => onSelectArticle(a.article_number)}
            className={`group flex w-full items-center gap-3 px-4 py-3 text-left transition-colors hover:bg-bg-hover/40 ${
              i > 0 ? 'border-t border-border-subtle/60' : ''
            }`}
          >
            <span className="shrink-0 text-xs font-medium text-text-muted tabular-nums">
              #{a.article_number}
            </span>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium text-text-primary">
                {a.title}
              </div>
              <div className="mt-0.5 flex items-center gap-2 text-xs text-text-muted">
                <span className="truncate">{a.source_name}</span>
                <span className="opacity-40">·</span>
                <span className="tabular-nums">R {a.relevance_score.toFixed(1)}</span>
                <span className="tabular-nums">N {a.novelty_score.toFixed(1)}</span>
              </div>
            </div>
            <ChevronRight className="h-4 w-4 shrink-0 text-text-muted transition-transform group-hover:translate-x-0.5" />
          </button>
        ))}
      </div>
    </section>
  )
}
