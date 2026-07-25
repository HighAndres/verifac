'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useToast } from '@/components/Toast'
import { getWatcherStatus, runWatcher, enviarConfirmaciones, isAuthenticated } from '@/lib/api'

interface UltimaRevision {
  revisados?: number
  procesadas?: number
  errores?: number
  omitidos?: number
  origen?: string
  timestamp?: string | null
  error?: string
}

interface Status {
  configurado: boolean
  cuenta: string
  host: string
  carpeta: string
  poll_minutos: number
  auto_activo: boolean
  confirmaciones_activas: boolean
  confirmaciones_pendientes: number
  remitentes_permitidos: string[]
  watcher_running: boolean
  ultima_revision: UltimaRevision | null
  instrucciones: string | null
}

const sleep = (ms: number) => new Promise(r => setTimeout(r, ms))

export default function CorreoPage() {
  const router = useRouter()
  const toast = useToast()
  const [status, setStatus] = useState<Status | null>(null)
  const [running, setRunning] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [result, setResult] = useState<UltimaRevision | null>(null)

  function cargarStatus() {
    getWatcherStatus().then((s: Status) => {
      setStatus(s)
      // Si al entrar ya hay una revisión en curso (o la lanzó el poll), reflejarlo.
      if (s.watcher_running) setRunning(true)
    }).catch(() => setStatus(null))
  }

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    cargarStatus()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function handleEnviarConfirmaciones() {
    setEnviando(true)
    try {
      const res = await enviarConfirmaciones()
      toast(
        res.enviadas > 0
          ? `${res.enviadas} confirmación(es) enviada(s)${res.errores ? ` · ${res.errores} con error` : ''}`
          : res.motivo ?? 'No había confirmaciones pendientes',
        res.errores ? 'info' : 'success'
      )
      cargarStatus()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al enviar confirmaciones', 'error')
    } finally {
      setEnviando(false)
    }
  }

  async function handleRun() {
    setRunning(true)
    setResult(null)
    try {
      const res = await runWatcher()   // responde al instante; procesa en 2º plano
      if (res.started === false) {
        toast(res.mensaje ?? 'Ya hay una revisión en curso', 'info')
      } else {
        toast('Revisión iniciada — procesando en segundo plano…', 'info')
      }
      // Consultar el avance hasta que termine (sin colgar la petición).
      const inicio = Date.now()
      // Un ciclo de gracia para que el backend marque running=true.
      await sleep(1500)
      while (Date.now() - inicio < 10 * 60 * 1000) {
        const s: Status = await getWatcherStatus()
        setStatus(s)
        if (!s.watcher_running) {
          const u = s.ultima_revision
          setResult(u)
          if (u && u.error) {
            toast('La revisión terminó con error', 'error')
          } else if (u) {
            toast(
              `${u.procesadas ?? 0} procesadas · ${u.errores ?? 0} con error` +
              (u.omitidos ? ` · ${u.omitidos} omitidas` : ''),
              (u.errores ?? 0) ? 'info' : 'success'
            )
          }
          break
        }
        await sleep(3000)
      }
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
              <div className="flex gap-3">
                <button
                  onClick={handleEnviarConfirmaciones}
                  disabled={enviando || !status.configurado || status.confirmaciones_pendientes === 0}
                  title="Envía ahora los correos de confirmación a los profesores con factura aprobada"
                  className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  {enviando ? 'Enviando…' : `✉ Enviar confirmaciones (${status.confirmaciones_pendientes})`}
                </button>
                <button
                  onClick={handleRun}
                  disabled={running || !status.configurado}
                  title="Procesa en segundo plano; puedes salir de esta pantalla sin interrumpirlo"
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
                >
                  {running ? 'Procesando…' : '↻ Revisar ahora'}
                </button>
              </div>
            </div>

            <dl className="grid grid-cols-2 gap-x-6 gap-y-2 mt-4 text-sm">
              <div><dt className="text-slate-400">Cuenta</dt><dd className="text-slate-700">{status.cuenta}</dd></div>
              <div><dt className="text-slate-400">Servidor</dt><dd className="text-slate-700">{status.host} · {status.carpeta}</dd></div>
              <div><dt className="text-slate-400">Revisión automática</dt><dd className="text-slate-700">{status.auto_activo ? `cada ${status.poll_minutos} min` : 'desactivada'}</dd></div>
              <div><dt className="text-slate-400">Remitentes permitidos</dt><dd className="text-slate-700">{status.remitentes_permitidos.length ? status.remitentes_permitidos.join(', ') : 'todos'}</dd></div>
              <div><dt className="text-slate-400">Confirmación a profesores</dt><dd className="text-slate-700">{status.confirmaciones_activas ? 'automática al aprobar' : 'manual (con el botón)'}{status.confirmaciones_pendientes > 0 ? ` · ${status.confirmaciones_pendientes} pendiente(s)` : ''}</dd></div>
            </dl>

            {status.instrucciones && (
              <p className="mt-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                {status.instrucciones}
              </p>
            )}
          </div>
        )}

        {running && (
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-5 text-sm text-blue-800 flex items-center gap-2">
            <span className="inline-block w-2.5 h-2.5 rounded-full bg-blue-500 animate-pulse" />
            Procesando el correo en segundo plano… puedes salir de esta pantalla, no se interrumpe.
          </div>
        )}

        {result && !running && (
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="text-sm font-semibold text-slate-800 mb-3">Resultado de la última revisión</h3>
            {result.error ? (
              <p className="text-sm text-red-600">La revisión terminó con error. Revisa la configuración del correo.</p>
            ) : (
              <>
                <div className="flex flex-wrap gap-4 text-sm">
                  <span className="text-slate-600">Revisados: <b>{result.revisados ?? 0}</b></span>
                  <span className="text-emerald-700">Procesadas: <b>{result.procesadas ?? 0}</b></span>
                  <span className="text-red-600">Errores: <b>{result.errores ?? 0}</b></span>
                  {(result.omitidos ?? 0) > 0 && <span className="text-slate-500">Omitidas: <b>{result.omitidos}</b></span>}
                </div>
                {(result.procesadas ?? 0) === 0 && (result.errores ?? 0) === 0 ? (
                  <p className="text-sm text-slate-500 mt-3">No había correos nuevos con facturas.</p>
                ) : (
                  <button onClick={() => router.push('/facturas')}
                    className="mt-3 text-sm text-blue-600 hover:underline">
                    Ver facturas →
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
