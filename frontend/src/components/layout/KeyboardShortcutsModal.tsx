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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-2xl bg-bg-elevated p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-text-primary">Keyboard Shortcuts</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="space-y-2">
          {shortcuts.map(({ key, description }) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-text-secondary">{description}</span>
              <kbd className="rounded-md bg-bg-primary px-2 py-0.5 font-mono text-xs text-text-muted">
                {key}
              </kbd>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
