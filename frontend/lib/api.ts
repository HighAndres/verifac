const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

function token(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem('cfdi_token')
}

function authHeaders(): HeadersInit {
  const t = token()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

// FastAPI devuelve `detail` como texto (HTTPException) o como lista de objetos
// {loc, msg, ...} en errores de validación (422). Normaliza ambos a un texto útil.
function mensajeError(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    const msgs = detail
      .map(e => (e && typeof e === 'object' && 'msg' in e ? String((e as { msg: unknown }).msg) : ''))
      .filter(Boolean)
    if (msgs.length) return msgs.join(' · ')
  }
  return 'Error del servidor'
}

async function handle(res: Response) {
  if (res.status === 401) {
    localStorage.removeItem('cfdi_token')
    window.location.href = '/login'
    throw new Error('No autenticado')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(mensajeError(err.detail))
  }
  if (res.status === 204) return null
  return res.json()
}

export async function login(username: string, password: string) {
  const res = await fetch(`${API}/api/v1/auth/login`, {
    method: 'POST',
    body: new URLSearchParams({ username, password }),
  })
  if (!res.ok) throw new Error('Credenciales incorrectas')
  const data = await res.json()
  localStorage.setItem('cfdi_token', data.access_token)
  localStorage.setItem('cfdi_rol', data.rol)
  localStorage.setItem('cfdi_nombre', data.nombre)
}

export function logout() {
  localStorage.removeItem('cfdi_token')
  localStorage.removeItem('cfdi_rol')
  localStorage.removeItem('cfdi_nombre')
  window.location.href = '/login'
}

export function isAuthenticated() { return Boolean(token()) }
export function getRol(): string { return (typeof window !== 'undefined' ? localStorage.getItem('cfdi_rol') : null) ?? '' }
export function getNombre(): string { return (typeof window !== 'undefined' ? localStorage.getItem('cfdi_nombre') : null) ?? '' }
export function isSuperAdmin(): boolean { return getRol() === 'superadmin' }

// ── Usuarios ──────────────────────────────────────────────────────────────────

export async function getUsuarios() {
  return handle(await fetch(`${API}/api/v1/usuarios`, { headers: authHeaders() }))
}

export async function createUsuario(data: object) {
  return handle(await fetch(`${API}/api/v1/usuarios`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  }))
}

export async function updateUsuario(id: string, data: object) {
  return handle(await fetch(`${API}/api/v1/usuarios/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  }))
}

export async function deleteUsuario(id: string) {
  return handle(await fetch(`${API}/api/v1/usuarios/${id}`, {
    method: 'DELETE', headers: authHeaders(),
  }))
}

// ── Auditoría ─────────────────────────────────────────────────────────────────

export async function getAuditoria(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(params).toString()
  return handle(await fetch(`${API}/api/v1/auditoria${qs ? '?' + qs : ''}`, { headers: authHeaders() }))
}

// ── Facturas ──────────────────────────────────────────────────────────────────

export async function getFacturas(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(params).toString()
  return handle(await fetch(`${API}/api/v1/facturas${qs ? '?' + qs : ''}`, { headers: authHeaders() }))
}

export async function getFactura(id: string) {
  return handle(await fetch(`${API}/api/v1/facturas/${id}`, { headers: authHeaders() }))
}

export async function uploadFactura(file: File) {
  const fd = new FormData()
  fd.append('file', file)
  return handle(await fetch(`${API}/api/v1/facturas/upload`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  }))
}

export async function revalidarFactura(id: string) {
  return handle(await fetch(`${API}/api/v1/facturas/${id}/revalidar`, {
    method: 'POST',
    headers: authHeaders(),
  }))
}

export async function revalidarMes(mes: number, anio: number) {
  return handle(await fetch(`${API}/api/v1/facturas/revalidar-mes?mes=${mes}&anio=${anio}`, {
    method: 'POST',
    headers: authHeaders(),
  }))
}

// ── Profesores ────────────────────────────────────────────────────────────────

export async function getProfesores(params: Record<string, string> = {}) {
  const qs = new URLSearchParams(params).toString()
  return handle(await fetch(`${API}/api/v1/profesores${qs ? '?' + qs : ''}`, { headers: authHeaders() }))
}

export async function createProfesor(data: object) {
  return handle(await fetch(`${API}/api/v1/profesores`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  }))
}

export async function updateProfesor(id: string, data: object) {
  return handle(await fetch(`${API}/api/v1/profesores/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(data),
  }))
}

// ── Catálogo de claves ────────────────────────────────────────────────────────

export async function getCatalogo(tipo?: string) {
  const qs = tipo ? `?tipo=${tipo}` : ''
  return handle(await fetch(`${API}/api/v1/catalogo-claves${qs}`, { headers: authHeaders() }))
}

export async function getClavesByProfesor(profesorId: string) {
  return handle(await fetch(`${API}/api/v1/profesores/${profesorId}/claves`, { headers: authHeaders() }))
}

export async function asignarClave(profesorId: string, claveId: string) {
  return handle(await fetch(`${API}/api/v1/profesores/${profesorId}/claves/${claveId}`, {
    method: 'POST',
    headers: authHeaders(),
  }))
}

export async function removerClave(profesorId: string, claveId: string) {
  return handle(await fetch(`${API}/api/v1/profesores/${profesorId}/claves/${claveId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  }))
}

// ── Montos mensuales ──────────────────────────────────────────────────────────

export async function getMontosMensuales(mes: number, anio: number) {
  return handle(await fetch(`${API}/api/v1/facturas/montos/${mes}/${anio}`, { headers: authHeaders() }))
}

export async function uploadMontosMensuales(file: File, mes: number, anio: number) {
  const fd = new FormData()
  fd.append('file', file)
  return handle(await fetch(`${API}/api/v1/facturas/upload-montos?mes=${mes}&anio=${anio}`, {
    method: 'POST',
    headers: authHeaders(),
    body: fd,
  }))
}

// ── Dashboard ─────────────────────────────────────────────────────────────────

export async function getDashboard(mes: number, anio: number) {
  return handle(await fetch(`${API}/api/v1/dashboard?mes=${mes}&anio=${anio}`, { headers: authHeaders() }))
}

export async function descargarExcelMes(mes: number, anio: number) {
  const res = await fetch(`${API}/api/v1/facturas/export-mes?mes=${mes}&anio=${anio}`, { headers: authHeaders() })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(mensajeError(err.detail))
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `Verifac_conciliacion_${anio}-${String(mes).padStart(2, '0')}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Correo (watcher IMAP) ─────────────────────────────────────────────────────

export async function getWatcherStatus() {
  return handle(await fetch(`${API}/api/v1/watcher/status`, { headers: authHeaders() }))
}

export async function runWatcher() {
  return handle(await fetch(`${API}/api/v1/watcher/run`, { method: 'POST', headers: authHeaders() }))
}

export async function enviarConfirmaciones() {
  return handle(await fetch(`${API}/api/v1/watcher/enviar-confirmaciones`, { method: 'POST', headers: authHeaders() }))
}

export async function getWatcherConfig() {
  return handle(await fetch(`${API}/api/v1/watcher/config`, { headers: authHeaders() }))
}

export async function updateWatcherConfig(data: object) {
  return handle(await fetch(`${API}/api/v1/watcher/config`, {
    method: 'PUT',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }))
}
