'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useToast } from '@/components/Toast'
import {
  getUsuarios, createUsuario, updateUsuario, deleteUsuario, getProfesores, isSuperAdmin,
  generarCredencialesProfesores, enviarCredenciales,
} from '@/lib/api'

interface DetalleCredencial {
  nombre: string
  rfc: string
  correo?: string
  motivo?: string
}

interface ResultadoCredenciales {
  creados: number
  errores: number
  omitidos: number
  detalle_creados: DetalleCredencial[]
  detalle_errores: DetalleCredencial[]
  detalle_omitidos: DetalleCredencial[]
}

interface Usuario {
  id: string
  username: string
  nombre: string
  correo: string | null
  rol: string
  profesor_id: string | null
  activo: boolean
  ultimo_acceso: string | null
  created_at: string
}

interface ProfesorOpcion {
  id: string
  nombre: string
  rfc: string
}

const ROL_LABELS: Record<string, string> = {
  superadmin: 'Super Admin',
  revisor: 'Revisor',
  consulta: 'Consulta',
  profesor: 'Profesor',
}

const emptyForm = { username: '', nombre: '', password: '', correo: '', rol: 'revisor', profesor_id: '' }

export default function UsuariosPage() {
  const router = useRouter()
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [profesores, setProfesores] = useState<ProfesorOpcion[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(emptyForm)
  const [editId, setEditId] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [mostrarPassword, setMostrarPassword] = useState(false)
  const [generando, setGenerando] = useState(false)
  const [resultadoCred, setResultadoCred] = useState<ResultadoCredenciales | null>(null)
  const [enviandoId, setEnviandoId] = useState<string | null>(null)
  const toast = useToast()

  useEffect(() => {
    if (!isSuperAdmin()) { router.push('/facturas'); return }
    load()
    getProfesores({ limit: '100', activo: 'true' })
      .then(data => setProfesores(data.items))
      .catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function load() {
    setLoading(true)
    try { setUsuarios(await getUsuarios()) }
    finally { setLoading(false) }
  }

  function iniciarNuevo() {
    setEditId(null); setForm(emptyForm); setError(''); setMostrarPassword(false); setShowForm(true)
  }

  function iniciarEdicion(u: Usuario) {
    setEditId(u.id)
    setForm({ username: u.username, nombre: u.nombre, password: '', correo: u.correo ?? '', rol: u.rol, profesor_id: u.profesor_id ?? '' })
    setError(''); setMostrarPassword(false); setShowForm(true)
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true); setError('')
    try {
      // profesor_id solo aplica al rol profesor; en otros roles se manda null para limpiarlo.
      const profesorId = form.rol === 'profesor' ? (form.profesor_id || null) : null
      if (editId) {
        const payload: Record<string, unknown> = { nombre: form.nombre, rol: form.rol, profesor_id: profesorId }
        // correo solo si cambió: así se puede editar (p.ej. cambiar contraseña) un
        // usuario que aún no tiene correo real capturado.
        const correoOriginal = usuarios.find(u => u.id === editId)?.correo ?? ''
        if (form.correo.trim().toLowerCase() !== correoOriginal.trim().toLowerCase()) payload.correo = form.correo || null
        if (form.password) payload.password = form.password
        await updateUsuario(editId, payload)
      } else {
        await createUsuario({
          username: form.username,
          nombre: form.nombre,
          correo: form.correo || null,
          password: form.password,
          rol: form.rol,
          profesor_id: profesorId,
        })
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

  async function generarCredenciales() {
    if (!confirm(
      'Se creará una cuenta (rol Profesor) para cada profesor activo con correo real que aún no tenga acceso, ' +
      'y se le enviará su contraseña por correo.\n\n¿Continuar?'
    )) return
    setGenerando(true); setResultadoCred(null)
    try {
      const res: ResultadoCredenciales = await generarCredencialesProfesores()
      setResultadoCred(res)
      if (res.creados > 0) toast(`Credenciales enviadas a ${res.creados} profesor${res.creados !== 1 ? 'es' : ''}`, 'success')
      else if (res.errores === 0) toast('No hay profesores pendientes de cuenta', 'info')
      if (res.errores > 0) toast(`${res.errores} envío${res.errores !== 1 ? 's' : ''} con error`, 'error')
      await load()
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al generar credenciales', 'error')
    } finally { setGenerando(false) }
  }

  async function reenviarCredenciales(u: Usuario) {
    if (!confirm(
      `Se generará una contraseña NUEVA para "${u.username}" (la actual dejará de funcionar) ` +
      `y se enviará a ${u.correo || 'su correo'}.\n\n¿Continuar?`
    )) return
    setEnviandoId(u.id)
    try {
      const res = await enviarCredenciales(u.id)
      toast(`Credenciales enviadas a ${res.enviado_a}`, 'success')
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al enviar credenciales', 'error')
    } finally { setEnviandoId(null) }
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
      <main className="flex-1 p-8 max-w-6xl">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-800">Usuarios</h2>
            <p className="text-sm text-slate-500 mt-0.5">{usuarios.length} registro{usuarios.length !== 1 ? 's' : ''}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={generarCredenciales} disabled={generando}
              title="Crea cuentas para los profesores activos sin acceso y les envía su contraseña por correo"
              className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
              {generando ? 'Enviando…' : '✉ Credenciales a profesores'}
            </button>
            <button onClick={iniciarNuevo}
              className="bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
              + Nuevo usuario
            </button>
          </div>
        </div>

        {resultadoCred && (
          <div className="mb-6 bg-white border border-slate-200 rounded-xl p-5 text-sm">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-slate-700">Resultado del envío de credenciales</h3>
              <button onClick={() => setResultadoCred(null)} className="text-xs text-slate-400 hover:text-slate-600">Cerrar</button>
            </div>
            <p className="text-slate-600 mb-2">
              <span className="font-medium text-emerald-700">{resultadoCred.creados} enviadas</span>
              {' · '}<span className={resultadoCred.errores ? 'font-medium text-red-600' : ''}>{resultadoCred.errores} con error</span>
              {' · '}{resultadoCred.omitidos} omitidos
            </p>
            {resultadoCred.detalle_creados.length > 0 && (
              <p className="text-xs text-slate-500 mb-1">
                <span className="font-medium text-slate-600">Enviadas:</span>{' '}
                {resultadoCred.detalle_creados.map(d => `${d.nombre} (${d.correo})`).join(' · ')}
              </p>
            )}
            {resultadoCred.detalle_errores.length > 0 && (
              <p className="text-xs text-red-600 mb-1">
                <span className="font-medium">Errores:</span>{' '}
                {resultadoCred.detalle_errores.map(d => `${d.nombre}: ${d.motivo}`).join(' · ')}
              </p>
            )}
            {resultadoCred.detalle_omitidos.length > 0 && (
              <p className="text-xs text-slate-400">
                <span className="font-medium text-slate-500">Omitidos:</span>{' '}
                {resultadoCred.detalle_omitidos.map(d => `${d.nombre}: ${d.motivo}`).join(' · ')}
              </p>
            )}
          </div>
        )}

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
                  Correo <span className="text-slate-400">(credencial de acceso)</span>
                </label>
                <input type="email" value={form.correo} onChange={e => setForm(f => ({ ...f, correo: e.target.value }))}
                  required={!editId} placeholder="juan@thehumantalent.com"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  Contraseña {editId && <span className="text-slate-400">(dejar vacío para no cambiar)</span>}
                </label>
                <div className="relative">
                  <input type={mostrarPassword ? 'text' : 'password'} value={form.password}
                    onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                    required={!editId} placeholder="••••••••"
                    className="w-full border border-slate-300 rounded-lg pl-3 pr-9 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                  <button type="button" onClick={() => setMostrarPassword(v => !v)}
                    tabIndex={-1}
                    title={mostrarPassword ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
                    {mostrarPassword ? (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-10-8-10-8a18.5 18.5 0 0 1 4.22-5.94M9.9 4.24A10.4 10.4 0 0 1 12 4c7 0 10 8 10 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                        <path d="m1 1 22 22" />
                      </svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M2 12s3-8 10-8 10 8 10 8-3 8-10 8-10-8-10-8Z" />
                        <circle cx="12" cy="12" r="3" />
                      </svg>
                    )}
                  </button>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Rol</label>
                <select value={form.rol} onChange={e => setForm(f => ({ ...f, rol: e.target.value }))}
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="revisor">Revisor — opera la validación</option>
                  <option value="superadmin">Super Admin — acceso total</option>
                  <option value="consulta">Consulta — solo lectura, descarga reportes</option>
                  <option value="profesor">Profesor — solo su portal de consulta</option>
                </select>
              </div>
              {form.rol === 'profesor' && (
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-slate-600 mb-1">Profesor ligado</label>
                  <select value={form.profesor_id} onChange={e => setForm(f => ({ ...f, profesor_id: e.target.value }))}
                    required
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="">— Selecciona un profesor —</option>
                    {profesores.map(p => (
                      <option key={p.id} value={p.id}>{p.nombre} · {p.rfc}</option>
                    ))}
                  </select>
                  <p className="text-xs text-slate-400 mt-1">El portal mostrará solo las facturas de este profesor.</p>
                </div>
              )}
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

        <div className="bg-white rounded-xl border border-slate-200 overflow-x-auto">
          {loading ? (
            <p className="text-slate-400 text-sm text-center py-16">Cargando…</p>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-slate-50 border-b border-slate-200">
                <tr>
                  {['Usuario', 'Nombre', 'Correo', 'Rol', 'Último acceso', 'Estado', ''].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {usuarios.map(u => (
                  <tr key={u.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono font-medium text-slate-700">{u.username}</td>
                    <td className="px-4 py-3">{u.nombre}</td>
                    <td className="px-4 py-3 text-slate-600 text-xs">{u.correo || <span className="text-slate-300">—</span>}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                        u.rol === 'superadmin' ? 'bg-purple-100 text-purple-700'
                          : u.rol === 'profesor' ? 'bg-teal-100 text-teal-700'
                          : u.rol === 'consulta' ? 'bg-amber-100 text-amber-700'
                          : 'bg-blue-100 text-blue-700'
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
                        {u.correo && !u.correo.endsWith('@pendiente.local') && (
                          <button onClick={() => reenviarCredenciales(u)} disabled={enviandoId === u.id}
                            title="Genera una contraseña nueva y la envía a su correo"
                            className="text-xs text-emerald-600 hover:text-emerald-800 font-medium disabled:opacity-50">
                            {enviandoId === u.id ? 'Enviando…' : 'Enviar credenciales'}
                          </button>
                        )}
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
