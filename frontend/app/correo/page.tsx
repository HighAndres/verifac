'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useToast } from '@/components/Toast'
import { getWatcherStatus, runWatcher, isAuthenticated } from '@/lib/api'

interface Status {
  configurado: boolean
  cuenta: string
  host: string
  carpeta: string
  poll_minutos: number
  auto_activo: boolean
  confirmaciones_activas: boolean
  remitentes_permitidos: string[]
  instrucciones: string | null
}

interface RunResult {
  revisados: number
  omitidos: number
  total_procesadas: number
  total_errores: number
  procesadas: { emisor: string; estado: string; pdf_cotejo: string }[]
  errores: { archivo?: string; error?: string }[]
}

export default function CorreoPage() {
  const router = useRouter()
  const toast = useToast()
  const [status, setStatus] = useState<Status | null>(null)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<RunResult | null>(null)

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    getWatcherStatus().then(setStatus).catch(() => setStatus(null))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleRun() {
    setRunning(true)
    setResult(null)
    try {
      const res = await runWatcher()
      setResult(res)
      toast(
        `${res.total_procesadas} procesadas · ${res.total_errores} con error` +
        (res.omitidos ? ` · ${res.omitidos} omitidas` : ''),
        res.total_errores ? 'info' : 'success'
      )
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al revisar el correo', 'error')
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8 max-w-3xl">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-slate-800">Correo</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Procesa las facturas que llegaron por correo (XML + PDF).
          </p>
        </div>

        {status && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 mb-5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${status.configurado ? 'bg-emerald-500' : 'bg-red-500'}`} />
                <span className="text-sm font-medium text-slate-700">
                  {status.configurado ? 'Correo configurado' : 'Correo no configurado'}
                </span>
              </div>
              <button
                onClick={handleRun}
                disabled={running || !status.configurado}
                className={`bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors`}
              >
                {running ? 'Revisando…' : '↻ Revisar ahora'}
              </button>
            </div>

            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 mt-4 text-sm">
              <div><dt className="text-slate-400">Cuenta</dt><dd className="text-slate-700">{status.cuenta}</dd></div>
              <div><dt className="text-slate-400">Servidor</dt><dd className="text-slate-700">{status.host} · {status.carpeta}</dd></div>
              <div><dt className="text-slate-400">Revisión automática</dt><dd className="text-slate-700">{status.auto_activo ? `cada ${status.poll_minutos} min` : 'desactivada'}</dd></div>
              <div><dt className="text-slate-400">Remitentes permitidos</dt><dd className="text-slate-700">{status.remitentes_permitidos.length ? status.remitentes_permitidos.join(', ') : 'todos'}</dd></div>
              <div><dt className="text-slate-400">Confirmación a profesores</dt><dd className="text-slate-700">{status.confirmaciones_activas ? 'activa (solo facturas aprobadas)' : 'desactivada'}</dd></div>
            </dl>

            {status.instrucciones && (
              <p className="mt-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                {status.instrucciones}
              </p>
            )}
          </div>
        )}

        {result && (
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-3">Resultado de la última revisión</h3>
            <div className="flex gap-4 text-sm mb-4">
              <span className="text-slate-600">Revisados: <b>{result.revisados}</b></span>
              <span className="text-emerald-700">Procesadas: <b>{result.total_procesadas}</b></span>
              <span className="text-red-600">Errores: <b>{result.total_errores}</b></span>
              {result.omitidos > 0 && <span className="text-slate-500">Omitidas: <b>{result.omitidos}</b></span>}
            </div>

            {result.procesadas.length > 0 && (
              <ul className="space-y-1 text-sm">
                {result.procesadas.map((p, i) => (
                  <li key={i} className="flex items-center justify-between border-b border-slate-100 py-1.5">
                    <span className="text-slate-700">{p.emisor}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${p.estado === 'aprobada' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                      {p.estado}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            {result.errores.length > 0 && (
              <ul className="mt-3 space-y-1 text-xs text-red-600">
                {result.errores.map((e, i) => (
                  <li key={i}>• {e.archivo ? `${e.archivo}: ` : ''}{e.error}</li>
                ))}
              </ul>
            )}

            {result.total_procesadas === 0 && result.total_errores === 0 && (
              <p className="text-sm text-slate-500">No había correos nuevos con facturas.</p>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
