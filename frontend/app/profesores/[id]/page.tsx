'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import Sidebar from '@/components/Sidebar'
import {
  isAuthenticated,
  getCatalogo,
  getClavesByProfesor,
  asignarClave,
  removerClave,
  updateProfesor,
} from '@/lib/api'

// ── Tipos ─────────────────────────────────────────────────────────────────────

interface Profesor {
  id: string
  rfc: string
  nombre: string
  correo: string
  regimen_fiscal: string
  activo: boolean
}

interface CatalogoClave {
  id: string
  clave: string
  descripcion: string
  tipo: string
  activo: boolean
}

interface ClaveAsignada {
  id: string
  catalogo_clave_id: string
  clave: string
  descripcion: string
  tipo: string
}

// ── Constantes ────────────────────────────────────────────────────────────────

const REGIMENES = [
  { value: '626', label: '626 — RESICO' },
  { value: '612', label: '612 — PF Act. Empresariales y Profesionales' },
  { value: '603', label: '603 — PM Fines no Lucrativos' },
]

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

function authH(): HeadersInit {
  const t = typeof window !== 'undefined' ? localStorage.getItem('cfdi_token') : null
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function getProfesor(id: string): Promise<Profesor> {
  const res = await fetch(`${API}/api/v1/profesores/${id}`, { headers: authH() })
  if (!res.ok) throw new Error('No encontrado')
  return res.json()
}

// ── Componente ────────────────────────────────────────────────────────────────

export default function ProfesorDetallePage() {
  const router = useRouter()
  const { id } = useParams<{ id: string }>()

  const [profesor, setProfesor] = useState<Profesor | null>(null)
  const [catalogo, setCatalogo] = useState<CatalogoClave[]>([])
  const [asignadas, setAsignadas] = useState<ClaveAsignada[]>([])
  const [loading, setLoading] = useState(true)
  const [toggling, setToggling] = useState<string | null>(null)   // clave_id en proceso
  const [editando, setEditando] = useState(false)
  const [editForm, setEditForm] = useState({ nombre: '', correo: '', regimen_fiscal: '' })
  const [saveError, setSaveError] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    const [p, cat, asig] = await Promise.all([
      getProfesor(id),
      getCatalogo('servicio'),
      getClavesByProfesor(id),
    ])
    setProfesor(p)
    setCatalogo(cat)
    setAsignadas(asig)
    setLoading(false)
  }, [id])

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    load()
  }, [load, router])

  // ── Toggle de una clave ────────────────────────────────────────────────────

  async function toggleClave(claveId: string, estaAsignada: boolean) {
    setToggling(claveId)
    try {
      if (estaAsignada) {
        await removerClave(id, claveId)
      } else {
        await asignarClave(id, claveId)
      }
      // Refrescar solo las asignadas
      const actualizadas = await getClavesByProfesor(id)
      setAsignadas(actualizadas)
    } finally {
      setToggling(null)
    }
  }

  // ── Editar datos del profesor ──────────────────────────────────────────────

  function iniciarEdicion() {
    if (!profesor) return
    setEditForm({ nombre: profesor.nombre, correo: profesor.correo, regimen_fiscal: profesor.regimen_fiscal })
    setEditando(true)
    setSaveError('')
  }

  async function guardarEdicion(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setSaveError('')
    try {
      await updateProfesor(id, editForm)
      const updated = await getProfesor(id)
      setProfesor(updated)
      setEditando(false)
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Error al guardar')
    } finally {
      setSaving(false)
    }
  }

  // ── Estado de claves ──────────────────────────────────────────────────────

  const asignadasIds = new Set(asignadas.map(a => a.catalogo_clave_id))
  const tieneOverride = asignadas.length > 0
  const catalogoServicio = catalogo.filter(c => c.tipo === 'servicio')
  const catalogoUnidad = catalogo.filter(c => c.tipo === 'unidad')

  if (loading) return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 flex items-center justify-center">
        <p className="text-slate-400 text-sm">Cargando…</p>
      </main>
    </div>
  )

  if (!profesor) return null

  return (
    <div className="flex min-h-screen">
      <Sidebar />

      <main className="flex-1 p-8 max-w-4xl">

        {/* Breadcrumb */}
        <div className="mb-6">
          <Link href="/profesores" className="text-sm text-slate-500 hover:text-slate-700">
            ← Profesores
          </Link>
        </div>

        {/* ── Card datos del profesor ── */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 mb-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold text-slate-800">{profesor.nombre}</h2>
              <p className="text-sm font-mono text-slate-400 mt-0.5">{profesor.rfc}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                profesor.activo ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
              }`}>
                {profesor.activo ? 'Activo' : 'Inactivo'}
              </span>
              {!editando && (
                <button
                  onClick={iniciarEdicion}
                  className="text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  Editar
                </button>
              )}
            </div>
          </div>

          {editando ? (
            <form onSubmit={guardarEdicion} className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Nombre</label>
                <input
                  value={editForm.nombre}
                  onChange={e => setEditForm(f => ({ ...f, nombre: e.target.value }))}
                  required
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Correo</label>
                <input
                  type="email"
                  value={editForm.correo}
                  onChange={e => setEditForm(f => ({ ...f, correo: e.target.value }))}
                  required
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Régimen fiscal</label>
                <select
                  value={editForm.regimen_fiscal}
                  onChange={e => setEditForm(f => ({ ...f, regimen_fiscal: e.target.value }))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {REGIMENES.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
              {saveError && (
                <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {saveError}
                </p>
              )}
              <div className="col-span-2 flex gap-2">
                <button type="submit" disabled={saving}
                  className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                  {saving ? 'Guardando…' : 'Guardar cambios'}
                </button>
                <button type="button" onClick={() => setEditando(false)}
                  className="px-4 py-2 border border-slate-200 rounded-lg text-sm text-slate-600 hover:bg-slate-50 transition-colors">
                  Cancelar
                </button>
              </div>
            </form>
          ) : (
            <dl className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <dt className="text-xs text-slate-400 uppercase tracking-wide font-medium mb-0.5">Correo</dt>
                <dd className="text-slate-700">{profesor.correo}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400 uppercase tracking-wide font-medium mb-0.5">Régimen fiscal</dt>
                <dd className="text-slate-700">
                  {REGIMENES.find(r => r.value === profesor.regimen_fiscal)?.label ?? profesor.regimen_fiscal}
                </dd>
              </div>
            </dl>
          )}
        </div>

        {/* ── Sección claves SAT ── */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-slate-100">
            <h3 className="font-semibold text-slate-800">Claves SAT autorizadas</h3>
            <p className="text-xs text-slate-500 mt-1">
              {tieneOverride
                ? `Este profesor tiene ${asignadas.length} clave${asignadas.length !== 1 ? 's' : ''} específica${asignadas.length !== 1 ? 's' : ''} asignada${asignadas.length !== 1 ? 's' : ''}. Solo estas serán válidas en sus facturas.`
                : 'Sin asignaciones específicas — se permiten todas las claves activas del catálogo global.'}
            </p>
          </div>

          {/* Claves de servicio */}
          <div className="px-6 py-5">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
              Claves de producto / servicio
            </p>

            {catalogoServicio.length === 0 ? (
              <p className="text-sm text-slate-400 italic">No hay claves de servicio en el catálogo.</p>
            ) : (
              <div className="space-y-2">
                {catalogoServicio.map(cat => {
                  const asignada = asignadasIds.has(cat.id)
                  const enProceso = toggling === cat.id
                  return (
                    <label
                      key={cat.id}
                      className={`flex items-center gap-4 p-3 rounded-lg border cursor-pointer transition-colors select-none ${
                        asignada
                          ? 'border-blue-200 bg-blue-50'
                          : 'border-slate-100 hover:border-slate-200 hover:bg-slate-50'
                      } ${enProceso ? 'opacity-50 pointer-events-none' : ''}`}
                    >
                      <input
                        type="checkbox"
                        checked={asignada}
                        onChange={() => toggleClave(cat.id, asignada)}
                        className="h-4 w-4 rounded text-blue-600 border-slate-300 focus:ring-blue-500"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-sm font-semibold text-slate-700">{cat.clave}</span>
                          {asignada && (
                            <span className="text-xs bg-blue-600 text-white px-1.5 py-0.5 rounded font-medium">
                              Asignada
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5 truncate">{cat.descripcion}</p>
                      </div>
                      {enProceso && (
                        <span className="text-xs text-slate-400 shrink-0">Guardando…</span>
                      )}
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          {/* Claves de unidad — solo informativo, no son override */}
          {catalogoUnidad.length > 0 && (
            <div className="px-6 pb-5 border-t border-slate-100 pt-5">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">
                Claves de unidad válidas (globales, no configurables por profesor)
              </p>
              <div className="flex gap-2 flex-wrap">
                {catalogoUnidad.map(c => (
                  <span key={c.id} className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 text-slate-600 text-xs">
                    <span className="font-mono font-semibold">{c.clave}</span>
                    <span className="text-slate-400">·</span>
                    <span>{c.descripcion}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Nota informativa sobre la lógica */}
          <div className="px-6 py-4 bg-amber-50 border-t border-amber-100">
            <p className="text-xs text-amber-700">
              <span className="font-semibold">¿Cómo funciona?</span>{' '}
              Si marcas al menos una clave, el validador solo aceptará esas claves en las facturas de este profesor.
              Si no marcas ninguna, se permiten todas las claves activas del catálogo.
            </p>
          </div>
        </div>

      </main>
    </div>
  )
}
