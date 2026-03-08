import { useState } from 'react'
import { useApi } from '../hooks/useApi'
import { Database, Trash2, AlertTriangle, RefreshCw } from 'lucide-react'

interface Stats {
  counts: Record<string, number>
  db_path: string
  size_bytes: number
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`
}

type ConfirmAction = 'truncate' | 'delete' | null

const ACTION_CONFIG = {
  truncate: {
    label: 'Truncate database',
    description: 'Deletes all papers, authors, topics, and chunks. The database file is kept and the schema is preserved — you can re-ingest immediately.',
    confirmWord: 'truncate',
    buttonClass: 'bg-amber-700 hover:bg-amber-600',
    icon: <Trash2 size={14} />,
    endpoint: '/api/admin/truncate',
    method: 'POST' as const,
  },
  delete: {
    label: 'Delete database',
    description: 'Permanently deletes the database file. The server will create a fresh empty database on the next request. Restart the server after deleting for a fully clean state.',
    confirmWord: 'delete',
    buttonClass: 'bg-red-700 hover:bg-red-600',
    icon: <Trash2 size={14} />,
    endpoint: '/api/admin/db',
    method: 'DELETE' as const,
  },
}

export default function Settings() {
  const { data: stats, loading, error, refetch } = useApi<Stats>('/api/admin/stats')
  const [confirmAction, setConfirmAction] = useState<ConfirmAction>(null)
  const [confirmText, setConfirmText] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<{ ok: boolean; message: string } | null>(null)

  const openConfirm = (action: ConfirmAction) => {
    setConfirmAction(action)
    setConfirmText('')
    setResult(null)
  }

  const cancel = () => {
    setConfirmAction(null)
    setConfirmText('')
  }

  const execute = async () => {
    if (!confirmAction) return
    const cfg = ACTION_CONFIG[confirmAction]
    if (confirmText !== cfg.confirmWord) return

    setRunning(true)
    try {
      const res = await fetch(cfg.endpoint, { method: cfg.method })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? res.statusText)
      setResult({ ok: true, message: `Done. Status: ${data.status}` })
      setConfirmAction(null)
      setConfirmText('')
      refetch()
    } catch (e) {
      setResult({ ok: false, message: e instanceof Error ? e.message : String(e) })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="h-full overflow-y-auto p-6 max-w-xl space-y-8">
      <div>
        <h2 className="text-base font-semibold text-gray-100">Settings</h2>
        <p className="text-xs text-gray-500 mt-0.5">Database management and administration</p>
      </div>

      {/* DB Stats */}
      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-medium text-gray-300">
            <Database size={14} className="text-indigo-400" /> Database
          </h3>
          <button onClick={refetch} className="text-gray-600 hover:text-gray-300 transition-colors">
            <RefreshCw size={13} />
          </button>
        </div>

        {loading && <p className="text-xs text-gray-500">Loading…</p>}
        {error && <p className="text-xs text-red-400">{error}</p>}
        {stats && (
          <div className="bg-gray-900 rounded-lg border border-gray-800 divide-y divide-gray-800">
            <div className="px-4 py-2.5 flex justify-between text-xs">
              <span className="text-gray-500">Path</span>
              <span className="text-gray-400 font-mono truncate max-w-xs text-right">{stats.db_path}</span>
            </div>
            <div className="px-4 py-2.5 flex justify-between text-xs">
              <span className="text-gray-500">File size</span>
              <span className="text-gray-300 font-medium">{formatBytes(stats.size_bytes)}</span>
            </div>
            {Object.entries(stats.counts).map(([key, val]) => (
              <div key={key} className="px-4 py-2.5 flex justify-between text-xs">
                <span className="text-gray-500 capitalize">{key}</span>
                <span className="text-gray-300 font-medium tabular-nums">{val.toLocaleString()}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Result banner */}
      {result && (
        <div className={`px-4 py-3 rounded-lg text-sm ${result.ok ? 'bg-green-950 text-green-300 border border-green-900' : 'bg-red-950 text-red-300 border border-red-900'}`}>
          {result.message}
        </div>
      )}

      {/* Danger zone */}
      <section className="space-y-3">
        <h3 className="flex items-center gap-2 text-sm font-medium text-amber-400">
          <AlertTriangle size={14} /> Danger zone
        </h3>

        <div className="border border-gray-800 rounded-lg divide-y divide-gray-800">
          {(Object.entries(ACTION_CONFIG) as [ConfirmAction, typeof ACTION_CONFIG['truncate']][]).map(([key, cfg]) => (
            <div key={key} className="p-4 flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-200">{cfg.label}</p>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">{cfg.description}</p>
              </div>
              <button
                onClick={() => openConfirm(key)}
                className={`shrink-0 flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium text-white transition-colors ${cfg.buttonClass}`}
              >
                {cfg.icon}
                {cfg.label.split(' ')[0]}
              </button>
            </div>
          ))}
        </div>
      </section>

      {/* Confirmation modal */}
      {confirmAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-gray-900 border border-gray-700 rounded-xl shadow-2xl p-6 w-full max-w-sm mx-4 space-y-4">
            <div className="flex items-center gap-2 text-amber-400">
              <AlertTriangle size={16} />
              <h3 className="font-semibold text-sm">{ACTION_CONFIG[confirmAction].label}</h3>
            </div>
            <p className="text-xs text-gray-400 leading-relaxed">
              {ACTION_CONFIG[confirmAction].description}
            </p>
            <div className="space-y-2">
              <label className="text-xs text-gray-400">
                Type <strong className="text-gray-200 font-mono">{ACTION_CONFIG[confirmAction].confirmWord}</strong> to confirm:
              </label>
              <input
                autoFocus
                value={confirmText}
                onChange={e => setConfirmText(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && confirmText === ACTION_CONFIG[confirmAction!].confirmWord && execute()}
                className="w-full bg-gray-800 text-gray-100 text-sm rounded px-3 py-2 outline-none focus:ring-1 focus:ring-red-500 font-mono"
                placeholder={ACTION_CONFIG[confirmAction].confirmWord}
              />
            </div>
            <div className="flex gap-2 justify-end">
              <button onClick={cancel} disabled={running} className="px-4 py-2 rounded text-sm text-gray-400 hover:text-gray-100 transition-colors">
                Cancel
              </button>
              <button
                onClick={execute}
                disabled={running || confirmText !== ACTION_CONFIG[confirmAction].confirmWord}
                className={`flex items-center gap-2 px-4 py-2 rounded text-sm text-white font-medium transition-colors disabled:opacity-40 ${ACTION_CONFIG[confirmAction].buttonClass}`}
              >
                {running && <RefreshCw size={13} className="animate-spin" />}
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
