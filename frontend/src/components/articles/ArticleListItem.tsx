import { cn } from '@/lib/utils'
import type { ArticleListItem as ArticleListItemType } from '@/types'
import type { FeedbackItem } from '@/types'
import { BookOpen, Eye } from 'lucide-react'

interface ArticleListItemProps {
  article: ArticleListItemType
  isSelected: boolean
  feedback?: FeedbackItem
  onClick: () => void
}

function noveltyColor(score: number): string {
  if (score >= 0.7) return 'text-success'
  if (score >= 0.4) return 'text-warning'
  return 'text-text-muted'
}

export default function ArticleListItem({ article, isSelected, feedback, onClick }: ArticleListItemProps) {
  const isRead = feedback?.read === true

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex w-full flex-col gap-1 rounded-xl px-3 py-2.5 text-left transition-all duration-200',
        isSelected
          ? 'bg-bg-active text-text-primary'
          : 'text-text-secondary hover:bg-bg-hover hover:text-text-primary',
      )}
    >
      <div className="flex items-start gap-2">
        <div className="mt-0.5 shrink-0">
          {isRead
            ? <Eye className="h-3.5 w-3.5 text-text-muted" />
            : <BookOpen className="h-3.5 w-3.5 text-accent" />
          }
        </div>
        <span className="line-clamp-2 text-sm font-medium leading-tight">
          {article.title}
        </span>
      </div>
      <div className="ml-5 flex items-center gap-2 text-xs">
        <span className="rounded-lg bg-bg-tertiary px-1.5 py-0.5 text-text-muted">
          {article.source_name}
        </span>
        <span className="text-text-muted">R:{article.relevance_score}</span>
        <span className={noveltyColor(article.novelty_score)}>
          N:{Math.round(article.novelty_score * 100)}%
        </span>
        {article.is_deepening && (
          <span className="text-accent">↩ deep</span>
        )}
      </div>
    </button>
  )
}
