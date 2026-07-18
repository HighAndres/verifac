'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import StatusBadge from '@/components/StatusBadge'
import { isAuthenticated, uploadFactura } from '@/lib/api'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

type XmlResult = { id: string; estado: string; uuid_cfdi: string; motivo_rechazo: string | null }

type ExcelFila = {
  fila: number
  nombre_emisor: string
  categoria?: string
  subtotal?: string
  estado: string
  errores: string[]
  factura_id?: string
}

type ExcelResult = {
  total_filas: number
  aprobadas: number
  rechazadas: number
  resultados: ExcelFila[]
}

export default function UploadPage() {
  const router = useRouter()
  const [tab, setTab] = useState<'xml' | 'excel'>('xml')

  // ── Estado XML ────────────────────────────────────────────────────────────
  const xmlRef = useRef<HTMLInputElement>(null)
  const [xmlFile, setXmlFile] = useState<File | null>(null)
  const [dragging, setDragging] = useState(false)
  const [xmlLoading, setXmlLoading] = useState(false)
  const [xmlResult, setXmlResult] = useState<XmlResult | null>(null)
  const [xmlError, setXmlError] = useState('')

  // ── Estado Excel ──────────────────────────────────────────────────────────
  const xlsxRef = useRef<HTMLInputElement>(null)
  const [xlsxFile, setXlsxFile] = useState<File | null>(null)
  const [xlsxLoading, setXlsxLoading] = useState(false)
  const [xlsxResult, setXlsxResult] = useState<ExcelResult | null>(null)
  const [xlsxError, setXlsxError] = useState('')

  useEffect(() => {
    if (!isAuthenticated()) router.push('/login')
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // ── Handlers XML ──────────────────────────────────────────────────────────
  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f?.name.toLowerCase().endsWith('.xml')) setXmlFile(f)
  }

  async function handleXmlUpload() {
    if (!xmlFile) return
    setXmlLoading(true); setXmlError(''); setXmlResult(null)
    try {
      const data = await uploadFactura(xmlFile)
      setXmlResult(data)
      setXmlFile(null)
    } catch (err: unknown) {
      setXmlError(err instanceof Error ? err.message : 'Error al procesar el archivo')
    } finally {
      setXmlLoading(false)
    }
  }

  // ── Handlers Excel ────────────────────────────────────────────────────────
  async function handleExcelUpload() {
    if (!xlsxFile) return
    setXlsxLoading(true); setXlsxError(''); setXlsxResult(null)
    try {
      const token = localStorage.getItem('cfdi_token')
      const fd = new FormData()
      fd.append('file', xlsxFile)
      const res = await fetch(`${API}/api/v1/facturas/upload-excel`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: fd,
      })
      if (!res.ok) {
        const e = await res.json()
        throw new Error(e.detail ?? 'Error del servidor')
      }
      const data: ExcelResult = await res.json()
      setXlsxResult(data)
      setXlsxFile(null)
    } catch (err: unknown) {
      setXlsxError(err instanceof Error ? err.message : 'Error al procesar el Excel')
    } finally {
      setXlsxLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-8 max-w-3xl">
        <h2 className="text-2xl font-bold text-slate-800 mb-6">Subir facturas</h2>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-slate-100 rounded-lg p-1 w-fit">
          <button
            onClick={() => setTab('xml')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === 'xml' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            XML individual (CFDI 4.0)
          </button>
          <button
            onClick={() => setTab('excel')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === 'excel' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Excel masivo (formato BBVA)
          </button>
        </div>

        {/* ── Tab XML ── */}
        {tab === 'xml' && (
          <div>
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={onDrop}
              onClick={() => xmlRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
                dragging ? 'border-blue-400 bg-blue-50'
                : xmlFile ? 'border-emerald-400 bg-emerald-50'
                : 'border-slate-300 hover:border-slate-400 bg-white'
              }`}
            >
              <input ref={xmlRef} type="file" accept=".xml" className="hidden"
                onChange={e => e.target.files?.[0] && setXmlFile(e.target.files[0])} />
              <div className="text-4xl mb-3">{xmlFile ? '📄' : '📂'}</div>
              {xmlFile ? (
                <>
                  <p className="font-medium text-emerald-700">{xmlFile.name}</p>
                  <p className="text-sm text-slate-400 mt-1">{(xmlFile.size / 1024).toFixed(1)} KB</p>
                </>
              ) : (
                <>
                  <p className="font-medium text-slate-600">Arrastra el XML aquí o haz clic para seleccionar</p>
                  <p className="text-sm text-slate-400 mt-1">Archivos .xml — CFDI 4.0</p>
                </>
              )}
            </div>

            <div className="flex gap-3 mt-4">
              <button onClick={handleXmlUpload} disabled={!xmlFile || xmlLoading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-medium py-2.5 rounded-lg text-sm transition-colors">
                {xmlLoading ? 'Validando…' : 'Validar y guardar'}
              </button>
              {xmlFile && (
                <button onClick={() => { setXmlFile(null); setXmlResult(null); setXmlError('') }}
                  className="px-4 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                  Limpiar
                </button>
              )}
            </div>

            {xmlError && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">{xmlError}</div>
            )}

            {xmlResult && (
              <div className={`mt-4 rounded-xl border p-5 ${xmlResult.estado === 'aprobada' ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}>
                <div className="flex items-center gap-3 mb-2">
                  <StatusBadge estado={xmlResult.estado} />
                  <span className="font-mono text-xs text-slate-500">{xmlResult.uuid_cfdi.slice(0, 8)}…</span>
                </div>
                {xmlResult.motivo_rechazo && <p className="text-sm text-red-700 mt-1">{xmlResult.motivo_rechazo}</p>}
                <button onClick={() => router.push(`/facturas/${xmlResult.id}`)}
                  className="mt-3 text-sm text-blue-600 hover:underline">
                  Ver detalle completo →
                </button>
              </div>
            )}
          </div>
        )}

        {/* ── Tab Excel ── */}
        {tab === 'excel' && (
          <div>
            <div className="mb-4 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-700 flex items-center justify-between gap-3">
              <div>
                <span className="font-semibold">Formato requerido:</span> usa la misma estructura del archivo
                {' '}<span className="font-mono">Ejemplo Base BBVA.xlsx</span> — una fila por profesor, con las mismas columnas.
              </div>
              <a
                href="/plantillas/Ejemplo_Base_BBVA.xlsx"
                download="Ejemplo Base BBVA.xlsx"
                className="shrink-0 bg-white border border-amber-300 hover:bg-amber-100 text-amber-800 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
              >
                ↓ Plantilla en blanco
              </a>
            </div>

            <div
              onClick={() => xlsxRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors ${
                xlsxFile ? 'border-emerald-400 bg-emerald-50' : 'border-slate-300 hover:border-slate-400 bg-white'
              }`}
            >
              <input ref={xlsxRef} type="file" accept=".xlsx" className="hidden"
                onChange={e => e.target.files?.[0] && setXlsxFile(e.target.files[0])} />
              <div className="text-4xl mb-3">{xlsxFile ? '📊' : '📋'}</div>
              {xlsxFile ? (
                <>
                  <p className="font-medium text-emerald-700">{xlsxFile.name}</p>
                  <p className="text-sm text-slate-400 mt-1">{(xlsxFile.size / 1024).toFixed(1)} KB</p>
                </>
              ) : (
                <>
                  <p className="font-medium text-slate-600">Haz clic para seleccionar el Excel</p>
                  <p className="text-sm text-slate-400 mt-1">Archivos .xlsx — formato Ejemplo Base BBVA</p>
                </>
              )}
            </div>

            <div className="flex gap-3 mt-4">
              <button onClick={handleExcelUpload} disabled={!xlsxFile || xlsxLoading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-medium py-2.5 rounded-lg text-sm transition-colors">
                {xlsxLoading ? 'Procesando…' : 'Cargar masivamente'}
              </button>
              {xlsxFile && (
                <button onClick={() => { setXlsxFile(null); setXlsxResult(null); setXlsxError('') }}
                  className="px-4 py-2.5 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                  Limpiar
                </button>
              )}
            </div>

            {xlsxError && (
              <div className="mt-4 bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-sm text-red-700">{xlsxError}</div>
            )}

            {xlsxResult && (
              <div className="mt-4 space-y-3">
                {/* Resumen */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-white border border-slate-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-slate-800">{xlsxResult.total_filas}</p>
                    <p className="text-xs text-slate-500 mt-1">Total filas</p>
                  </div>
                  <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-emerald-700">{xlsxResult.aprobadas}</p>
                    <p className="text-xs text-emerald-600 mt-1">Aprobadas</p>
                  </div>
                  <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-red-700">{xlsxResult.rechazadas}</p>
                    <p className="text-xs text-red-600 mt-1">Rechazadas</p>
                  </div>
                </div>

                {/* Detalle por fila */}
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  <div className="px-4 py-3 border-b border-slate-100">
                    <p className="text-sm font-semibold text-slate-700">Resultado por fila</p>
                  </div>
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 border-b border-slate-100">
                      <tr>
                        {['Fila', 'Nombre emisor', 'Categoría', 'Subtotal', 'Estado', ''].map(h => (
                          <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {xlsxResult.resultados.map(r => (
                        <tr key={r.fila} className={r.estado === 'rechazada' ? 'bg-red-50' : ''}>
                          <td className="px-4 py-2.5 text-slate-400 text-xs">{r.fila}</td>
                          <td className="px-4 py-2.5 font-medium text-slate-700 truncate max-w-[180px]">{r.nombre_emisor}</td>
                          <td className="px-4 py-2.5 text-slate-500 text-xs">{r.categoria ?? '—'}</td>
                          <td className="px-4 py-2.5 tabular-nums text-xs">
                            {r.subtotal ? new Intl.NumberFormat('es-MX', { style: 'currency', currency: 'MXN' }).format(Number(r.subtotal)) : '—'}
                          </td>
                          <td className="px-4 py-2.5"><StatusBadge estado={r.estado} /></td>
                          <td className="px-4 py-2.5 text-right">
                            {r.factura_id && (
                              <button onClick={() => router.push(`/facturas/${r.factura_id}`)}
                                className="text-xs text-blue-500 hover:underline">
                                Ver →
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
