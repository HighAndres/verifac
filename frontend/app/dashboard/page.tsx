'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '@/components/Sidebar'
import StatusBadge from '@/components/StatusBadge'
import { getDashboard, isAuthenticated } from '@/lib/api'

interface Resumen {
  mes: number
  anio: number
  facturas: { total: number; aprobadas: number; rechazadas: number; otras: number }
  montos: {
    profesores_en_layout: number
    sin_match: number
    esperado_total: number
    aprobado_total: number
  }
  pendientes_envio: { nombre: string; rfc: string; esperado: number }[]
  ultimas_facturas: {
    id: string; nombre_emisor: string | null; total: number
    estado: string; fecha_emision: string | null
  }[]
}

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
const ANIO_ACTUAL = new Date().getFullYear()
const ANIOS = Array.from({ length: 5 }, (_, i) => ANIO_ACTUAL - i)

const fmt = (v: number) =>
  new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v)

function Tile({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 tabular-nums ${accent ?? 'text-slate-800'}`}>{value}</p>
    </div>
  )
}

export default function DashboardPage() {
  const router = useRouter()
  const [mes, setMes] = useState(new Date().getMonth() + 1)
  const [anio, setAnio] = useState(ANIO_ACTUAL)
  const [data, setData] = useState<Resumen | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    setLoading(true)
    getDashboard(mes, anio)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false))
  }, [mes, anio]) // eslint-disable-line react-hooks/exhaustive-deps

  const esperado = data?.montos.esperado_total ?? 0
  const aprobado = data?.montos.aprobado_total ?? 0
  const pct = esperado > 0 ? Math.min(100, (aprobado / esperado) * 100) : 0

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8 max-w-5xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Panorama del mes</h2>
            <p className="text-sm text-slate-500 mt-0.5">Estado de la conciliación de {MESES[mes - 1]} {anio}</p>
          </div>
          <div className="flex gap-3">
            <select value={mes} onChange={e => setMes(Number(e.target.value))}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white">
              {MESES.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
            </select>
            <select value={anio} onChange={e => setAnio(Number(e.target.value))}
              className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white">
              {ANIOS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
        </div>

        {loading ? (
          <p className="text-slate-500 text-sm py-16 text-center">Cargando…</p>
        ) : !data ? (
          <p className="text-slate-500 text-sm py-16 text-center">No se pudo cargar el panorama.</p>
        ) : (
          <div className="space-y-6">
            {/* KPIs */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <Tile label="Facturas recibidas" value={String(data.facturas.total)} />
              <Tile label="Aprobadas" value={String(data.facturas.aprobadas)} accent="text-emerald-600" />
              <Tile label="Rechazadas" value={String(data.facturas.rechazadas)} accent="text-red-600" />
              <Tile label="Profesores en layout" value={String(data.montos.profesores_en_layout)} />
            </div>

            {/* Avance de conciliación */}
            <div className="bg-white border border-slate-200 rounded-xl p-5">
              <div className="flex items-baseline justify-between mb-2">
                <p className="text-sm font-medium text-slate-700">Monto conciliado (facturas aprobadas vs esperado)</p>
                <p className="text-sm text-slate-500 tabular-nums">
                  <span className="font-semibold text-slate-800">{fmt(aprobado)}</span>
                  {' '}de {fmt(esperado)} ({pct.toFixed(0)}%)
                </p>
              </div>
              <div className="h-3 bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-blue-600 rounded-full transition-all" style={{ width: `${pct}%` }} />
              </div>
              {esperado === 0 && (
                <p className="text-xs text-slate-400 mt-2">
                  Sin layout de montos para este mes — <Link href="/montos" className="text-blue-600 hover:underline">cargarlo</Link> habilita la conciliación.
                </p>
              )}
            </div>

            {/* Avisos */}
            {data.montos.sin_match > 0 && (
              <div className="bg-amber-50 border border-amber-200 rounded-xl px-4 py-3 text-sm text-amber-700">
                <strong>{data.montos.sin_match}</strong> fila(s) del layout sin profesor emparejado —{' '}
                <Link href="/montos" className="underline font-medium">revisar en Montos del mes</Link>.
              </div>
            )}

            <div className="grid lg:grid-cols-2 gap-6">
              {/* Pendientes de envío */}
              <div className="bg-white border border-slate-200 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-slate-800 mb-3">
                  Sin factura aprobada ({data.pendientes_envio.length})
                </h3>
                {data.pendientes_envio.length === 0 ? (
                  <p className="text-sm text-slate-400">
                    {esperado > 0 ? 'Todos los profesores del layout tienen factura aprobada. ✓' : 'Sin layout cargado este mes.'}
                  </p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {data.pendientes_envio.map(p => (
                      <li key={p.rfc} className="py-2 flex items-center justify-between text-sm">
                        <div>
                          <p className="text-slate-700">{p.nombre}</p>
                          <p className="text-xs text-slate-400 font-mono">{p.rfc}</p>
                        </div>
                        <span className="text-slate-500 tabular-nums">{fmt(p.esperado)}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Últimas facturas */}
              <div className="bg-white border border-slate-200 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-slate-800 mb-3">Últimas facturas del mes</h3>
                {data.ultimas_facturas.length === 0 ? (
                  <p className="text-sm text-slate-400">Aún no llegan facturas este mes.</p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {data.ultimas_facturas.map(f => (
                      <li key={f.id} className="py-2 flex items-center justify-between gap-3 text-sm">
                        <Link href={`/facturas/${f.id}`} className="text-slate-700 hover:text-blue-600 truncate">
                          {f.nombre_emisor ?? '(sin nombre)'}
                        </Link>
                        <div className="flex items-center gap-3 shrink-0">
                          <span className="text-slate-500 tabular-nums">{fmt(f.total)}</span>
                          <StatusBadge estado={f.estado} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
