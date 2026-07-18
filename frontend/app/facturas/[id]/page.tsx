'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '@/components/Sidebar'
import StatusBadge from '@/components/StatusBadge'
import { getFactura, isAuthenticated } from '@/lib/api'

interface Detalle {
  id: string
  campo: string
  valor_recibido: string | null
  valor_esperado: string | null
  resultado: boolean
  mensaje: string | null
}

interface FacturaDetalle {
  id: string
  uuid_cfdi: string
  rfc_emisor: string
  nombre_emisor: string | null
  regimen_emisor: string | null
  fecha_emision: string | null
  fecha_timbrado: string | null
  subtotal: string | null
  iva_trasladado: string | null
  iva_retenido: string | null
  isr_retenido: string | null
  total: string | null
  clave_servicio: string | null
  clave_unidad: string | null
  descripcion_concepto: string | null
  forma_pago: string | null
  metodo_pago: string | null
  uso_cfdi: string | null
  estado: string
  motivo_rechazo: string | null
  created_at: string
  detalles: Detalle[]
}

const REGIMENES: Record<string, string> = {
  '626': 'RESICO',
  '612': 'PF Act. Empresariales',
  '603': 'PM Fines no Lucrativos',
}

export default function FacturaDetallePage() {
  const router = useRouter()
  const { id } = useParams<{ id: string }>()
  const [factura, setFactura] = useState<FacturaDetalle | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    getFactura(id).then(setFactura).finally(() => setLoading(false))
  }, [id]) // eslint-disable-line react-hooks/exhaustive-deps

  const fmt = (v: string | null) =>
    v ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(Number(v)) : '—'

  if (loading) return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8 flex items-center justify-center">
        <p className="text-slate-400">Cargando…</p>
      </main>
    </div>
  )

  if (!factura) return null

  const pasados = factura.detalles.filter(d => d.resultado).length
  const total = factura.detalles.length

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-8 max-w-5xl">
        <div className="mb-6">
          <Link href="/facturas" className="text-sm text-slate-500 hover:text-slate-700">
            ← Facturas
          </Link>
        </div>

        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h2 className="text-xl font-bold text-slate-800">{factura.nombre_emisor ?? factura.rfc_emisor}</h2>
              <StatusBadge estado={factura.estado} />
            </div>
            <p className="text-xs font-mono text-slate-400">{factura.uuid_cfdi}</p>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold text-slate-800">{fmt(factura.total)}</p>
            <p className="text-xs text-slate-400">Total factura</p>
          </div>
        </div>

        {factura.motivo_rechazo && (
          <div className="mb-5 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
            {factura.motivo_rechazo}
          </div>
        )}

        {/* Datos fiscales */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Emisor</p>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">RFC</dt><dd className="font-mono font-medium">{factura.rfc_emisor}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Régimen</dt><dd>{factura.regimen_emisor ? `${factura.regimen_emisor} — ${REGIMENES[factura.regimen_emisor] ?? ''}` : '—'}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Clave servicio</dt><dd className="font-mono">{factura.clave_servicio ?? '—'}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Clave unidad</dt><dd className="font-mono">{factura.clave_unidad ?? '—'}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Uso CFDI</dt><dd className="font-mono">{factura.uso_cfdi ?? '—'}</dd></div>
            </dl>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">Importes</p>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Subtotal</dt><dd className="tabular-nums">{fmt(factura.subtotal)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">IVA trasladado</dt><dd className="tabular-nums">{fmt(factura.iva_trasladado)}</dd></div>
              <div className="flex justify-between text-red-700"><dt>ISR retenido</dt><dd className="tabular-nums">({fmt(factura.isr_retenido)})</dd></div>
              <div className="flex justify-between text-red-700"><dt>IVA retenido</dt><dd className="tabular-nums">({fmt(factura.iva_retenido)})</dd></div>
              <div className="flex justify-between pt-2 border-t border-slate-100 font-semibold"><dt>Total</dt><dd className="tabular-nums">{fmt(factura.total)}</dd></div>
            </dl>
          </div>
        </div>

        {/* Validaciones */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <h3 className="font-semibold text-slate-700">Resultado de validaciones</h3>
            <span className="text-sm text-slate-500">{pasados}/{total} checks</span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-100">
              <tr>
                {['Campo', 'Recibido', 'Esperado', 'Nota', ''].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-50">
              {factura.detalles.map(d => (
                <tr key={d.id} className={d.resultado ? '' : 'bg-red-50'}>
                  <td className="px-4 py-2.5 font-mono text-xs text-slate-600">{d.campo}</td>
                  <td className="px-4 py-2.5 font-mono text-xs max-w-[160px] truncate" title={d.valor_recibido ?? ''}>
                    {d.valor_recibido ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500 max-w-[180px] truncate" title={d.valor_esperado ?? ''}>
                    {d.valor_esperado ?? '—'}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-400 italic">{d.mensaje ?? ''}</td>
                  <td className="px-4 py-2.5 text-center">
                    {d.resultado
                      ? <span className="text-emerald-600 font-bold">✓</span>
                      : <span className="text-red-600 font-bold">✗</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  )
}
