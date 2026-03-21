import type { ReactNode } from 'react'

interface SidebarProps {
  topSlot: ReactNode
  bottomSlot: ReactNode
}

export default function Sidebar({ topSlot, bottomSlot }: SidebarProps) {
  return (
    <aside className="flex w-[300px] shrink-0 flex-col bg-bg-secondary shadow-[1px_0_0_0_rgba(255,255,255,0.05)]">
      <div className="flex-1 overflow-y-auto">
        {topSlot}
      </div>
      <div className="border-t border-white/5 flex-1 overflow-y-auto">
        {bottomSlot}
      </div>
    </aside>
  )
}
