import type { ArticleListItem as ArticleListItemType, FeedbackItem } from '@/types'
import ArticleListItem from './ArticleListItem'

interface ArticleListProps {
  articles: ArticleListItemType[]
  selectedArticle: number | null
  onSelectArticle: (articleNumber: number) => void
  feedback: Map<number, FeedbackItem>
  loading?: boolean
}

export default function ArticleList({
  articles,
  selectedArticle,
  onSelectArticle,
  feedback,
  loading,
}: ArticleListProps) {
  if (loading) {
    return <div className="p-3 text-sm text-text-muted">Loading articles…</div>
  }

  if (articles.length === 0) {
    return <div className="p-3 text-sm text-text-muted">Select a briefing date above.</div>
  }

  return (
    <div className="p-1">
      <div className="px-2 py-1.5 text-xs font-medium uppercase tracking-wider text-text-muted">
        Articles ({articles.length})
      </div>
      {articles.map((a) => (
        <ArticleListItem
          key={a.article_number}
          article={a}
          isSelected={selectedArticle === a.article_number}
          feedback={feedback.get(a.article_number)}
          onClick={() => onSelectArticle(a.article_number)}
        />
      ))}
    </div>
  )
}
