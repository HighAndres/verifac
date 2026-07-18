'use client'

import { createContext, useCallback, useContext, useState } from 'react'

type ToastType = 'success' | 'error' | 'info'
interface ToastMsg { id: number; text: string; type: ToastType }

const ToastCtx = createContext<(text: string, type?: ToastType) => void>(() => {})

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastMsg[]>([])
  let next = 0

  const show = useCallback((text: string, type: ToastType = 'success') => {
    const id = ++next
    setToasts(t => [...t, { id, text, type }])
    setTimeout(() => setToasts(t => t.filter(m => m.id !== id)), 3500)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <ToastCtx.Provider value={show}>
      {children}
      <div className="fixed bottom-5 right-5 flex flex-col gap-2 z-50 pointer-events-none">
        {toasts.map(m => (
          <div key={m.id} className={`
            px-4 py-3 rounded-xl shadow-lg text-sm font-medium text-white
            animate-in slide-in-from-right-5 fade-in duration-200
            ${m.type === 'success' ? 'bg-emerald-600' : m.type === 'error' ? 'bg-red-600' : 'bg-slate-700'}
          `}>
            {m.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function useToast() { return useContext(ToastCtx) }
