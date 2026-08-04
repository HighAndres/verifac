'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { getCatalogo, isAuthenticated } from '@/lib/api'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

function authH(): HeadersInit {
  const t = typeof window !== 'undefined' ? localStorage.getItem('cfdi_token') : null
  return t ? { Authorization: `Bearer ${t}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

interface Clave {
  id: string
  clave: string
  descripcion: string
  tipo: string
  activo: boolean
  created_at: string
}

const emptyForm = { clave: '', descripcion: '', tipo: 'servicio', activo: true }

export default function CatalogoPage() {
  const router = useRouter()
  const [claves, setClaves] = useState<Clave[]>([])
  const [loading, setLoading] = useState(true)
  const [filtroTipo, setFiltroTipo] = useState<string>('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [editId, setEditId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  const [showLote, setShowLote] = useState(false)
  const [loteTipo, setLoteTipo] = useState('servicio')
  const [loteTexto, setLoteTexto] = useState('')
  const [loteSaving, setLoteSaving] = useState(false)
  const [loteResultado, setLoteResultado] = useState('')
  const [loteError, setLoteError] = useState('')

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    load()
  }, [filtroTipo]) // eslint-disable-line react-hooks/exhaustive-deps

  async function load() {
    setLoading(true)
    try {
      const data = await getCatalogo(filtroTipo || undefined)
      setClaves(data)
    } finally {
      setLoading(false)
    }
  }

  function iniciarNueva() {
    setShowLote(false)
    setEditId(null)
    setForm(emptyForm)
    setError('')
    setShowForm(true)
  }

  function iniciarEdicion(c: Clave) {
    setShowLote(false)
    setEditId(c.id)
    setForm({ clave: c.clave, descripcion: c.descripcion, tipo: c.tipo, activo: c.activo })
    setError('')
    setShowForm(true)
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      if (editId) {
        // PATCH — solo campos editables (no clave)
        const res = await fetch(`${API}/api/v1/catalogo-claves/${editId}`, {
          method: 'PATCH',
          headers: authH(),
          body: JSON.stringify({ descripcion: form.descripcion, tipo: form.tipo, activo: form.activo }),
        })
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail) }
      } else {
        // POST — nueva clave
        const res = await fetch(`${API}/api/v1/catalogo-claves`, {
          method: 'POST',
          headers: authH(),
          body: JSON.stringify(form),
        })
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail) }
      }
      setShowForm(false)
      setEditId(null)
      await load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  function iniciarLote() {
    setShowForm(false)
    setLoteTexto('')
    setLoteResultado('')
    setLoteError('')
    setShowLote(true)
  }

  async function guardarLote(e: React.FormEvent) {
    e.preventDefault()
    const items = loteTexto
      .split('\n')
      .map(linea => linea.trim())
      .filter(Boolean)
      .map(linea => {
        const idx = linea.indexOf(',')
        const clave = (idx === -1 ? linea : linea.slice(0, idx)).trim()
        const descripcion = (idx === -1 ? '' : linea.slice(idx + 1)).trim()
        return { clave, descripcion: descripcion || clave, tipo: loteTipo, activo: true }
      })
    if (items.length === 0) { setLoteError('Pega al menos una clave.'); return }

    setLoteSaving(true)
    setLoteError('')
    setLoteResultado('')
    try {
      const res = await fetch(`${API}/api/v1/catalogo-claves/lote`, {
        method: 'POST',
        headers: authH(),
        body: JSON.stringify({ items }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Error al cargar el lote')
      const partes = [`${data.creadas} clave${data.creadas === 1 ? '' : 's'} agregada${data.creadas === 1 ? '' : 's'}`]
      if (data.existentes > 0) partes.push(`${data.existentes} ya existían (omitidas)`)
      if (data.errores?.length > 0) partes.push(`${data.errores.length} con error: ${data.errores.join('; ')}`)
      setLoteResultado(partes.join(' — '))
      setLoteTexto('')
      await load()
    } catch (err: unknown) {
      setLoteError(err instanceof Error ? err.message : 'Error al cargar el lote')
    } finally {
      setLoteSaving(false)
    }
  }

  async function toggleActivo(c: Clave) {
    await fetch(`${API}/api/v1/catalogo-claves/${c.id}`, {
      method: 'PATCH',
      headers: authH(),
      body: JSON.stringify({ activo: !c.activo }),
    })
    await load()
  }

  const servicios = claves.filter(c => c.tipo === 'servicio')
  const unidades = claves.filter(c => c.tipo === 'unidad')

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-8 max-w-4xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Catálogo SAT</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Claves globales del SAT — se aplican a todos los profesores salvo que tengan asignación específica
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={iniciarLote}
              className="bg-white border border-slate-200 hover:border-slate-400 text-slate-700 text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              Cargar varias
            </button>
            <button
              onClick={iniciarNueva}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
            >
              + Nueva clave
            </button>
          </div>
        </div>

        {/* Carga en lote */}
        {showLote && (
          <div className="mb-6 bg-white border border-slate-200 rounded-xl p-6">
            <h3 className="font-semibold text-slate-700 mb-1">Cargar varias claves</h3>
            <p className="text-xs text-slate-500 mb-4">
              Una clave por línea, formato <code className="bg-slate-100 px-1 rounded">clave,descripción</code>.
              Las que ya existan en el catálogo se omiten automáticamente.
            </p>
            <form onSubmit={guardarLote} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Tipo (aplica a todas las líneas)</label>
                <select
                  value={loteTipo}
                  onChange={e => setLoteTipo(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="servicio">Servicio (ClaveProdServ)</option>
                  <option value="unidad">Unidad (ClaveUnidad)</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Claves</label>
                <textarea
                  value={loteTexto}
                  onChange={e => setLoteTexto(e.target.value)}
                  rows={6}
                  placeholder={'90141702,Servicios de enseñanza universitaria y de posgrado\n90141500,Servicios de instrucción\n86131500,Servicios de investigación educativa'}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              {loteError && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{loteError}</p>
              )}
              {loteResultado && (
                <p className="text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">{loteResultado}</p>
              )}
              <div className="flex gap-2">
                <button type="submit" disabled={loteSaving}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                  {loteSaving ? 'Cargando…' : 'Cargar todas'}
                </button>
                <button type="button" onClick={() => setShowLote(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                  Cerrar
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Formulario alta / edición */}
        {showForm && (
          <div className="mb-6 bg-white border border-slate-200 rounded-xl p-6">
            <h3 className="font-semibold text-slate-700 mb-4">
              {editId ? 'Editar clave' : 'Nueva clave SAT'}
            </h3>
            <form onSubmit={guardar} className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Clave SAT {editId && <span className="text-slate-400">(no editable)</span>}
                </label>
                <input
                  value={form.clave}
                  onChange={e => setForm(f => ({ ...f, clave: e.target.value }))}
                  required
                  disabled={!!editId}
                  placeholder="90141702"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-400"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Tipo</label>
                <select
                  value={form.tipo}
                  onChange={e => setForm(f => ({ ...f, tipo: e.target.value }))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="servicio">Servicio (ClaveProdServ)</option>
                  <option value="unidad">Unidad (ClaveUnidad)</option>
                </select>
              </div>

              <div className="col-span-2">
                <label className="block text-xs font-medium text-slate-600 mb-1">Descripción</label>
                <input
                  value={form.descripcion}
                  onChange={e => setForm(f => ({ ...f, descripcion: e.target.value }))}
                  required
                  placeholder="Servicios de enseñanza universitaria y de posgrado"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>

              {editId && (
                <div className="col-span-2 flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="activo"
                    checked={form.activo}
                    onChange={e => setForm(f => ({ ...f, activo: e.target.checked }))}
                    className="h-4 w-4 rounded text-blue-600"
                  />
                  <label htmlFor="activo" className="text-sm text-slate-600">Activa</label>
                </div>
              )}

              {error && (
                <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <div className="col-span-2 flex gap-2">
                <button type="submit" disabled={saving}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                  {saving ? 'Guardando…' : 'Guardar'}
                </button>
                <button type="button" onClick={() => { setShowForm(false); setEditId(null) }}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Filtro */}
        <div className="flex gap-2 mb-5">
          {[['', 'Todas'], ['servicio', 'Servicio'], ['unidad', 'Unidad']].map(([val, label]) => (
            <button key={val} onClick={() => setFiltroTipo(val)}
              className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                filtroTipo === val
                  ? 'bg-blue-600 text-white'
                  : 'bg-white border border-slate-200 text-slate-600 hover:border-slate-400'
              }`}>
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <p className="text-slate-400 text-sm text-center py-16">Cargando…</p>
        ) : (
          <div className="space-y-6">
            {/* Claves de servicio */}
            {(!filtroTipo || filtroTipo === 'servicio') && (
              <section>
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
                  Claves de producto / servicio — ClaveProdServ ({servicios.length})
                </h3>
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  {servicios.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-8">Sin claves de servicio.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 border-b border-slate-100">
                        <tr>
                          {['Clave SAT', 'Descripción', 'Estado', ''].map(h => (
                            <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {servicios.map(c => (
                          <tr key={c.id} className="hover:bg-slate-50">
                            <td className="px-4 py-3 font-mono font-semibold text-slate-700">{c.clave}</td>
                            <td className="px-4 py-3 text-slate-600">{c.descripcion}</td>
                            <td className="px-4 py-3">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                c.activo ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'
                              }`}>
                                {c.activo ? 'Activa' : 'Inactiva'}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right">
                              <div className="flex items-center justify-end gap-3">
                                <button onClick={() => iniciarEdicion(c)}
                                  className="text-xs text-blue-500 hover:text-blue-700 font-medium">
                                  Editar
                                </button>
                                <button onClick={() => toggleActivo(c)}
                                  className="text-xs text-slate-400 hover:text-slate-600">
                                  {c.activo ? 'Desactivar' : 'Activar'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </section>
            )}

            {/* Claves de unidad */}
            {(!filtroTipo || filtroTipo === 'unidad') && (
              <section>
                <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
                  Claves de unidad — ClaveUnidad ({unidades.length})
                </h3>
                <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
                  {unidades.length === 0 ? (
                    <p className="text-sm text-slate-400 text-center py-8">Sin claves de unidad.</p>
                  ) : (
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 border-b border-slate-100">
                        <tr>
                          {['Clave SAT', 'Descripción', 'Estado', ''].map(h => (
                            <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-slate-400 uppercase tracking-wide">{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-50">
                        {unidades.map(c => (
                          <tr key={c.id} className="hover:bg-slate-50">
                            <td className="px-4 py-3 font-mono font-semibold text-slate-700">{c.clave}</td>
                            <td className="px-4 py-3 text-slate-600">{c.descripcion}</td>
                            <td className="px-4 py-3">
                              <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                c.activo ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'
                              }`}>
                                {c.activo ? 'Activa' : 'Inactiva'}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-right">
                              <div className="flex items-center justify-end gap-3">
                                <button onClick={() => iniciarEdicion(c)}
                                  className="text-xs text-blue-500 hover:text-blue-700 font-medium">
                                  Editar
                                </button>
                                <button onClick={() => toggleActivo(c)}
                                  className="text-xs text-slate-400 hover:text-slate-600">
                                  {c.activo ? 'Desactivar' : 'Activar'}
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </div>
              </section>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
