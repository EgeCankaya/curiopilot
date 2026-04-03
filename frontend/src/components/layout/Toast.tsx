import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { CheckCircle, AlertTriangle, Info, X } from 'lucide-react'
import { cn } from '@/lib/utils'

type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: number
  type: ToastType
  message: string
}

interface ToastContextValue {
  toast: (type: ToastType, message: string) => void
}

const ToastContext = createContext<ToastContextValue>({ toast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const addToast = useCallback((type: ToastType, message: string) => {
    const id = nextId++
    setToasts((prev) => [...prev, { id, type, message }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={{ toast: addToast }}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  )
}

const icons = {
  success: CheckCircle,
  error: AlertTriangle,
  info: Info,
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const Icon = icons[toast.type]

  return (
    <div
      className={cn(
        'pointer-events-auto flex items-center gap-3 rounded-xl px-4 py-3 shadow-lg backdrop-blur-sm',
        'animate-in slide-in-from-right-5 fade-in duration-200',
        toast.type === 'success' && 'bg-emerald-600/90 text-white',
        toast.type === 'error' && 'bg-red-600/90 text-white',
        toast.type === 'info' && 'bg-bg-elevated text-text-primary shadow-md',
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="text-sm">{toast.message}</span>
      <button onClick={onDismiss} className="ml-2 shrink-0 rounded p-0.5 opacity-70 hover:opacity-100">
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  )
}
