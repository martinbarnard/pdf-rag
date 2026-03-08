export default function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 text-gray-400 h-full">
      <div className="w-8 h-8 rounded-full border-2 border-gray-600 border-t-indigo-400 animate-spin" />
      <span className="text-sm">{label}</span>
    </div>
  )
}
