'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { logout, getNombre, isSuperAdmin } from '@/lib/api'

// Menú ordenado según el proceso de operación:
// 1) Configuración inicial (una vez)  2) Operación mensual  3) Administración
const gruposBase = [
  {
    titulo: 'Configuración',
    links: [
      { href: '/profesores', label: 'Profesores' },
      { href: '/catalogo',   label: 'Catálogo SAT' },
    ],
  },
  {
    titulo: 'Operación mensual',
    links: [
      { href: '/dashboard', label: 'Dashboard' },
      { href: '/montos',   label: '1 · Montos del mes' },
      { href: '/upload',   label: '2 · Subir XML / Excel' },
      { href: '/facturas', label: '3 · Facturas' },
      { href: '/correo',   label: 'Correo' },
    ],
  },
]

const grupoAdmin = {
  titulo: 'Administración',
  links: [
    { href: '/usuarios',       label: 'Usuarios' },
    { href: '/config-correo',  label: 'Config. correo' },
    { href: '/auditoria',      label: 'Auditoría' },
  ],
}

export default function Sidebar() {
  const path = usePathname()
  const [superAdmin, setSuperAdmin] = useState(false)
  const [nombre, setNombre] = useState('')

  useEffect(() => {
    setSuperAdmin(isSuperAdmin())
    setNombre(getNombre())
  }, [])

  const grupos = superAdmin ? [...gruposBase, grupoAdmin] : gruposBase

  return (
    <aside className="w-56 min-h-screen bg-slate-900 text-slate-100 flex flex-col shrink-0">
      <div className="px-5 py-6 border-b border-slate-700 flex items-center gap-3">
        <div className="w-9 h-9 rounded-xl bg-blue-600 flex items-center justify-center shrink-0">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2 4 5v6c0 5 3.5 8 8 10 4.5-2 8-5 8-10V5l-8-3Z" />
            <path d="m9 12 2 2 4-4" />
          </svg>
        </div>
        <div>
          <h1 className="text-lg font-semibold leading-none">Verifac</h1>
          <p className="text-[10px] text-slate-400 uppercase tracking-widest mt-1">Conciliación CFDI</p>
        </div>
      </div>

      <nav className="flex-1 py-4 space-y-4">
        {grupos.map(({ titulo, links }) => (
          <div key={titulo}>
            <p className="px-5 pb-1 text-[10px] font-semibold uppercase tracking-widest text-slate-500">
              {titulo}
            </p>
            {links.map(({ href, label }) => {
              const active = path === href || (href !== '/facturas' && path.startsWith(href))
              return (
                <Link key={href} href={href}
                  className={`flex items-center px-5 py-2.5 text-sm transition-colors ${
                    active
                      ? 'bg-blue-600 text-white font-medium'
                      : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                  }`}
                >
                  {label}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-slate-700">
        <p className="text-xs text-slate-300 font-medium truncate">{nombre || 'Usuario'}</p>
        <p className="text-xs text-slate-500 mt-0.5 capitalize">{superAdmin ? 'Super Admin' : 'Revisor'}</p>
        <button onClick={logout}
          className="mt-2 text-xs text-slate-400 hover:text-white transition-colors">
          Cerrar sesión
        </button>
      </div>
    </aside>
  )
}
