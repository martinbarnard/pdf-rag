import { BrowserRouter, Routes, Route, NavLink, Navigate } from 'react-router-dom'
import { Network, BookOpen, Tag, Upload, Search, Settings as SettingsIcon } from 'lucide-react'
import { useApi } from './hooks/useApi'
import { IngestProvider, useIngest } from './context/IngestContext'
import GraphExplorer from './pages/GraphExplorer'
import PaperBrowser from './pages/PaperBrowser'
import TopicMap from './pages/TopicMap'
import TopicDetail from './pages/TopicDetail'
import AuthorDetail from './pages/AuthorDetail'
import IngestUI from './pages/IngestUI'
import SearchPage from './pages/Search'
import SettingsPage from './pages/Settings'

const NAV = [
  { to: '/graph',    label: 'Graph',    icon: Network       },
  { to: '/papers',   label: 'Papers',   icon: BookOpen      },
  { to: '/topics',   label: 'Topics',   icon: Tag           },
  { to: '/search',   label: 'Search',   icon: Search        },
  { to: '/ingest',   label: 'Ingest',   icon: Upload        },
  { to: '/settings', label: 'Settings', icon: SettingsIcon  },
]

interface Stats { papers: number; authors: number; topics: number; chunks: number }

function Sidebar() {
  const { data: stats } = useApi<Stats>('/api/stats')
  const { activeCount } = useIngest()

  return (
    <nav className="flex flex-col w-48 shrink-0 bg-gray-900 border-r border-gray-800">
      <div className="px-4 pt-5 pb-4 border-b border-gray-800">
        <h1 className="text-sm font-bold text-indigo-400 tracking-wider uppercase">pdf-rag</h1>
        <p className="text-xs text-gray-500 mt-0.5">Graph explorer</p>
      </div>

      <div className="flex flex-col gap-0.5 p-2 flex-1">
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
            <span className="flex-1">{label}</span>
            {label === 'Ingest' && activeCount > 0 && (
              <span className="ml-auto bg-indigo-500 text-white text-xs font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none">
                {activeCount}
              </span>
            )}
          </NavLink>
        ))}
      </div>

      {stats && (
        <div className="px-4 py-3 border-t border-gray-800 space-y-1">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Database</p>
          {[
            { label: 'Papers',  value: stats.papers  },
            { label: 'Authors', value: stats.authors },
            { label: 'Topics',  value: stats.topics  },
            { label: 'Chunks',  value: stats.chunks  },
          ].map(({ label, value }) => (
            <div key={label} className="flex justify-between text-xs">
              <span className="text-gray-500">{label}</span>
              <span className="text-gray-300 font-medium tabular-nums">{value}</span>
            </div>
          ))}
        </div>
      )}
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter basename="/app">
      <IngestProvider>
      <div className="flex h-screen bg-gray-950 text-gray-100 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Navigate to="/graph" replace />} />
            <Route path="/graph"        element={<GraphExplorer />} />
            <Route path="/papers"       element={<PaperBrowser />} />
            <Route path="/topics"       element={<TopicMap />} />
            <Route path="/topics/:id"   element={<TopicDetail />} />
            <Route path="/authors/:id"  element={<AuthorDetail />} />
            <Route path="/search"       element={<SearchPage />} />
            <Route path="/ingest"       element={<IngestUI />} />
            <Route path="/settings"     element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
      </IngestProvider>
    </BrowserRouter>
  )
}
