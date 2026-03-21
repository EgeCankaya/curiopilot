import type { ReactNode } from 'react'

interface ContentPanelProps {
  children: ReactNode
}

export default function ContentPanel({ children }: ContentPanelProps) {
  return (
    <main className="flex-1 overflow-y-auto p-8">
      <div className="mx-auto max-w-3xl">
        {children}
      </div>
    </main>
  )
}
