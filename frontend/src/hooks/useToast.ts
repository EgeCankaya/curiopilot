import { createContext, useContext } from 'react'

export type ToastType = 'success' | 'error' | 'info'

export interface ToastContextValue {
  toast: (type: ToastType, message: string) => void
}

export const ToastContext = createContext<ToastContextValue>({ toast: () => {} })

export function useToast() {
  return useContext(ToastContext)
}
