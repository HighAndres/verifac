import type { Metadata } from 'next'
import './globals.css'
import { ToastProvider } from '@/components/Toast'
import IdleTimeout from '@/components/IdleTimeout'

export const metadata: Metadata = {
  title: 'Verifac — Validación y conciliación de CFDI',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body className="bg-slate-50 text-slate-900 antialiased">
        <ToastProvider>
          <IdleTimeout />
          {children}
        </ToastProvider>
      </body>
    </html>
  )
}
