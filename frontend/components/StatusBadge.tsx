const config = {
  aprobada:  { bg: 'bg-emerald-100 text-emerald-800', label: 'Aprobada' },
  rechazada: { bg: 'bg-red-100 text-red-800',         label: 'Rechazada' },
  pendiente: { bg: 'bg-amber-100 text-amber-800',     label: 'Pendiente' },
} as const

type Estado = keyof typeof config

export default function StatusBadge({ estado }: { estado: string }) {
  const { bg, label } = config[estado as Estado] ?? { bg: 'bg-slate-100 text-slate-700', label: estado }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${bg}`}>
      {label}
    </span>
  )
}
