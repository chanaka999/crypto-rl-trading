import { useEffect, useState } from 'react';
import { getMetrics, getEquityCurve } from '../services/api';
import StatCard from '../components/StatCard';
import {
  DollarSign, TrendingUp, TrendingDown, BarChart3,
  Target, Activity, AlertTriangle
} from 'lucide-react';
import {
  XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Area, AreaChart
} from 'recharts';

interface Metrics {
  mode: string;
  symbol: string;
  initial_balance: number;
  current_balance: number;
  total_pnl: number;
  return_pct: number;
  num_trades: number;
  win_rate: number;
  max_drawdown: number;
  monthly_target_return_pct: number;
  target_warning: string;
  warnings: string[];
}

export default function Overview() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [equityCurve, setEquityCurve] = useState<Array<{ step: number; equity: number }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [metricsRes, equityRes] = await Promise.all([
          getMetrics(),
          getEquityCurve(),
        ]);
        setMetrics(metricsRes.data);
        setEquityCurve(equityRes.data.equity_curve || []);
      } catch {
        console.error('Failed to fetch data');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-400" />
      </div>
    );
  }

  const m = metrics;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Dashboard Overview</h2>
          <p className="text-gray-500 text-sm mt-1">
            Mode: <span className="text-emerald-400 font-medium uppercase">{m?.mode || 'N/A'}</span>
            {' | '}
            Pair: <span className="text-white font-medium">{m?.symbol || 'N/A'}</span>
          </p>
        </div>
        {m?.mode === 'live' && (
          <div className="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2">
            <Radio className="animate-pulse" size={16} />
            LIVE TRADING ACTIVE
          </div>
        )}
      </div>

      {m?.warnings && m.warnings.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 text-yellow-400 font-medium text-sm mb-2">
            <AlertTriangle size={16} />
            Warnings
          </div>
          {m.warnings.map((w, i) => (
            <p key={i} className="text-xs text-yellow-400/80 mt-1">{w}</p>
          ))}
        </div>
      )}

      {m?.target_warning && (
        <div className="bg-orange-500/10 border border-orange-500/30 rounded-lg p-3 text-xs text-orange-400">
          <strong>Target Alert:</strong> {m.target_warning}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Initial Balance"
          value={`$${m?.initial_balance?.toFixed(2) || '0'}`}
          icon={<DollarSign size={16} />}
        />
        <StatCard
          title="Current Balance"
          value={`$${m?.current_balance?.toFixed(2) || '0'}`}
          icon={<DollarSign size={16} />}
          trend={m && m.current_balance >= m.initial_balance ? 'up' : 'down'}
        />
        <StatCard
          title="Total P&L"
          value={`$${m?.total_pnl?.toFixed(4) || '0'}`}
          subtitle={`${m?.return_pct?.toFixed(2) || '0'}%`}
          icon={m && m.total_pnl >= 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
          trend={m && m.total_pnl >= 0 ? 'up' : 'down'}
        />
        <StatCard
          title="Win Rate"
          value={`${m?.win_rate?.toFixed(1) || '0'}%`}
          subtitle={`${m?.num_trades || 0} trades`}
          icon={<Target size={16} />}
          trend={m && m.win_rate >= 50 ? 'up' : m && m.win_rate > 0 ? 'down' : 'neutral'}
        />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Max Drawdown"
          value={`${m?.max_drawdown?.toFixed(2) || '0'}%`}
          icon={<Activity size={16} />}
          trend={m && m.max_drawdown > 10 ? 'down' : 'neutral'}
        />
        <StatCard
          title="Monthly Target"
          value={`${m?.monthly_target_return_pct || 0}%`}
          subtitle="Aggressive target"
          icon={<BarChart3 size={16} />}
        />
        <StatCard
          title="Number of Trades"
          value={m?.num_trades || 0}
          icon={<BarChart3 size={16} />}
        />
        <StatCard
          title="Return %"
          value={`${m?.return_pct?.toFixed(2) || '0'}%`}
          icon={<TrendingUp size={16} />}
          trend={m && m.return_pct >= 0 ? 'up' : 'down'}
        />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-4">Equity Curve</h3>
        {equityCurve.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <AreaChart data={equityCurve}>
              <defs>
                <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="step" stroke="#6b7280" tick={{ fontSize: 11 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Area type="monotone" dataKey="equity" stroke="#10b981" fill="url(#equityGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-600 text-sm">
            No equity data yet. Run a backtest or start trading to see results.
          </div>
        )}
      </div>
    </div>
  );
}

function Radio({ className, size }: { className?: string; size?: number }) {
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="2" /><path d="M16.24 7.76a6 6 0 0 1 0 8.49m-8.48-.01a6 6 0 0 1 0-8.49m11.31-2.82a10 10 0 0 1 0 14.14m-14.14 0a10 10 0 0 1 0-14.14" />
    </svg>
  );
}
