import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, Zap, BookOpen, FlaskConical,
  Database, Star, TrendingUp
} from 'lucide-react'

const nav = [
  { to: '/',          icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/daily',     icon: Zap,             label: 'Daily Actions' },
  { to: '/strategies',icon: BookOpen,         label: 'Strategies' },
  { to: '/backtest',  icon: FlaskConical,     label: 'Backtest' },
  { to: '/data',      icon: Database,         label: 'Data Viewer' },
  { to: '/watchlist', icon: Star,             label: 'Watchlist' },
]

export default function Sidebar() {
  return (
    <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
      {/* Logo */}
      <div className="flex items-center gap-2 px-4 py-5 border-b border-gray-800">
        <TrendingUp className="text-green-400" size={22} />
        <span className="font-bold text-white text-sm">TradingSystem</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 space-y-1">
        {nav.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                isActive
                  ? 'bg-green-600/20 text-green-400'
                  : 'text-gray-400 hover:text-white hover:bg-gray-800'
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-gray-800 text-xs text-gray-600">
        Educational tool only.<br />Not financial advice.
      </div>
    </aside>
  )
}
