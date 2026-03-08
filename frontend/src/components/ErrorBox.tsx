export default function ErrorBox({ message }: { message: string }) {
  return (
    <div className="m-6 p-4 rounded-lg bg-red-950 border border-red-800 text-red-300 text-sm">
      <strong>Error:</strong> {message}
    </div>
  )
}
