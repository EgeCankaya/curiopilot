import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface SidebarProps {
  topSlot: ReactNode
  bottomSlot: ReactNode
  open?: boolean
  isMobile?: boolean
  onClose?: () => void
}

export default function Sidebar({ topSlot, bottomSlot, open = true, isMobile = false, onClose }: SidebarProps) {
  if (isMobile) {
    return (
      <>
        {/* Overlay */}
        {open && (
          <div
            className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            onClick={onClose}
          />
        )}
        {/* Drawer */}
        <aside
          className={cn(
            'fixed inset-y-0 left-0 z-50 flex w-[300px] flex-col bg-bg-secondary shadow-lg transition-transform duration-300',
            open ? 'translate-x-0' : '-translate-x-full',
          )}
          style={{ top: '3.5rem' }}
        >
          <div className="flex-1 overflow-y-auto">
            {topSlot}
          </div>
          <div className="border-t border-border-subtle flex-1 overflow-y-auto">
            {bottomSlot}
          </div>
        </aside>
      </>
    )
  }

  return (
    <aside className="flex w-[300px] shrink-0 flex-col bg-bg-secondary shadow-[1px_0_0_0] shadow-border-subtle">
      <div className="flex-1 overflow-y-auto">
        {topSlot}
      </div>
      <div className="border-t border-border-subtle flex-1 overflow-y-auto">
        {bottomSlot}
      </div>
    </aside>
  )
}
