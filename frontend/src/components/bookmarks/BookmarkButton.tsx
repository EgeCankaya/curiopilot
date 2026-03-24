import { Star } from 'lucide-react'
import { cn } from '@/lib/utils'

interface BookmarkButtonProps {
  bookmarked: boolean
  onToggle: () => void
  className?: string
}

export default function BookmarkButton({ bookmarked, onToggle, className }: BookmarkButtonProps) {
  return (
    <button
      onClick={(e) => { e.stopPropagation(); onToggle() }}
      title={bookmarked ? 'Remove bookmark' : 'Add bookmark'}
      className={cn(
        'rounded-lg p-1 transition-all duration-200',
        bookmarked
          ? 'text-warning hover:text-warning/80'
          : 'text-text-muted hover:text-warning',
        className,
      )}
    >
      <Star className={cn('h-4 w-4', bookmarked && 'fill-current')} />
    </button>
  )
}
