import type { ArticleFull } from '@/types'
import ArticleBody from './ArticleBody'
import { ExternalLink, Loader2 } from 'lucide-react'

interface ArticleViewProps {
  article: ArticleFull | null
  loading: boolean
  error: string | null
}

function NoveltyBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  let color = 'text-text-muted bg-bg-tertiary'
  if (score >= 0.7) color = 'text-success bg-success/10'
  else if (score >= 0.4) color = 'text-warning bg-warning/10'
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      {pct}% novel
    </span>
  )
}

export default function ArticleView({ article, loading, error }: ArticleViewProps) {
  if (loading) {
    return (
      <div className="flex items-center gap-2 py-12 text-text-muted">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span>Loading article…</span>
      </div>
    )
  }

  if (error) {
    return <p className="py-12 text-danger">{error}</p>
  }

  if (!article) return null

  const hasBody = article.body_content && article.body_content.trim().length > 0

  return (
    <article className="space-y-6">
      {/* Header */}
      <header className="space-y-3">
        <h2 className="text-2xl font-bold leading-tight text-text-primary">
          {article.title}
        </h2>

        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-lg bg-bg-tertiary px-2 py-0.5 text-text-muted">
            {article.source_name}
          </span>
          <span className="text-text-muted">Relevance: {article.relevance_score}/10</span>
          <NoveltyBadge score={article.novelty_score} />
          {article.is_deepening && (
            <span className="rounded-full bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent">
              ↩ Deepening
            </span>
          )}
          <a
            href={article.url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto flex items-center gap-1 text-accent transition-all duration-200 hover:text-accent-hover"
          >
            <span>Original</span>
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        </div>

        {article.novelty_explanation && (
          <div className="rounded-2xl bg-accent/5 border border-accent/15 p-4 text-sm text-text-secondary">
            <span className="font-medium text-accent">Why it's new to you: </span>
            {article.novelty_explanation}
          </div>
        )}
      </header>

      {/* Body */}
      {hasBody ? (
        <ArticleBody
          content={article.body_content}
          contentType={article.body_content_type}
        />
      ) : (
        <FallbackBody article={article} />
      )}
    </article>
  )
}

function FallbackBody({ article }: { article: ArticleFull }) {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-warning/20 bg-warning/5 p-4">
        <p className="text-sm font-medium text-warning">Full article not available</p>
        <p className="mt-1 text-sm text-text-muted">
          This article was processed before full-text extraction was enabled.
          The AI summary is shown below.
        </p>
        <button
          onClick={() => window.open(article.url, '_blank')}
          className="mt-3 inline-flex items-center gap-1.5 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white transition-all duration-200 hover:bg-accent-hover active:scale-[0.98]"
        >
          <ExternalLink className="h-4 w-4" />
          Read Original
        </button>
      </div>

      <div className="prose prose-invert prose-slate max-w-none text-base leading-[1.7]">
        <p className="text-text-secondary">{article.summary}</p>
      </div>
    </div>
  )
}
