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

function noveltyDot(score: number): string {
  if (score >= 0.7) return 'bg-success'
  if (score >= 0.4) return 'bg-warning'
  return 'bg-text-muted'
}

export default function ArticleListItem({ article, isSelected, feedback, onClick }: ArticleListItemProps) {
  const isRead = feedback?.read === true

  return (
    <button
      onClick={onClick}
      className={cn(
        'flex w-full flex-col gap-1 rounded-lg px-3 py-2 text-left transition-colors duration-150',
        isSelected
          ? 'bg-accent/15 text-text-primary'
          : 'text-text-secondary hover:bg-bg-hover/60 hover:text-text-primary',
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
      <div className="ml-5 flex items-center gap-2 text-xs text-text-muted">
        <span className="truncate">{article.source_name}</span>
        <span className="opacity-40">·</span>
        <span className="tabular-nums">R {article.relevance_score}</span>
        <span className="inline-flex items-center gap-1 tabular-nums">
          <span className={cn('h-1.5 w-1.5 rounded-full', noveltyDot(article.novelty_score))} />
          {Math.round(article.novelty_score * 100)}%
        </span>
        {article.is_deepening && (
          <span className="text-accent">↩ deep</span>
        )}
      </div>
    </button>
  )
}
