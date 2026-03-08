import { useRef, useState } from 'react'
import { Upload, CheckCircle, XCircle, Loader, Clock } from 'lucide-react'
import { useIngest } from '../context/IngestContext'
import type { IngestJob } from '../context/IngestContext'

export default function IngestUI() {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const { jobs, submit, clearFinished } = useIngest()

  const addFiles = (files: FileList | null) => {
    if (!files) return
    Array.from(files).forEach(f => submit(f))
  }

  return (
    <div className="h-full flex flex-col p-6 gap-5 overflow-y-auto">
      <div>
        <h2 className="text-base font-semibold text-gray-100">Ingest documents</h2>
        <p className="text-xs text-gray-500 mt-0.5">PDF, DOCX, Markdown, HTML, LaTeX — uploads run in the background</p>
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
        onClick={() => inputRef.current?.click()}
        className={`flex flex-col items-center justify-center gap-3 border-2 border-dashed rounded-xl py-12 cursor-pointer transition-colors ${
          dragging
            ? 'border-indigo-500 bg-indigo-950/30'
            : 'border-gray-700 hover:border-gray-600 bg-gray-900'
        }`}
      >
        <Upload size={28} className="text-gray-500" />
        <p className="text-sm text-gray-400">Drop files here or <span className="text-indigo-400">browse</span></p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.md,.html,.htm,.tex"
          className="hidden"
          onChange={e => { addFiles(e.target.files); e.target.value = '' }}
        />
      </div>

      {/* Queue */}
      {jobs.length > 0 && (
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
              Queue ({jobs.length})
            </h3>
            <button onClick={clearFinished} className="text-xs text-gray-600 hover:text-gray-400">
              Clear finished
            </button>
          </div>
          {jobs.map(item => (
            <JobRow key={item.id} job={item} />
          ))}
        </div>
      )}
    </div>
  )
}

function JobRow({ job }: { job: IngestJob }) {
  return (
    <div className="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-gray-900 border border-gray-800">
      <StatusIcon status={job.status} />
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-200 truncate">{job.filename}</p>
        {job.status === 'done' && (
          <p className="text-xs text-gray-500 mt-0.5">
            {job.chunk_count} chunks · {job.entity_count} entities · {job.citation_count} citations
          </p>
        )}
        {job.status === 'error' && (
          <p className="text-xs text-red-400 mt-0.5 truncate" title={job.error}>{job.error}</p>
        )}
        {(job.status === 'queued' || job.status === 'preparing' || job.status === 'storing') && (
          <p className="text-xs text-gray-600 mt-0.5">
            {job.status === 'queued' ? 'Waiting…' : job.status === 'preparing' ? 'Parsing & embedding…' : 'Writing to graph…'}
          </p>
        )}
      </div>
      <span className={`text-xs font-medium shrink-0 ${statusColour(job.status)}`}>
        {job.status}
      </span>
    </div>
  )
}

function StatusIcon({ status }: { status: IngestJob['status'] }) {
  if (status === 'done')                                  return <CheckCircle size={16} className="text-green-400 shrink-0" />
  if (status === 'error')                                 return <XCircle size={16} className="text-red-400 shrink-0" />
  if (status === 'preparing' || status === 'storing')     return <Loader size={16} className="text-indigo-400 animate-spin shrink-0" />
  return <Clock size={16} className="text-gray-600 shrink-0" />
}

function statusColour(status: IngestJob['status']) {
  return ({
    queued:    'text-gray-500',
    preparing: 'text-indigo-400',
    storing:   'text-amber-400',
    done:      'text-green-400',
    error:     'text-red-400',
  } as Record<string, string>)[status] ?? 'text-gray-500'
}
