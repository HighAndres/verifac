'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { usePathname } from 'next/navigation'
import { isAuthenticated, logout } from '@/lib/api'

// Tiempos configurables:
const IDLE_MS = 15 * 60 * 1000   // inactividad antes de mostrar el aviso (15 min)
const AVISO_S = 60               // segundos de cuenta regresiva para responder

export default function IdleTimeout() {
  const pathname = usePathname()
  const [aviso, setAviso] = useState(false)
  const [segs, setSegs] = useState(AVISO_S)

  const idleRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const tickRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const avisoRef = useRef(false)
  avisoRef.current = aviso

  const limpiarTick = () => {
    if (tickRef.current) { clearInterval(tickRef.current); tickRef.current = null }
  }

  const iniciarAviso = useCallback(() => {
    setAviso(true)
    setSegs(AVISO_S)
    limpiarTick()
    tickRef.current = setInterval(() => {
      setSegs(s => {
        if (s <= 1) { limpiarTick(); logout(); return 0 }
        return s - 1
      })
    }, 1000)
  }, [])

  const reiniciarInactividad = useCallback(() => {
    if (idleRef.current) clearTimeout(idleRef.current)
    idleRef.current = setTimeout(iniciarAviso, IDLE_MS)
  }, [iniciarAviso])

  const seguirConectado = () => {
    limpiarTick()
    setAviso(false)
    reiniciarInactividad()
  }

  useEffect(() => {
    // No corre en el login ni sin sesión activa.
    if (pathname === '/login' || !isAuthenticated()) return

    // Mientras el aviso está visible, la actividad NO lo reinicia:
    // el usuario debe confirmar explícitamente que sigue ahí.
    const onActivity = () => { if (!avisoRef.current) reiniciarInactividad() }
    const eventos: (keyof WindowEventMap)[] =
      ['mousemove', 'mousedown', 'keydown', 'scroll', 'touchstart']
    eventos.forEach(e => window.addEventListener(e, onActivity, { passive: true }))
    reiniciarInactividad()

    return () => {
      eventos.forEach(e => window.removeEventListener(e, onActivity))
      if (idleRef.current) clearTimeout(idleRef.current)
      limpiarTick()
      // Al cambiar de ruta (hubo navegación = el usuario está presente) se descarta
      // cualquier aviso en curso para no dejar el countdown congelado.
      setAviso(false)
    }
  }, [pathname, reiniciarInactividad])

  if (!aviso) return null

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/70 backdrop-blur-sm px-4">
      <div className="bg-white rounded-2xl shadow-xl p-7 w-full max-w-sm text-center">
        <div className="w-12 h-12 rounded-full bg-amber-100 flex items-center justify-center mx-auto">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#d97706"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <path d="M12 6v6l4 2" />
          </svg>
        </div>
        <h2 className="text-lg font-semibold text-slate-800 mt-4">¿Sigues ahí?</h2>
        <p className="text-sm text-slate-500 mt-1">
          Tu sesión se cerrará por inactividad en{' '}
          <span className="font-semibold text-slate-800 tabular-nums">{segs}s</span>.
        </p>
        <div className="flex gap-3 mt-6">
          <button
            onClick={() => logout()}
            className="flex-1 border border-slate-200 text-slate-600 hover:bg-slate-50 text-sm font-medium py-2.5 rounded-lg transition-colors"
          >
            Cerrar sesión
          </button>
          <button
            onClick={seguirConectado}
            autoFocus
            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium py-2.5 rounded-lg transition-colors"
          >
            Seguir conectado
          </button>
        </div>
      </div>
    </div>
  )
}
