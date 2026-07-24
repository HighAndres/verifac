'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import StatusBadge from '@/components/StatusBadge'
import { useToast } from '@/components/Toast'
import { getPagos, guardarPago, isAuthenticated } from '@/lib/api'

interface FilaPago {
  profesor_id: string
  nombre: string
  rfc: string
  factura_estado: string | null
  factura_total: number | null
  esperado: number | null
  pagada: boolean
  fecha_pago: string | null
  metodo_pago: string | null
  monto_pagado: number | null
  registrado_por: string | null
}

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
const METODOS = ['Transferencia', 'Cheque', 'Efectivo', 'Otro']
const HOY = new Date()
const ANIO_ACTUAL = HOY.getFullYear()
const ANIOS = Array.from({ length: 5 }, (_, i) => ANIO_ACTUAL - i)

export default function PagosPage() {
  const router = useRouter()
  const toast = useToast()
  const [filas, setFilas] = useState<FilaPago[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [savingId, setSavingId] = useState<string | null>(null)
  const [mes, setMes] = useState(String(HOY.getMonth() + 1))
  const [anio, setAnio] = useState(String(ANIO_ACTUAL))

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    load()
  }, [mes, anio]) // eslint-disable-line react-hooks/exhaustive-deps

  async function load() {
    setLoading(true); setError('')
    try {
      const data = await getPagos(Number(mes), Number(anio))
      setFilas(data.items)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cargar pagos'
      setError(msg); toast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }

  // Actualiza una fila localmente (sin guardar todavía).
  function setFila(id: string, patch: Partial<FilaPago>) {
    setFilas(fs => fs.map(f => f.profesor_id === id ? { ...f, ...patch } : f))
  }

  async function persistir(fila: FilaPago) {
    setSavingId(fila.profesor_id)
    try {
      const guardado = await guardarPago({
        profesor_id: fila.profesor_id,
        mes: Number(mes),
        anio: Number(anio),
        pagada: fila.pagada,
        fecha_pago: fila.pagada ? fila.fecha_pago : null,
        metodo_pago: fila.pagada ? fila.metodo_pago : null,
        monto_pagado: fila.pagada ? fila.monto_pagado : null,
      })
      setFila(fila.profesor_id, {
        pagada: guardado.pagada,
        fecha_pago: guardado.fecha_pago,
        metodo_pago: guardado.metodo_pago,
        monto_pagado: guardado.monto_pagado,
        registrado_por: guardado.registrado_por,
      })
      toast('Pago actualizado', 'success')
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al guardar', 'error')
      load()  // revertir a lo que hay en el servidor
    } finally {
      setSavingId(null)
    }
  }

  // Al marcar el check: si se activa, precarga monto sugerido y fecha de hoy; guarda de inmediato.
  function togglePagada(fila: FilaPago, valor: boolean) {
    const patch: Partial<FilaPago> = { pagada: valor }
    if (valor) {
      if (!fila.fecha_pago) patch.fecha_pago = new Date().toISOString().slice(0, 10)
      if (fila.monto_pagado == null) patch.monto_pagado = fila.factura_total ?? fila.esperado ?? null
      if (!fila.metodo_pago) patch.metodo_pago = 'Transferencia'
    }
    const actualizada = { ...fila, ...patch }
    setFila(fila.profesor_id, patch)
    persistir(actualizada)
  }

  const fmt = (v: number | null) =>
    v != null ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v) : '—'

  const pagados = filas.filter(f => f.pagada).length

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Pagos</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              {pagados} de {filas.length} profesor{filas.length !== 1 ? 'es' : ''} marcado{pagados !== 1 ? 's' : ''} como pagado{pagados !== 1 ? 's' : ''}
            </p>
          </div>
          <div className="flex gap-2">
            <select value={mes} onChange={e => setMes(e.target.value)}
              className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
              {MESES.map((m, i) => <option key={i + 1} value={String(i + 1)}>{m}</option>)}
            </select>
            <select value={anio} onChange={e => setAnio(e.target.value)}
              className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
              {ANIOS.map(a => <option key={a} value={String(a)}>{a}</option>)}
            </select>
          </div>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {error} — <button onClick={load} className="underline">Reintentar</button>
          </div>
        )}

        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          {loading ? (
            <p className="text-slate-500 text-sm text-center py-16">Cargando…</p>
          ) : filas.length === 0 ? (
            <p className="text-slate-500 text-sm text-center py-16">No hay profesores activos.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  {['Profesor', 'Factura del mes', 'Esperado', 'Pagada', 'Fecha de pago', 'Método', 'Monto pagado'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filas.map(f => {
                  const guardando = savingId === f.profesor_id
                  return (
                    <tr key={f.profesor_id} className={`hover:bg-slate-50 transition-colors ${guardando ? 'opacity-60' : ''}`}>
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-700">{f.nombre}</div>
                        <div className="font-mono text-xs text-slate-400">{f.rfc}</div>
                      </td>
                      <td className="px-4 py-3">
                        {f.factura_estado
                          ? <div className="flex items-center gap-2"><StatusBadge estado={f.factura_estado} /><span className="text-xs text-slate-500 tabular-nums">{fmt(f.factura_total)}</span></div>
                          : <span className="text-xs text-slate-400">Sin factura</span>}
                      </td>
                      <td className="px-4 py-3 text-slate-500 tabular-nums text-xs">{fmt(f.esperado)}</td>
                      <td className="px-4 py-3">
                        <input type="checkbox" checked={f.pagada} disabled={guardando}
                          onChange={e => togglePagada(f, e.target.checked)}
                          className="h-4 w-4 rounded text-blue-600 border-slate-300 focus:ring-blue-500" />
                      </td>
                      <td className="px-4 py-3">
                        <input type="date" value={f.fecha_pago ?? ''} disabled={!f.pagada || guardando}
                          onChange={e => setFila(f.profesor_id, { fecha_pago: e.target.value || null })}
                          onBlur={() => f.pagada && persistir(f)}
                          className="border border-slate-200 rounded-lg px-2 py-1 text-xs bg-white disabled:bg-slate-50 disabled:text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </td>
                      <td className="px-4 py-3">
                        <select value={f.metodo_pago ?? ''} disabled={!f.pagada || guardando}
                          onChange={e => { setFila(f.profesor_id, { metodo_pago: e.target.value || null }); persistir({ ...f, metodo_pago: e.target.value || null }) }}
                          className="border border-slate-200 rounded-lg px-2 py-1 text-xs bg-white disabled:bg-slate-50 disabled:text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500">
                          <option value="">—</option>
                          {METODOS.map(m => <option key={m} value={m}>{m}</option>)}
                        </select>
                      </td>
                      <td className="px-4 py-3">
                        <input type="number" step="0.01" value={f.monto_pagado ?? ''} disabled={!f.pagada || guardando}
                          onChange={e => setFila(f.profesor_id, { monto_pagado: e.target.value === '' ? null : Number(e.target.value) })}
                          onBlur={() => f.pagada && persistir(f)}
                          className="w-28 border border-slate-200 rounded-lg px-2 py-1 text-xs bg-white tabular-nums disabled:bg-slate-50 disabled:text-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  )
}
