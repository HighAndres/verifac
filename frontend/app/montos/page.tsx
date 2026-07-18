'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useToast } from '@/components/Toast'
import { getMontosMensuales, uploadMontosMensuales, revalidarMes, isAuthenticated } from '@/lib/api'

interface MontoItem {
  id: string
  nombre_layout: string
  categoria: string | null
  regimen_fiscal: string
  profesor_id: string | null
  subtotal: number
  iva_trasladado: number
  iva_retenido: number
  isr_retenido: number
  total: number
}

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
const ANIO_ACTUAL = new Date().getFullYear()
const ANIOS = Array.from({ length: 5 }, (_, i) => ANIO_ACTUAL - i)

const fmt = (v: number) =>
  new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(v)

const REGIMEN_LABEL: Record<string, string> = {
  '612': '612 · Honorarios',
  '626': '626 · RESICO',
  '603': '603 · Sin retención',
}

export default function MontosPage() {
  const router = useRouter()
  const toast = useToast()
  const fileRef = useRef<HTMLInputElement>(null)

  const [mes, setMes] = useState(new Date().getMonth() + 1)
  const [anio, setAnio] = useState(ANIO_ACTUAL)
  const [items, setItems] = useState<MontoItem[]>([])
  const [loading, setLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [revalidando, setRevalidando] = useState(false)

  async function handleRevalidar() {
    setRevalidando(true)
    try {
      const res = await revalidarMes(mes, anio)
      toast(
        `${res.revalidadas} facturas revalidadas · ${res.con_cambio} con cambio de estado`,
        'success'
      )
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al revalidar', 'error')
    } finally {
      setRevalidando(false)
    }
  }

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    cargar()
  }, [mes, anio]) // eslint-disable-line react-hooks/exhaustive-deps

  async function cargar() {
    setLoading(true)
    try {
      const data = await getMontosMensuales(mes, anio)
      setItems(data.items)
    } catch {
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      const res = await uploadMontosMensuales(file, mes, anio)
      const reemplazo = res.montos_previos_reemplazados
        ? ` · ${res.montos_previos_reemplazados} previos reemplazados`
        : ''
      toast(
        `${res.total_filas} filas cargadas · ${res.emparejados} emparejados · ${res.sin_match} sin match${reemplazo}`,
        'success'
      )
      for (const adv of (res.advertencias ?? [])) toast(adv, 'info')
      await cargar()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al cargar el archivo', 'error')
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const totalSubtotal = items.reduce((s, i) => s + i.subtotal, 0)
  const totalImporte  = items.reduce((s, i) => s + i.total, 0)

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8">

        {/* Encabezado */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Montos del mes</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Layout de referencia para conciliación CFDI
            </p>
          </div>

          <div className="flex gap-3">
            <a
              href="/plantillas/Ejemplo_Base_BBVA_Montos.xlsx"
              download="Ejemplo Base BBVA Montos.xlsx"
              className="bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              ↓ Plantilla en blanco
            </a>
            <button
              onClick={handleRevalidar}
              disabled={revalidando}
              title="Revuelve a validar las facturas de este mes contra el layout actual"
              className={`bg-slate-100 hover:bg-slate-200 text-slate-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors ${revalidando ? 'opacity-60 pointer-events-none' : ''}`}
            >
              {revalidando ? 'Revalidando…' : '↻ Revalidar mes'}
            </button>
            <label className={`cursor-pointer bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors ${uploading ? 'opacity-60 pointer-events-none' : ''}`}>
              {uploading ? 'Cargando…' : '+ Subir layout (.xlsx)'}
              <input
                ref={fileRef}
                type="file"
                accept=".xlsx"
                className="hidden"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </div>
        </div>

        {/* Selector mes / año */}
        <div className="flex gap-3 mb-6">
          <select
            value={mes}
            onChange={e => setMes(Number(e.target.value))}
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {MESES.map((m, i) => (
              <option key={i + 1} value={i + 1}>{m}</option>
            ))}
          </select>

          <select
            value={anio}
            onChange={e => setAnio(Number(e.target.value))}
            className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            {ANIOS.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>

          <span className="self-center text-sm text-slate-400">
            {items.length} profesor{items.length !== 1 ? 'es' : ''}
          </span>
        </div>

        {/* Tabla */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {loading ? (
            <p className="text-slate-500 text-sm text-center py-16">Cargando…</p>
          ) : items.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-slate-500 text-sm">No hay montos cargados para {MESES[mes - 1]} {anio}.</p>
              <p className="text-slate-400 text-xs mt-1">Sube el layout .xlsx para este mes.</p>
            </div>
          ) : (
            <>
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 bg-slate-50">
                  <tr>
                    {['Nombre', 'Categoría', 'Régimen', 'Emparejado', 'Subtotal', 'IVA', 'IVA ret.', 'ISR ret.', 'Total'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {items.map(item => (
                    <tr key={item.id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 font-medium text-slate-800 max-w-[220px] truncate" title={item.nombre_layout}>
                        {item.nombre_layout}
                      </td>
                      <td className="px-4 py-3 text-slate-500 text-xs">{item.categoria ?? '—'}</td>
                      <td className="px-4 py-3 text-xs">
                        <span className="bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-mono">
                          {REGIMEN_LABEL[item.regimen_fiscal] ?? item.regimen_fiscal}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {item.profesor_id ? (
                          <span className="inline-flex items-center gap-1 text-green-700 bg-green-50 border border-green-200 text-xs px-2 py-0.5 rounded-full font-medium">
                            ✓ Sí
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 border border-amber-200 text-xs px-2 py-0.5 rounded-full font-medium">
                            ✗ Sin match
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmt(item.subtotal)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-slate-500">{fmt(item.iva_trasladado)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-slate-500">{fmt(item.iva_retenido)}</td>
                      <td className="px-4 py-3 text-right tabular-nums text-slate-500">{fmt(item.isr_retenido)}</td>
                      <td className="px-4 py-3 text-right tabular-nums font-semibold text-slate-800">{fmt(item.total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Totales */}
              <div className="px-4 py-3 border-t border-slate-100 bg-slate-50 flex justify-between items-center">
                <span className="text-xs text-slate-400">{items.length} profesores</span>
                <div className="flex gap-6 text-sm">
                  <span className="text-slate-500">
                    Subtotal: <span className="font-semibold text-slate-700">{fmt(totalSubtotal)}</span>
                  </span>
                  <span className="text-slate-500">
                    Total a pagar: <span className="font-semibold text-slate-800">{fmt(totalImporte)}</span>
                  </span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* Nota informativa */}
        {items.some(i => !i.profesor_id) && (
          <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
            <strong>Profesores sin match:</strong> registra estos profesores en el catálogo con el mismo nombre del layout para que el sistema los empareje y pueda validar sus facturas contra los montos esperados.
          </div>
        )}

      </main>
    </div>
  )
}
