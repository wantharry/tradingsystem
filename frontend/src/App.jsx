import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/layout/Sidebar'
import Header from './components/layout/Header'
import Dashboard from './pages/Dashboard'
import DailyActions from './pages/DailyActions'
import Strategies from './pages/Strategies'
import Backtest from './pages/Backtest'
import DataViewer from './pages/DataViewer'
import Watchlist from './pages/Watchlist'
import Screener from './pages/Screener'

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden bg-gray-950">
      <Sidebar />
      <div className="flex flex-col flex-1 overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/daily" element={<DailyActions />} />
            <Route path="/strategies" element={<Strategies />} />
            <Route path="/backtest" element={<Backtest />} />
            <Route path="/data" element={<DataViewer />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/screener" element={<Screener />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}
