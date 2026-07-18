'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { getProfesores, createProfesor, isAuthenticated } from '@/lib/api'
import { useToast } from '@/components/Toast'

interface Profesor {
  id: string
  rfc: string
  nombre: string
  correo: string
  regimen_fiscal: string
  activo: boolean
  created_at: string
}

const REGIMENES = [
  { value: '626', label: '626 — RESICO' },
  { value: '612', label: '612 — PF Act. Empresariales y Profesionales' },
  { value: '603', label: '603 — PM Fines no Lucrativos' },
]

const emptyForm = { rfc: '', nombre: '', correo: '', regimen_fiscal: '612' }

export default function ProfesoresPage() {
  const router = useRouter()
  const toast = useToast()
  const [profesores, setProfesores] = useState<Profesor[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function load(q = busqueda) {
    setLoading(true)
    try {
      const params: Record<string, string> = {}
      if (q) params.q = q
      const data = await getProfesores(params)
      setProfesores(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setFormError('')
    try {
      await createProfesor(form)
      setShowForm(false)
      setForm(emptyForm)
      toast('Profesor agregado correctamente')
      await load()
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  const regimenLabel = (v: string) => REGIMENES.find(r => r.value === v)?.label ?? v

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-8">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Profesores</h2>
            <p className="text-sm text-slate-500 mt-0.5">{total} registro{total !== 1 ? 's' : ''}</p>
          </div>
          <div className="flex gap-2">
            <form onSubmit={e => { e.preventDefault(); load(busqueda) }} className="flex gap-2">
              <input value={busqueda} onChange={e => setBusqueda(e.target.value)}
                placeholder="Buscar RFC o nombre…"
                className="border border-slate-200 rounded-lg px-3 py-2 text-sm w-44 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <button type="submit"
                className="px-3 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50">
                Buscar
              </button>
            </form>
            <button onClick={() => { setShowForm(true); setFormError('') }}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
              + Nuevo profesor
            </button>
          </div>
        </div>

        {/* Formulario nuevo */}
        {showForm && (
          <div className="mb-6 bg-white border border-slate-200 rounded-xl p-6">
            <h3 className="font-semibold text-slate-700 mb-4">Nuevo profesor</h3>
            <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">RFC</label>
                <input
                  value={form.rfc} onChange={e => setForm(f => ({ ...f, rfc: e.target.value.toUpperCase() }))}
                  required maxLength={13} placeholder="GAMA800101ABC"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Nombre completo</label>
                <input
                  value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
                  required placeholder="Ana Martínez García"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Correo</label>
                <input
                  type="email" value={form.correo} onChange={e => setForm(f => ({ ...f, correo: e.target.value }))}
                  required placeholder="ana@gmail.com"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Régimen fiscal</label>
                <select
                  value={form.regimen_fiscal} onChange={e => setForm(f => ({ ...f, regimen_fiscal: e.target.value }))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {REGIMENES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>

              {formError && (
                <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {formError}
                </p>
              )}

              <div className="col-span-2 flex gap-2 pt-1">
                <button type="submit" disabled={saving}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                  {saving ? 'Guardando…' : 'Guardar'}
                </button>
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                  Cancelar
                </button>
              </div>
            </form>
          </div>
        )}

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {loading ? (
            <p className="text-slate-500 text-sm text-center py-16">Cargando…</p>
          ) : profesores.length === 0 ? (
            <p className="text-slate-500 text-sm text-center py-16">Sin profesores registrados.</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-slate-200 bg-slate-50">
                <tr>
                  {['RFC', 'Nombre', 'Correo', 'Régimen', 'Estado', ''].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {profesores.map(p => (
                  <tr
                    key={p.id}
                    onClick={() => router.push(`/profesores/${p.id}`)}
                    className="hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-mono font-medium text-xs">{p.rfc}</td>
                    <td className="px-4 py-3 font-medium">{p.nombre}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{p.correo}</td>
                    <td className="px-4 py-3 text-xs">{regimenLabel(p.regimen_fiscal)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        p.activo ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'
                      }`}>
                        {p.activo ? 'Activo' : 'Inactivo'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-xs text-blue-500 font-medium">
                        Gestionar claves →
                      </span>
                    </td>
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
