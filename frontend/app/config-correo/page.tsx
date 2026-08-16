'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import { useToast } from '@/components/Toast'
import { getWatcherConfig, updateWatcherConfig, getCargaXml, actualizarCargaXml, isAuthenticated, isSuperAdmin } from '@/lib/api'

interface Config {
  imap_host: string
  imap_port: number
  imap_user: string
  imap_folder: string
  poll_minutos: number
  remitentes_permitidos: string | null
  auto_activo: boolean
  confirmaciones_activas: boolean
  password_configurado: boolean
}

export default function ConfigCorreoPage() {
  const router = useRouter()
  const toast = useToast()
  const [cfg, setCfg] = useState<Config | null>(null)
  const [saving, setSaving] = useState(false)
  const [cargaXmlActiva, setCargaXmlActiva] = useState<boolean | null>(null)
  const [savingCargaXml, setSavingCargaXml] = useState(false)

  useEffect(() => {
    if (!isAuthenticated()) { router.push('/login'); return }
    if (!isSuperAdmin()) { router.push('/correo'); return }
    getWatcherConfig().then(setCfg).catch(() => toast('No se pudo cargar la configuración', 'error'))
    getCargaXml().then(r => setCargaXmlActiva(r.carga_xml_portal_activa)).catch(() => {})
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  async function toggleCargaXml() {
    if (cargaXmlActiva === null) return
    const nuevo = !cargaXmlActiva
    setSavingCargaXml(true)
    try {
      const res = await actualizarCargaXml(nuevo)
      setCargaXmlActiva(res.carga_xml_portal_activa)
      toast(`Carga de facturas del portal ${res.carga_xml_portal_activa ? 'activada' : 'desactivada'}`, 'success')
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al guardar', 'error')
    } finally {
      setSavingCargaXml(false)
    }
  }

  function set<K extends keyof Config>(k: K, v: Config[K]) {
    setCfg(c => (c ? { ...c, [k]: v } : c))
  }

  async function handleSave() {
    if (!cfg) return
    setSaving(true)
    try {
      const res = await updateWatcherConfig({
        imap_host: cfg.imap_host,
        imap_port: Number(cfg.imap_port),
        imap_user: cfg.imap_user,
        imap_folder: cfg.imap_folder,
        poll_minutos: Number(cfg.poll_minutos),
        remitentes_permitidos: cfg.remitentes_permitidos,
        auto_activo: cfg.auto_activo,
        confirmaciones_activas: cfg.confirmaciones_activas,
      })
      setCfg(res)
      toast('Configuración de correo guardada', 'success')
    } catch (err: unknown) {
      toast(err instanceof Error ? err.message : 'Error al guardar', 'error')
    } finally {
      setSaving(false)
    }
  }

  const label = 'block text-sm font-medium text-slate-700 mb-1'
  const input = 'w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500'

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 p-8 max-w-2xl">
        <div className="mb-6">
          <h2 className="text-2xl font-bold text-slate-800">Configuración de correo</h2>
          <p className="text-sm text-slate-500 mt-0.5">
            Buzón IMAP del que Verifac lee las facturas. Solo super admin.
          </p>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-6 mb-6">
          <h3 className="text-sm font-semibold text-slate-700 mb-1">Carga de facturas (portal)</h3>
          <p className="text-xs text-slate-400 mb-4">
            Apaga esto para que ningún profesor pueda subir su factura desde el portal — útil para
            cerrar la recepción del mes o durante mantenimiento. No afecta la carga manual desde
            Facturas ni el correo.
          </p>
          {cargaXmlActiva === null ? (
            <p className="text-slate-400 text-sm">Cargando…</p>
          ) : (
            <button
              onClick={toggleCargaXml}
              disabled={savingCargaXml}
              className={`flex items-center gap-3 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 ${
                cargaXmlActiva
                  ? 'bg-emerald-50 border border-emerald-200 text-emerald-700 hover:bg-emerald-100'
                  : 'bg-red-50 border border-red-200 text-red-700 hover:bg-red-100'
              }`}
            >
              <span className={`inline-block w-2.5 h-2.5 rounded-full ${cargaXmlActiva ? 'bg-emerald-500' : 'bg-red-500'}`} />
              {savingCargaXml ? 'Guardando…' : cargaXmlActiva ? 'Activada — clic para desactivar' : 'Desactivada — clic para activar'}
            </button>
          )}
        </div>

        {!cfg ? (
          <p className="text-slate-500 text-sm">Cargando…</p>
        ) : (
          <div className="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={label}>Servidor IMAP</label>
                <input className={input} value={cfg.imap_host} onChange={e => set('imap_host', e.target.value)} />
              </div>
              <div>
                <label className={label}>Puerto</label>
                <input type="number" className={input} value={cfg.imap_port} onChange={e => set('imap_port', Number(e.target.value))} />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={label}>Cuenta de correo</label>
                <input className={input} value={cfg.imap_user} onChange={e => set('imap_user', e.target.value)} />
              </div>
              <div>
                <label className={label}>Carpeta</label>
                <input className={input} value={cfg.imap_folder} onChange={e => set('imap_folder', e.target.value)} />
              </div>
            </div>

            <div>
              <label className={label}>Contraseña (App Password)</label>
              <div className="flex items-center gap-2">
                <span className={`inline-block w-2.5 h-2.5 rounded-full ${cfg.password_configurado ? 'bg-emerald-500' : 'bg-red-500'}`} />
                <span className="text-sm text-slate-600">
                  {cfg.password_configurado ? 'Configurada en el servidor' : 'No configurada'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Por seguridad, la contraseña se define en el archivo <span className="font-mono">.env</span> del servidor
                (<span className="font-mono">IMAP_PASSWORD</span>), no desde aquí.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className={label}>Revisión automática cada (min)</label>
                <input type="number" min={1} className={input} value={cfg.poll_minutos} onChange={e => set('poll_minutos', Number(e.target.value))} />
              </div>
              <div className="flex items-end pb-2">
                <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer">
                  <input type="checkbox" checked={cfg.auto_activo} onChange={e => set('auto_activo', e.target.checked)} className="w-4 h-4" />
                  Revisión automática activada
                </label>
              </div>
            </div>

            <div className="border-t border-slate-100 pt-4">
              <label className="flex items-start gap-2 text-sm text-slate-700 cursor-pointer">
                <input
                  type="checkbox"
                  checked={cfg.confirmaciones_activas}
                  onChange={e => set('confirmaciones_activas', e.target.checked)}
                  className="w-4 h-4 mt-0.5"
                />
                <span>
                  Enviar <strong>automáticamente</strong> la confirmación al profesor cuando su factura quede aprobada
                  <span className="block text-xs text-slate-400 mt-0.5">
                    Apagado, las confirmaciones solo se envían con el botón &quot;Enviar confirmaciones&quot; de la página
                    Correo. Se envía una sola vez por factura; las rechazadas no generan correo.
                  </span>
                </span>
              </label>
            </div>

            <div>
              <label className={label}>Remitentes permitidos</label>
              <textarea
                className={`${input} h-20 resize-none`}
                placeholder="uno por línea o separados por coma — vacío = cualquier remitente"
                value={cfg.remitentes_permitidos ?? ''}
                onChange={e => set('remitentes_permitidos', e.target.value)}
              />
              <p className="text-xs text-slate-400 mt-1">
                Si defines remitentes, solo se procesarán correos de esas direcciones; los demás se ignoran.
              </p>
            </div>

            <div className="pt-2">
              <button
                onClick={handleSave}
                disabled={saving}
                className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium px-5 py-2.5 rounded-lg transition-colors"
              >
                {saving ? 'Guardando…' : 'Guardar configuración'}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  )
}
