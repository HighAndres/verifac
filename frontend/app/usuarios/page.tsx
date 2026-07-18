'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { getUsuarios, createUsuario, updateUsuario, deleteUsuario, isSuperAdmin } from '@/lib/api'

interface Usuario {
  id: string
  username: string
  nombre: string
  rol: string
  activo: boolean
  ultimo_acceso: string | null
  created_at: string
}

const ROL_LABELS: Record<string, string> = {
  superadmin: 'Super Admin',
  revisor: 'Revisor',
}

const emptyForm = { username: '', nombre: '', password: '', rol: 'revisor' }

export default function UsuariosPage() {
  const router = useRouter()
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [editId, setEditId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!isSuperAdmin()) { router.push('/facturas'); return }
    load()
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function load() {
    setLoading(true)
    try { setUsuarios(await getUsuarios()) }
    finally { setLoading(false) }
  }

  function iniciarNuevo() {
    setEditId(null); setForm(emptyForm); setError(''); setShowForm(true)
  }

  function iniciarEdicion(u: Usuario) {
    setEditId(u.id)
    setForm({ username: u.username, nombre: u.nombre, password: '', rol: u.rol })
    setError(''); setShowForm(true)
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      if (editId) {
        const payload: Record<string, string> = { nombre: form.nombre, rol: form.rol }
        if (form.password) payload.password = form.password
        await updateUsuario(editId, payload)
      } else {
        await createUsuario(form)
      }
      setShowForm(false); setEditId(null)
      await load()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error al guardar')
    } finally { setSaving(false) }
  }

  async function toggleActivo(u: Usuario) {
    await updateUsuario(u.id, { activo: !u.activo })
    await load()
  }

  async function eliminar(u: Usuario) {
    if (!confirm(`¿Eliminar permanentemente al usuario "${u.username}"?`)) return
    try { await deleteUsuario(u.id); await load() }
    catch (err: unknown) { alert(err instanceof Error ? err.message : 'Error') }
  }

  const fmtDate = (v: string | null) =>
    v ? new Date(v).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' }) : '—'

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8 max-w-4xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Usuarios</h2>
            <p className="text-sm text-slate-500 mt-0.5">{usuarios.length} registro{usuarios.length !== 1 ? 's' : ''}</p>
          </div>
          <button onClick={iniciarNuevo}
            className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
            + Nuevo usuario
          </button>
        </div>

        {showForm && (
          <div className="mb-6 bg-white border border-slate-200 rounded-xl p-6">
            <h3 className="font-semibold text-slate-700 mb-4">
              {editId ? 'Editar usuario' : 'Nuevo usuario'}
            </h3>
            <form onSubmit={guardar} className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Username</label>
                <input value={form.username} onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                  required disabled={!!editId} placeholder="jperez"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-50 disabled:text-slate-400" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Nombre completo</label>
                <input value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
                  required placeholder="Juan Pérez"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Contraseña {editId && <span className="text-slate-400">(dejar vacío para no cambiar)</span>}
                </label>
                <input type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  required={!editId} placeholder="••••••••"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Rol</label>
                <select value={form.rol} onChange={e => setForm(f => ({ ...f, rol: e.target.value }))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="revisor">Revisor — opera la validación</option>
                  <option value="superadmin">Super Admin — acceso total</option>
                </select>
              </div>
              {error && (
                <p className="col-span-2 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">{error}</p>
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

        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          {loading ? (
            <p className="text-slate-400 text-sm text-center py-16">Cargando…</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  {['Usuario', 'Nombre', 'Rol', 'Último acceso', 'Estado', ''].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {usuarios.map(u => (
                  <tr key={u.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono font-medium text-slate-700">{u.username}</td>
                    <td className="px-4 py-3">{u.nombre}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.rol === 'superadmin' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                      }`}>{ROL_LABELS[u.rol] ?? u.rol}</span>
                    </td>
                    <td className="px-4 py-3 text-slate-500 text-xs">{fmtDate(u.ultimo_acceso)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.activo ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'
                      }`}>{u.activo ? 'Activo' : 'Inactivo'}</span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <button onClick={() => iniciarEdicion(u)}
                          className="text-xs text-blue-500 hover:text-blue-700 font-medium">Editar</button>
                        <button onClick={() => toggleActivo(u)}
                          className="text-xs text-slate-400 hover:text-slate-600">
                          {u.activo ? 'Desactivar' : 'Activar'}
                        </button>
                        <button onClick={() => eliminar(u)}
                          className="text-xs text-red-400 hover:text-red-600 font-medium">Eliminar</button>
                      </div>
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
