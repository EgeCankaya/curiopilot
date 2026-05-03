import { X } from 'lucide-react'

interface Props {
  open: boolean
  onClose: () => void
}

const shortcuts = [
  { key: 'j', description: 'Next article' },
  { key: 'k', description: 'Previous article' },
  { key: 'r', description: 'Toggle read status' },
  { key: '1-5', description: 'Set interest rating' },
  { key: 'Shift+R', description: 'Trigger pipeline run' },
  { key: 'Esc', description: 'Deselect article' },
  { key: '?', description: 'Show keyboard shortcuts' },
]

export default function KeyboardShortcutsModal({ open, onClose }: Props) {
  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-xl" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-2xl border border-border-subtle/60 bg-bg-glass p-6 shadow-lg backdrop-blur-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold tracking-tight text-text-primary">Keyboard shortcuts</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-text-muted transition-colors duration-150 hover:bg-bg-hover hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="divide-y divide-separator">
          {shortcuts.map(({ key, description }) => (
            <div key={key} className="flex items-center justify-between py-2 text-sm">
              <span className="text-text-secondary">{description}</span>
              <kbd className="rounded-md border border-border-subtle/80 bg-bg-card px-2 py-0.5 font-mono text-[11px] text-text-secondary shadow-[inset_0_-1px_0_0_var(--color-separator)]">
                {key}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
