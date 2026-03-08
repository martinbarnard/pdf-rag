import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { Network, BookOpen, Tag, Upload } from 'lucide-react'
import GraphExplorer from './pages/GraphExplorer'
import PaperBrowser from './pages/PaperBrowser'
import TopicMap from './pages/TopicMap'
import IngestUI from './pages/IngestUI'

const NAV = [
  { to: '/graph',  label: 'Graph',  icon: Network  },
  { to: '/papers', label: 'Papers', icon: BookOpen  },
  { to: '/topics', label: 'Topics', icon: Tag       },
  { to: '/ingest', label: 'Ingest', icon: Upload    },
]

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
        {/* Sidebar */}
        <nav className="flex flex-col gap-1 w-48 shrink-0 bg-gray-900 border-r border-gray-800 p-3">
          <div className="px-2 py-3 mb-2">
            <h1 className="text-sm font-semibold text-indigo-400 tracking-wider uppercase">pdf-rag</h1>
            <p className="text-xs text-gray-500 mt-0.5">Graph explorer</p>
          </div>
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-100'
                }`
              }
            >
              <Icon size={15} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Main */}
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Navigate to="/graph" replace />} />
            <Route path="/graph" element={<GraphExplorer />} />
            <Route path="/papers" element={<PaperBrowser />} />
            <Route path="/topics" element={<TopicMap />} />
            <Route path="/ingest" element={<IngestUI />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
