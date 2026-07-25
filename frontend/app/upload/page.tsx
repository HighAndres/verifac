'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import StatusBadge from '@/components/StatusBadge'
import { isAuthenticated, uploadFactura, importarProfesores } from '@/lib/api'

type XmlResult = { id: string; estado: string; uuid_cfdi: string; motivo_rechazo: string | null }

type ImportResult = {
  total_filas: number
  creados: number
  actualizados: number
  claves_nuevas_catalogo: number
  claves_asignadas: number
  montos_reenlazados: number
  errores: { fila: number; motivo: string }[]
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

  // ── Estado import profesores ──────────────────────────────────────────────
  const xlsxRef = useRef<HTMLInputElement>(null)
  const [xlsxFile, setXlsxFile] = useState<File | null>(null)
  const [xlsxLoading, setXlsxLoading] = useState(false)
  const [xlsxResult, setXlsxResult] = useState<ImportResult | null>(null)
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

  // ── Handler import de profesores ──────────────────────────────────────────
  async function handleImportUpload() {
    if (!xlsxFile) return
    setXlsxLoading(true); setXlsxError(''); setXlsxResult(null)
    try {
      const data: ImportResult = await importarProfesores(xlsxFile)
      setXlsxResult(data)
      setXlsxFile(null)
    } catch (err: unknown) {
      setXlsxError(err instanceof Error ? err.message : 'Error al importar')
    } finally {
      setXlsxLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-8 max-w-3xl">
        <h2 className="text-2xl font-bold text-slate-800 mb-6">Cargar datos</h2>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-slate-100 rounded-lg p-1 w-fit">
          <button
            onClick={() => setTab('xml')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === 'xml' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Factura XML (CFDI 4.0)
          </button>
          <button
            onClick={() => setTab('excel')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === 'excel' ? 'bg-white text-slate-800 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            Importar profesores (Excel)
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

        {/* ── Tab Importar profesores ── */}
        {tab === 'excel' && (
          <div>
            <div className="mb-4 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-800 flex items-center justify-between gap-3">
              <div>
                <span className="font-semibold">Da de alta o actualiza profesores</span> desde un Excel.
                Columnas: <span className="font-mono text-xs">Nombre, RFC, Correo, Clave régimen emisor, Clave prod/serv, Concepto de servicio</span>.
                Empareja por RFC; el correo es opcional (si falta se pone un temporal).
              </div>
              <a
                href="/plantillas/Plantilla_Importar_Profesores.xlsx"
                download="Plantilla Importar Profesores.xlsx"
                className="shrink-0 bg-white border border-blue-300 hover:bg-blue-100 text-blue-800 text-xs font-medium px-3 py-1.5 rounded-lg transition-colors"
              >
                ↓ Plantilla
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
              <div className="text-4xl mb-3">{xlsxFile ? '📊' : '👥'}</div>
              {xlsxFile ? (
                <>
                  <p className="font-medium text-emerald-700">{xlsxFile.name}</p>
                  <p className="text-sm text-slate-400 mt-1">{(xlsxFile.size / 1024).toFixed(1)} KB</p>
                </>
              ) : (
                <>
                  <p className="font-medium text-slate-600">Haz clic para seleccionar el Excel de profesores</p>
                  <p className="text-sm text-slate-400 mt-1">Archivos .xlsx</p>
                </>
              )}
            </div>

            <div className="flex gap-3 mt-4">
              <button onClick={handleImportUpload} disabled={!xlsxFile || xlsxLoading}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white font-medium py-2.5 rounded-lg text-sm transition-colors">
                {xlsxLoading ? 'Importando…' : 'Importar profesores'}
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
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-emerald-700">{xlsxResult.creados}</p>
                    <p className="text-xs text-emerald-600 mt-1">Creados</p>
                  </div>
                  <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-blue-700">{xlsxResult.actualizados}</p>
                    <p className="text-xs text-blue-600 mt-1">Actualizados</p>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-slate-800">{xlsxResult.claves_asignadas}</p>
                    <p className="text-xs text-slate-500 mt-1">Claves asignadas</p>
                  </div>
                  <div className="bg-white border border-slate-200 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-slate-800">{xlsxResult.errores.length}</p>
                    <p className="text-xs text-slate-500 mt-1">Errores</p>
                  </div>
                </div>

                <p className="text-xs text-slate-500">
                  {xlsxResult.total_filas} filas · {xlsxResult.claves_nuevas_catalogo} clave(s) nueva(s) en catálogo · {xlsxResult.montos_reenlazados} monto(s) re-enlazado(s)
                </p>

                {xlsxResult.errores.length > 0 && (
                  <div className="bg-white rounded-xl border border-red-200 overflow-hidden">
                    <div className="px-4 py-3 border-b border-red-100 bg-red-50">
                      <p className="text-sm font-semibold text-red-700">Filas con error</p>
                    </div>
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 border-b border-slate-100">
                        <tr>
                          {['Fila', 'Motivo'].map(h => (
                            <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {xlsxResult.errores.map(e => (
                          <tr key={e.fila}>
                            <td className="px-4 py-2.5 text-slate-400 text-xs">{e.fila}</td>
                            <td className="px-4 py-2.5 text-red-700">{e.motivo}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}

                <button onClick={() => router.push('/profesores')}
                  className="text-sm text-blue-600 hover:underline">
                  Ver profesores →
                </button>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
