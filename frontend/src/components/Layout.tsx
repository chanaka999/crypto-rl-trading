import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Settings, BarChart3, PlayCircle,
  Radio, Brain, History, AlertTriangle
} from 'lucide-react';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/backtest', icon: BarChart3, label: 'Backtest' },
  { to: '/paper', icon: PlayCircle, label: 'Paper Trading' },
  { to: '/live', icon: Radio, label: 'Live Trading' },
  { to: '/model', icon: Brain, label: 'Model' },
  { to: '/history', icon: History, label: 'History' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export default function Layout() {
  return (
    <div className="flex h-screen bg-gray-950 text-gray-100">
      <aside className="w-56 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="p-4 border-b border-gray-800">
          <h1 className="text-lg font-bold text-emerald-400 flex items-center gap-2">
            <BarChart3 size={22} />
            CryptoRL Bot
          </h1>
          <p className="text-xs text-gray-500 mt-1">RL Spot Trading System</p>
        </div>
        <nav className="flex-1 py-2">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-400 border-r-2 border-emerald-400'
                    : 'text-gray-400 hover:text-gray-200 hover:bg-gray-800'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 border-t border-gray-800">
          <div className="flex items-start gap-2 text-xs text-yellow-500/80 bg-yellow-500/5 rounded p-2">
            <AlertTriangle size={14} className="mt-0.5 shrink-0" />
            <span>Trading involves risk. Past performance does not guarantee future results.</span>
          </div>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
