/**
 * Global ingest queue context.
 *
 * Holds the list of all submitted jobs and polls the server while any job
 * is running, so the queue persists across page navigation.
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'

export interface IngestJob {
  id: string
  filename: string
  status: 'queued' | 'preparing' | 'storing' | 'done' | 'error'
  paper_id?: string
  chunk_count?: number
  entity_count?: number
  citation_count?: number
  error?: string
}

interface IngestContextValue {
  jobs: IngestJob[]
  submit: (file: File) => Promise<void>
  clearFinished: () => Promise<void>
  activeCount: number
}

const IngestContext = createContext<IngestContextValue | null>(null)

const POLL_MS = 2000

export function IngestProvider({ children }: { children: React.ReactNode }) {
  const [jobs, setJobs] = useState<IngestJob[]>([])
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const hasActive = jobs.some(j => j.status === 'queued' || j.status === 'preparing' || j.status === 'storing')

  // Merge server jobs into local state (preserves order of local additions)
  const mergeJobs = useCallback((serverJobs: IngestJob[]) => {
    setJobs(prev => {
      const byId = new Map(serverJobs.map(j => [j.id, j]))
      // update existing entries
      const updated = prev.map(j => byId.has(j.id) ? { ...j, ...byId.get(j.id)! } : j)
      // add any new ones from server not yet in local state
      const localIds = new Set(prev.map(j => j.id))
      const fresh = serverJobs.filter(j => !localIds.has(j.id))
      return [...updated, ...fresh]
    })
  }, [])

  const poll = useCallback(async () => {
    try {
      const res = await fetch('/api/ingest/jobs')
      if (res.ok) mergeJobs(await res.json())
    } catch { /* ignore network errors during poll */ }
  }, [mergeJobs])

  // Start/stop polling based on whether there are active jobs
  useEffect(() => {
    if (hasActive) {
      if (!pollRef.current) {
        pollRef.current = setInterval(poll, POLL_MS)
      }
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current)
        pollRef.current = null
      }
    }
    return () => {
      if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    }
  }, [hasActive, poll])

  // On mount: fetch existing jobs so a page refresh shows history
  useEffect(() => { poll() }, [poll])

  const submit = useCallback(async (file: File) => {
    const form = new FormData()
    form.append('file', file)

    // Optimistic local entry
    const tempId = `local-${Date.now()}-${file.name}`
    const optimistic: IngestJob = { id: tempId, filename: file.name, status: 'queued' }
    setJobs(prev => [optimistic, ...prev])

    try {
      const res = await fetch('/api/ingest', { method: 'POST', body: form })
      if (!res.ok) {
        const text = await res.text()
        setJobs(prev => prev.map(j =>
          j.id === tempId ? { ...j, status: 'error', error: text || `${res.status}` } : j
        ))
        return
      }
      const data: { job_id: string; filename: string; status: IngestJob['status'] } = await res.json()
      // Replace optimistic entry with real job from server
      setJobs(prev => prev.map(j => j.id === tempId ? { ...j, id: data.job_id, status: 'queued' } : j))
    } catch (e) {
      setJobs(prev => prev.map(j =>
        j.id === tempId ? { ...j, status: 'error', error: e instanceof Error ? e.message : String(e) } : j
      ))
    }
  }, [])

  const clearFinished = useCallback(async () => {
    try {
      await fetch('/api/ingest/jobs', { method: 'DELETE' })
    } catch { /* best-effort */ }
    setJobs(prev => prev.filter(j => j.status === 'queued' || j.status === 'preparing' || j.status === 'storing'))
  }, [])

  const activeCount = jobs.filter(j => j.status === 'queued' || j.status === 'preparing' || j.status === 'storing').length

  return (
    <IngestContext.Provider value={{ jobs, submit, clearFinished, activeCount }}>
      {children}
    </IngestContext.Provider>
  )
}

export function useIngest() {
  const ctx = useContext(IngestContext)
  if (!ctx) throw new Error('useIngest must be used within IngestProvider')
  return ctx
}
