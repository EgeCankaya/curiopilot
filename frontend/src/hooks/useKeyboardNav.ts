import { useEffect } from 'react'
import type { ArticleListItem, FeedbackItem } from '@/types'
import { submitFeedback } from '@/lib/api'

interface KeyboardNavOptions {
  articles: ArticleListItem[]
  selectedArticle: number | null
  onSelectArticle: (num: number | null) => void
  selectedDate: string | null
  feedback: Map<number, FeedbackItem>
  onUpdateFeedback: (articleNumber: number, patch: Partial<FeedbackItem>) => void
  onTriggerRun: () => void
}

function isInputFocused(): boolean {
  const el = document.activeElement
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (el as HTMLElement).isContentEditable
}

export function useKeyboardNav({
  articles,
  selectedArticle,
  onSelectArticle,
  selectedDate,
  feedback,
  onUpdateFeedback,
  onTriggerRun,
}: KeyboardNavOptions) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (isInputFocused()) return

      const articleNumbers = articles.map((a) => a.article_number)
      const currentIdx = selectedArticle != null ? articleNumbers.indexOf(selectedArticle) : -1

      switch (e.key) {
        case 'j': {
          // Next article
          if (articleNumbers.length === 0) return
          const nextIdx = currentIdx < articleNumbers.length - 1 ? currentIdx + 1 : 0
          onSelectArticle(articleNumbers[nextIdx])
          break
        }
        case 'k': {
          // Previous article
          if (articleNumbers.length === 0) return
          const prevIdx = currentIdx > 0 ? currentIdx - 1 : articleNumbers.length - 1
          onSelectArticle(articleNumbers[prevIdx])
          break
        }
        case 'r': {
          if (!selectedDate || selectedArticle == null) return
          const fb = feedback.get(selectedArticle)
          const newRead = !(fb?.read === true)
          onUpdateFeedback(selectedArticle, { read: newRead })
          submitFeedback(selectedDate, selectedArticle, { read: newRead }).catch(() => {})
          break
        }
        case '1':
        case '2':
        case '3':
        case '4':
        case '5': {
          if (!selectedDate || selectedArticle == null) return
          const interest = Number(e.key)
          onUpdateFeedback(selectedArticle, { interest })
          submitFeedback(selectedDate, selectedArticle, { interest }).catch(() => {})
          break
        }
        case 'R': {
          if (e.shiftKey) {
            e.preventDefault()
            onTriggerRun()
          }
          break
        }
        case 'Escape':
          onSelectArticle(null)
          break
        default:
          return
      }
    }

    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [articles, selectedArticle, selectedDate, feedback, onSelectArticle, onUpdateFeedback, onTriggerRun])
}
