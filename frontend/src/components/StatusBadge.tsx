import type { ItemStatus } from '../api/types'

const STYLES: Record<ItemStatus, { label: string; className: string }> = {
  pending: { label: 'Indexing…', className: 'bg-amber-100 text-amber-800 animate-pulse' },
  ready: { label: 'Ready', className: 'bg-green-100 text-green-800' },
  failed: { label: 'Failed', className: 'bg-red-100 text-red-800' },
}

export function StatusBadge({ status }: { status: ItemStatus }) {
  const { label, className } = STYLES[status]
  return <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${className}`}>{label}</span>
}
