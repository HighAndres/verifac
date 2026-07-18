'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { getAuditoria, isSuperAdmin } from '@/lib/api'

interface AuditLog {
  id: string
  username: string
  rol: string | null
  accion: string
  recurso: string | null
  recurso_id: string | null
  detalle: string | null
  ip: string | null
  timestamp: string
}

const ACCIONES = ['LOGIN', 'CREATE', 'UPDATE', 'DELETE', 'UPLOAD']
const RECURSOS = ['factura', 'profesor', 'catalogo_clave', 'usuario', 'watcher']

const ACCION_BADGE: Record<string, string> = {
  LOGIN:  'bg-blue-100 text-blue-700',
  CREATE: 'bg-emerald-100 text-emerald-700',
  UPDATE: 'bg-amber-100 text-amber-700',
  DELETE: 'bg-red-100 text-red-700',
  UPLOAD: 'bg-purple-100 text-purple-700',
}

export default function AuditoriaPage() {
  const router = useRouter()
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  const [filtroUsername, setFiltroUsername] = useState('')
  const [filtroAccion, setFiltroAccion] = useState('')
  const [filtroRecurso, setFiltroRecurso] = useState('')
  const [filtroDesde, setFiltroDesde] = useState('')
  const [filtroHasta, setFiltroHasta] = useState('')

  useEffect(() => {
    if (!isSuperAdmin()) { router.push('/facturas'); return }
    load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function load() {
    setLoading(true)
    try {
      const params: Record<string, string> = { limit: '100' }
      if (filtroUsername) params.username = filtroUsername
      if (filtroAccion) params.accion = filtroAccion
      if (filtroRecurso) params.recurso = filtroRecurso
      if (filtroDesde) params.desde = new Date(filtroDesde).toISOString()
      if (filtroHasta) params.hasta = new Date(filtroHasta + 'T23:59:59').toISOString()
      const data = await getAuditoria(params)
      setLogs(data.items)
      setTotal(data.total)
    } finally { setLoading(false) }
  }

  const fmtDate = (v: string) =>
    new Date(v).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'medium' })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-slate-800">Auditoría</h2>
          <p className="text-sm text-slate-500 mt-0.5">{total} evento{total !== 1 ? 's' : ''} registrado{total !== 1 ? 's' : ''}</p>
        </div>

        {/* Filtros */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 mb-5">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Filtros</p>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-5">
            <input value={filtroUsername} onChange={e => setFiltroUsername(e.target.value)}
              placeholder="Usuario" onKeyDown={e => e.key === 'Enter' && load()}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />

            <select value={filtroAccion} onChange={e => setFiltroAccion(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">Todas las acciones</option>
              {ACCIONES.map(a => <option key={a} value={a}>{a}</option>)}
            </select>

            <select value={filtroRecurso} onChange={e => setFiltroRecurso(e.target.value)}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">Todos los recursos</option>
              {RECURSOS.map(r => <option key={r} value={r}>{r}</option>)}
            </select>

            <div>
              <input type="date" value={filtroDesde} onChange={e => setFiltroDesde(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <p className="text-xs text-slate-400 mt-0.5 ml-1">Desde</p>
            </div>
            <div>
              <input type="date" value={filtroHasta} onChange={e => setFiltroHasta(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <p className="text-xs text-slate-400 mt-0.5 ml-1">Hasta</p>
            </div>
          </div>
          <button onClick={load}
            className="mt-3 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            Buscar
          </button>
        </div>

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {loading ? (
            <p className="text-slate-400 text-sm text-center py-16">Cargando…</p>
          ) : logs.length === 0 ? (
            <p className="text-slate-400 text-sm text-center py-16">Sin registros para los filtros seleccionados.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-100">
                <tr>
                  {['Fecha', 'Usuario', 'Rol', 'Acción', 'Recurso', 'Detalle', 'IP'].map(h => (
                    <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {logs.map(log => (
                  <tr key={log.id} className="hover:bg-slate-50">
                    <td className="px-4 py-2.5 text-slate-500 text-xs whitespace-nowrap">{fmtDate(log.timestamp)}</td>
                    <td className="px-4 py-2.5 font-mono font-medium text-xs">{log.username}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-400 capitalize">{log.rol ?? '—'}</td>
                    <td className="px-4 py-2.5">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${ACCION_BADGE[log.accion] ?? 'bg-slate-100 text-slate-600'}`}>
                        {log.accion}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">{log.recurso ?? '—'}</td>
                    <td className="px-4 py-2.5 text-xs text-slate-600 max-w-[240px] truncate" title={log.detalle ?? ''}>
                      {log.detalle ?? '—'}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-slate-400">{log.ip ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>
    </div>
  )
}
