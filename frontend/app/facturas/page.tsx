'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '@/components/Sidebar'
import StatusBadge from '@/components/StatusBadge'
import { useToast } from '@/components/Toast'
import { getFacturas, isAuthenticated } from '@/lib/api'

interface Factura {
  id: string
  uuid_cfdi: string
  rfc_emisor: string
  nombre_emisor: string | null
  subtotal: string | null
  total: string | null
  estado: string
  fecha_emision: string | null
  created_at: string
}

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
const ANIO_ACTUAL = new Date().getFullYear()
const ANIOS = Array.from({ length: 5 }, (_, i) => ANIO_ACTUAL - i)

export default function FacturasPage() {
  const router = useRouter()
  const toast = useToast()
  const [facturas, setFacturas] = useState<Factura[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [estado, setEstado] = useState('')
  const [mes, setMes] = useState('')
  const [anio, setAnio] = useState(String(ANIO_ACTUAL))
  const [busqueda, setBusqueda] = useState('')
  const busquedaRef = useRef(busqueda)

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    load()
  }, [estado, mes, anio]) // eslint-disable-line react-hooks/exhaustive-deps

  async function load(q = busquedaRef.current) {
    setLoading(true); setError('')
    try {
      const params: Record<string, string> = { limit: '100' }
      if (estado) params.estado = estado
      if (mes)    params.mes = mes
      if (anio)   params.anio = anio
      if (q)      params.q = q
      const data = await getFacturas(params)
      setFacturas(data.items)
      setTotal(data.total)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cargar facturas'
      setError(msg)
      toast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }

  function handleBusqueda(e: React.FormEvent) {
    e.preventDefault()
    busquedaRef.current = busqueda
    load(busqueda)
  }

  function limpiarFiltros() {
    setEstado(''); setMes(''); setAnio(String(ANIO_ACTUAL)); setBusqueda('')
    busquedaRef.current = ''
    load('')
  }

  const fmt = (v: string | null) =>
    v ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(Number(v)) : '—'
  const fmtDate = (v: string | null) =>
    v ? new Date(v).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'

  const totalImporte = facturas.reduce((s, f) => s + (f.total ? Number(f.total) : 0), 0)
  const hayFiltros = estado || mes || anio !== String(ANIO_ACTUAL) || busqueda

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Facturas</h2>
            <p className="text-sm text-slate-500 mt-0.5">{total} registro{total !== 1 ? 's' : ''}</p>
          </div>
          <Link href="/upload"
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            + Subir XML
          </Link>
        </div>

        {/* Filtros */}
        <div className="flex flex-wrap gap-3 mb-5 items-start">
          {/* Búsqueda */}
          <form onSubmit={handleBusqueda} className="flex gap-2">
            <input
              value={busqueda}
              onChange={e => setBusqueda(e.target.value)}
              placeholder="RFC o nombre del emisor…"
              className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white w-52 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button type="submit"
              className="px-3 py-1.5 border border-slate-200 rounded-lg text-sm bg-white text-slate-600 hover:bg-slate-50">
              Buscar
            </button>
          </form>

          <div className="w-px h-7 bg-slate-200 self-center" />

          {/* Estado */}
          <div className="flex gap-1.5">
            {['', 'pendiente', 'aprobada', 'rechazada'].map(e => (
              <button key={e} onClick={() => setEstado(e)}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  estado === e ? 'bg-blue-600 text-white' : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-400'
                }`}>
                {e === '' ? 'Todos' : e.charAt(0).toUpperCase() + e.slice(1)}
              </button>
            ))}
          </div>

          {/* Mes */}
          <select value={mes} onChange={e => setMes(e.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Todos los meses</option>
            {MESES.map((m, i) => <option key={i + 1} value={String(i + 1)}>{m}</option>)}
          </select>

          {/* Año */}
          <select value={anio} onChange={e => setAnio(e.target.value)}
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">Todos los años</option>
            {ANIOS.map(a => <option key={a} value={String(a)}>{a}</option>)}
          </select>

          {hayFiltros && (
            <button onClick={limpiarFiltros}
              className="text-xs text-slate-400 hover:text-slate-600 underline self-center">
              Limpiar filtros
            </button>
          )}
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {error} — <button onClick={() => load()} className="underline">Reintentar</button>
          </div>
        )}

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {loading ? (
            <p className="text-slate-500 text-sm text-center py-16">Cargando…</p>
          ) : facturas.length === 0 ? (
            <p className="text-slate-500 text-sm text-center py-16">
              Sin facturas para los filtros seleccionados.{' '}
              <Link href="/upload" className="text-blue-600 hover:underline">Subir XML.</Link>
            </p>
          ) : (
            <>
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 bg-slate-50">
                  <tr>
                    {['UUID', 'RFC Emisor', 'Nombre', 'Subtotal', 'Total', 'Estado', 'Fecha emisión'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {facturas.map(f => (
                    <tr key={f.id} onClick={() => router.push(`/facturas/${f.id}`)}
                      className="hover:bg-slate-50 cursor-pointer transition-colors">
                      <td className="px-4 py-3 font-mono text-xs text-slate-400">{f.uuid_cfdi.slice(0, 8)}…</td>
                      <td className="px-4 py-3 font-mono font-medium text-xs">{f.rfc_emisor}</td>
                      <td className="px-4 py-3 text-slate-700 truncate max-w-[180px]">{f.nombre_emisor ?? '—'}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmt(f.subtotal)}</td>
                      <td className="px-4 py-3 text-right tabular-nums font-semibold">{fmt(f.total)}</td>
                      <td className="px-4 py-3"><StatusBadge estado={f.estado} /></td>
                      <td className="px-4 py-3 text-slate-500 text-xs">{fmtDate(f.fecha_emision)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div className="px-4 py-3 border-t border-slate-100 bg-slate-50 flex justify-between items-center text-sm">
                <span className="text-slate-400 text-xs">{facturas.length} de {total} facturas</span>
                <span className="font-semibold text-slate-700">
                  Total: {new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(totalImporte)}
                </span>
              </div>
            </>
          )}
        </div>
      </main>
    </div>
  )
}
