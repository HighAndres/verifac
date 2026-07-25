'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import StatusBadge from '@/components/StatusBadge'
import { useToast } from '@/components/Toast'
import {
  getMiPerfil, getMisFacturas, getMisPagos, getMiFactura, subirMiFactura,
  isAuthenticated, isProfesor, logout, getNombre,
} from '@/lib/api'

interface Perfil {
  id: string
  rfc: string
  nombre: string
  correo: string
  regimen_fiscal: string
  drive_url: string | null
}

interface Factura {
  id: string
  uuid_cfdi: string
  total: string | null
  estado: string
  motivo_rechazo: string | null
  fecha_emision: string | null
  confirmacion_enviada?: string | null
}

interface Pago {
  mes: number
  anio: number
  fecha_pago: string | null
  metodo_pago: string | null
  monto_pagado: number | null
}

interface Detalle {
  campo: string
  valor_recibido: string | null
  valor_esperado: string | null
  resultado: boolean
  mensaje: string | null
}

interface FacturaDetalle extends Factura {
  detalles: Detalle[]
}

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
               'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
const ANIO_ACTUAL = new Date().getFullYear()
const ANIOS = Array.from({ length: 5 }, (_, i) => ANIO_ACTUAL - i)

// Tabla de resultados de validación (los mismos checks que ve el revisor).
function ChecksTabla({ f, onClose }: { f: FacturaDetalle; onClose?: () => void }) {
  const fallidos = f.detalles.filter(d => !d.resultado)
  return (
    <div className="border-t border-slate-100 bg-slate-50/50 px-5 py-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <StatusBadge estado={f.estado} />
          <span className="font-mono text-xs text-slate-400">{f.uuid_cfdi.slice(0, 8)}…</span>
          <span className="text-xs text-slate-500">{f.detalles.length - fallidos.length}/{f.detalles.length} checks</span>
        </div>
        {onClose && <button onClick={onClose} className="text-xs text-slate-400 hover:text-slate-600">Cerrar</button>}
      </div>
      {f.estado === 'rechazada' && (
        <p className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-lg px-3 py-2 mb-3">
          Corrige los campos marcados en rojo, vuelve a emitir el CFDI y súbelo de nuevo.
        </p>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-slate-400 uppercase tracking-wide">
            <tr><th className="py-1.5 pr-3">Campo</th><th className="py-1.5 pr-3">Recibido</th><th className="py-1.5 pr-3">Esperado</th><th className="py-1.5"></th></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {f.detalles.map((d, i) => (
              <tr key={i} className={d.resultado ? '' : 'bg-red-50/60'}>
                <td className="py-1.5 pr-3 text-slate-700">{d.campo}</td>
                <td className="py-1.5 pr-3 font-mono text-xs text-slate-500">{d.valor_recibido ?? '—'}</td>
                <td className="py-1.5 pr-3 font-mono text-xs text-slate-500">{d.valor_esperado ?? '—'}</td>
                <td className="py-1.5 text-right">{d.resultado ? <span className="text-emerald-600">✔</span> : <span className="text-red-600 font-semibold">✗</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function PortalPage() {
  const router = useRouter()
  const toast = useToast()
  const [perfil, setPerfil] = useState<Perfil | null>(null)
  const [facturas, setFacturas] = useState<Factura[]>([])
  const [pagos, setPagos] = useState<Pago[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [mes, setMes] = useState('')
  const [anio, setAnio] = useState(String(ANIO_ACTUAL))
  const [nombre, setNombre] = useState('')  // se fija en cliente para no romper la hidratación
  // Subir mi factura
  const [xmlFile, setXmlFile] = useState<File | null>(null)
  const [pdfFile, setPdfFile] = useState<File | null>(null)
  const [subiendo, setSubiendo] = useState(false)
  const [resultado, setResultado] = useState<FacturaDetalle | null>(null)
  const [detalleVer, setDetalleVer] = useState<FacturaDetalle | null>(null)  // detalle de una factura previa

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    if (!isProfesor()) { router.push('/dashboard'); return }
    setNombre(getNombre())
    getMiPerfil().then(setPerfil).catch(() => {})
    getMisPagos().then(d => setPagos(d.items)).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!isAuthenticated() || !isProfesor()) return
    load()
  }, [mes, anio]) // eslint-disable-line react-hooks/exhaustive-deps

  async function load() {
    setLoading(true); setError('')
    try {
      const params: Record<string, string> = { limit: '100' }
      if (mes)  params.mes = mes
      if (anio) params.anio = anio
      const data = await getMisFacturas(params)
      setFacturas(data.items)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al cargar tus facturas'
      setError(msg)
      toast(msg, 'error')
    } finally {
      setLoading(false)
    }
  }

  async function handleSubir(e: React.FormEvent) {
    e.preventDefault()
    if (!xmlFile || !pdfFile) return
    setSubiendo(true); setResultado(null); setDetalleVer(null)
    try {
      const res: FacturaDetalle = await subirMiFactura(xmlFile, pdfFile)
      setResultado(res)
      setXmlFile(null); setPdfFile(null)
      toast(
        res.estado === 'aprobada' ? 'Factura aprobada ✓' : 'Factura rechazada — revisa los campos marcados',
        res.estado === 'aprobada' ? 'success' : 'info'
      )
      load()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al subir la factura', 'error')
    } finally {
      setSubiendo(false)
    }
  }

  async function verDetalle(id: string) {
    try {
      const d: FacturaDetalle = await getMiFactura(id)
      setDetalleVer(d); setResultado(null)
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'No se pudo abrir el detalle', 'error')
    }
  }

  const fmt = (v: string | number | null) =>
    v != null && v !== '' ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(Number(v)) : '—'
  const fmtDate = (v: string | null) => {
    if (!v) return '—'
    // Fechas solo-día (YYYY-MM-DD) se parsean en local para no correrse por zona horaria.
    const d = /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(v + 'T00:00:00') : new Date(v)
    return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' })
  }
  const fmtPeriodo = (mes: number, anio: number) => `${MESES[mes - 1]} ${anio}`

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Encabezado */}
      <header className="bg-slate-900 text-slate-100">
        <div className="max-w-4xl mx-auto px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shrink-0">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2 4 5v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V5l-8-3Z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <div>
              <h1 className="text-lg font-semibold leading-none">Verifac</h1>
              <p className="text-[10px] text-slate-400 uppercase tracking-widest mt-1">Portal del profesor</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-sm font-medium truncate max-w-[200px]">{perfil?.nombre || nombre || 'Profesor'}</p>
            <button onClick={logout} className="text-xs text-slate-400 hover:text-white transition-colors">
              Cerrar sesión
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        {/* Datos + documentos */}
        <section className="grid gap-4 sm:grid-cols-2">
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3">Mis datos</h2>
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">RFC</dt>
                <dd className="font-mono font-medium">{perfil?.rfc ?? '—'}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Correo</dt>
                <dd className="text-slate-700 truncate">{perfil?.correo ?? '—'}</dd>
              </div>
              <div className="flex justify-between gap-4">
                <dt className="text-slate-500">Régimen fiscal</dt>
                <dd className="text-slate-700">{perfil?.regimen_fiscal ?? '—'}</dd>
              </div>
            </dl>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 p-5 flex flex-col">
            <h2 className="text-xs font-semibold uppercase tracking-widest text-slate-400 mb-3">Mis documentos</h2>
            <p className="text-sm text-slate-500 mb-4 flex-1">
              Comprobantes y documentos guardados en tu carpeta de Google Drive.
            </p>
            {perfil?.drive_url ? (
              <a href={perfil.drive_url} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <path d="M14 2v6h6" />
                </svg>
                Abrir mi carpeta
              </a>
            ) : (
              <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                Aún no disponible. Contacta al administrador.
              </p>
            )}
          </div>
        </section>

        {/* Subir mi factura */}
        <section className="bg-white rounded-xl border border-slate-200">
          <div className="px-5 py-4 border-b border-slate-100">
            <h2 className="text-base font-semibold text-slate-800">Subir mi factura</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Sube el <b>XML</b> y el <b>PDF</b> de tu factura. El sistema la valida al instante y te dice si está bien o qué corregir.
            </p>
          </div>
          <form onSubmit={handleSubir} className="p-5">
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block">
                <span className="block text-xs font-medium text-slate-600 mb-1">Archivo XML (CFDI 4.0)</span>
                <input type="file" accept=".xml" required
                  onChange={e => setXmlFile(e.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border file:border-slate-200 file:text-sm file:bg-slate-50 hover:file:bg-slate-100" />
              </label>
              <label className="block">
                <span className="block text-xs font-medium text-slate-600 mb-1">Archivo PDF</span>
                <input type="file" accept=".pdf" required
                  onChange={e => setPdfFile(e.target.files?.[0] ?? null)}
                  className="block w-full text-sm text-slate-600 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border file:border-slate-200 file:text-sm file:bg-slate-50 hover:file:bg-slate-100" />
              </label>
            </div>
            <button type="submit" disabled={subiendo || !xmlFile || !pdfFile}
              className="mt-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors">
              {subiendo ? 'Validando…' : 'Validar y enviar'}
            </button>
          </form>
          {resultado && <ChecksTabla f={resultado} onClose={() => setResultado(null)} />}
        </section>

        {/* Facturas */}
        <section className="bg-white rounded-xl border border-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-slate-100">
            <h2 className="text-base font-semibold text-slate-800">Mis facturas</h2>
            <div className="flex gap-2">
              <select value={mes} onChange={e => setMes(e.target.value)}
                className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Todos los meses</option>
                {MESES.map((m, i) => <option key={i + 1} value={String(i + 1)}>{m}</option>)}
              </select>
              <select value={anio} onChange={e => setAnio(e.target.value)}
                className="border border-slate-200 rounded-lg px-3 py-1.5 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Todos los años</option>
                {ANIOS.map(a => <option key={a} value={String(a)}>{a}</option>)}
              </select>
            </div>
          </div>

          {error && (
            <div className="m-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">
              {error} — <button onClick={load} className="underline">Reintentar</button>
            </div>
          )}

          <div className="overflow-x-auto">
            {loading ? (
              <p className="text-slate-500 text-sm text-center py-16">Cargando…</p>
            ) : facturas.length === 0 ? (
              <p className="text-slate-500 text-sm text-center py-16">
                No tienes facturas registradas para el periodo seleccionado.
              </p>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 bg-slate-50">
                  <tr>
                    {['Folio fiscal', 'Fecha emisión', 'Total', 'Estado', 'Detalle'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {facturas.map(f => (
                    <tr key={f.id} onClick={() => verDetalle(f.id)}
                      className="hover:bg-slate-50 transition-colors cursor-pointer">
                      <td className="px-4 py-3 font-mono text-xs text-slate-400">{f.uuid_cfdi.slice(0, 8)}…</td>
                      <td className="px-4 py-3 text-slate-500 text-xs">{fmtDate(f.fecha_emision)}</td>
                      <td className="px-4 py-3 text-right tabular-nums font-semibold">{fmt(f.total)}</td>
                      <td className="px-4 py-3"><StatusBadge estado={f.estado} /></td>
                      <td className="px-4 py-3 text-xs text-slate-500 max-w-[240px]">
                        {f.estado === 'rechazada' && f.motivo_rechazo
                          ? <span className="text-red-700">{f.motivo_rechazo}</span>
                          : f.estado === 'aprobada' && f.confirmacion_enviada
                            ? <span className="text-emerald-700">Confirmación enviada</span>
                            : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          {!loading && facturas.length > 0 && !detalleVer && (
            <p className="px-5 pb-3 text-xs text-slate-400">Toca una factura para ver el detalle de la validación.</p>
          )}
          {detalleVer && <ChecksTabla f={detalleVer} onClose={() => setDetalleVer(null)} />}
        </section>

        {/* Mis pagos */}
        <section className="bg-white rounded-xl border border-slate-200">
          <div className="px-5 py-4 border-b border-slate-100">
            <h2 className="text-base font-semibold text-slate-800">Mis pagos</h2>
          </div>
          <div className="overflow-x-auto">
            {pagos.length === 0 ? (
              <p className="text-slate-500 text-sm text-center py-12">Aún no se registran pagos.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="border-b border-slate-200 bg-slate-50">
                  <tr>
                    {['Periodo', 'Fecha de pago', 'Método', 'Monto pagado'].map(h => (
                      <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {pagos.map(p => (
                    <tr key={`${p.anio}-${p.mes}`} className="hover:bg-slate-50 transition-colors">
                      <td className="px-4 py-3 text-slate-700">{fmtPeriodo(p.mes, p.anio)}</td>
                      <td className="px-4 py-3 text-slate-500 text-xs">{fmtDate(p.fecha_pago)}</td>
                      <td className="px-4 py-3 text-slate-700">{p.metodo_pago ?? '—'}</td>
                      <td className="px-4 py-3 text-right tabular-nums font-semibold">{fmt(p.monto_pagado)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </main>
    </div>
  )
}
