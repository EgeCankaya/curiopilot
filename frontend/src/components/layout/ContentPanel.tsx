import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface ContentPanelProps {
  children: ReactNode
  /** When true, removes padding and max-width so content (e.g. iframe) can fill the panel. */
  flush?: boolean
  className?: string
}

export default function ContentPanel({ children, flush = false, className }: ContentPanelProps) {
  return (
    <main
      className={cn(
        'flex-1',
        flush
          ? 'flex min-h-0 flex-col overflow-hidden'
          : 'overflow-y-auto p-8',
        className,
      )}
    >
      {flush ? (
        children
      ) : (
        <div className="mx-auto max-w-3xl">{children}</div>
      )}
    </main>
  )
}
