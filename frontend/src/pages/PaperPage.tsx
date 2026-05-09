import { useEffect, useState } from 'react';
import { startPaper, stopPaper, resetPaper, getPaperStatus, getTrades } from '../services/api';
import { Play, Square, RotateCcw } from 'lucide-react';
import StatCard from '../components/StatCard';

interface PaperStatus {
  running: boolean;
  session_id: number | null;
  symbol: string;
  initial_balance: number;
  current_balance: number;
  coin_held: number;
  equity: number;
  unrealized_pnl: number;
  pnl: number;
  return_pct: number;
  num_trades: number;
  message?: string;
}

interface Trade {
  id: number;
  timestamp: string;
  side: string;
  price: number;
  quantity: number;
  fee: number;
  pnl: number;
  balance_after: number;
}

export default function PaperPage() {
  const [status, setStatus] = useState<PaperStatus | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    try {
      const [statusRes, tradesRes] = await Promise.all([
        getPaperStatus(),
        getTrades({ mode: 'paper', limit: 50 }),
      ]);
      setStatus(statusRes.data);
      setTrades(tradesRes.data.trades || []);
    } catch {
      console.error('Failed to fetch paper status');
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    setLoading(true);
    try {
      await startPaper();
      await fetchData();
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopPaper();
      await fetchData();
    } finally {
      setLoading(false);
    }
  };

  const handleReset = async () => {
    if (!confirm('Reset paper trading? This will clear all paper trades and reset balance.')) return;
    setLoading(true);
    try {
      await resetPaper();
      await fetchData();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Paper Trading</h2>
          <p className="text-gray-500 text-sm mt-1">Simulated trading with real-time market data</p>
        </div>
        <div className="flex gap-2">
          {status?.running ? (
            <button onClick={handleStop} disabled={loading}
              className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
              <Square size={16} /> Stop
            </button>
          ) : (
            <button onClick={handleStart} disabled={loading}
              className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
              <Play size={16} /> Start
            </button>
          )}
          <button onClick={handleReset} disabled={loading || (status?.running ?? false)}
            className="flex items-center gap-2 bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
            <RotateCcw size={16} /> Reset
          </button>
        </div>
      </div>

      <div className={`px-4 py-2 rounded-lg text-sm font-medium ${
        status?.running ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400' : 'bg-gray-800 border border-gray-700 text-gray-400'
      }`}>
        Status: {status?.running ? 'Running' : 'Stopped'}
        {status?.symbol && ` | Pair: ${status.symbol}`}
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="Initial Balance" value={`$${status?.initial_balance?.toFixed(2) || '0'}`} />
        <StatCard title="Current Balance" value={`$${status?.current_balance?.toFixed(4) || '0'}`}
          trend={status && status.current_balance >= status.initial_balance ? 'up' : 'down'} />
        <StatCard title="Equity" value={`$${status?.equity?.toFixed(4) || '0'}`}
          trend={status && status.equity >= status.initial_balance ? 'up' : 'down'} />
        <StatCard title="Unrealized P&L" value={`$${status?.unrealized_pnl?.toFixed(4) || '0'}`}
          trend={status && status.unrealized_pnl >= 0 ? 'up' : 'down'} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard title="Total P&L" value={`$${status?.pnl?.toFixed(4) || '0'}`}
          subtitle={`${status?.return_pct?.toFixed(2) || '0'}%`}
          trend={status && status.pnl >= 0 ? 'up' : 'down'} />
        <StatCard title="Coin Holdings" value={status?.coin_held?.toFixed(8) || '0'} />
        <StatCard title="Trades" value={status?.num_trades || 0} />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-4">Paper Trade History</h3>
        {trades.length > 0 ? (
          <div className="overflow-x-auto max-h-72 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="text-gray-500 border-b border-gray-800 sticky top-0 bg-gray-900">
                <tr>
                  <th className="text-left py-2 px-2">Time</th>
                  <th className="text-left py-2 px-2">Side</th>
                  <th className="text-right py-2 px-2">Price</th>
                  <th className="text-right py-2 px-2">Qty</th>
                  <th className="text-right py-2 px-2">Fee</th>
                  <th className="text-right py-2 px-2">P&L</th>
                  <th className="text-right py-2 px-2">Balance</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((t, i) => (
                  <tr key={i} className="border-b border-gray-800/50">
                    <td className="py-1.5 px-2 text-gray-400">{t.timestamp?.slice(0, 19)}</td>
                    <td className={`py-1.5 px-2 font-medium ${t.side === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>{t.side}</td>
                    <td className="py-1.5 px-2 text-right text-gray-300">{Number(t.price).toFixed(2)}</td>
                    <td className="py-1.5 px-2 text-right text-gray-300">{Number(t.quantity).toFixed(6)}</td>
                    <td className="py-1.5 px-2 text-right text-gray-500">{Number(t.fee).toFixed(4)}</td>
                    <td className={`py-1.5 px-2 text-right ${Number(t.pnl) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{Number(t.pnl).toFixed(4)}</td>
                    <td className="py-1.5 px-2 text-right text-gray-300">{Number(t.balance_after).toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-sm text-center py-8">No paper trades yet. Start the paper bot to begin.</p>
        )}
      </div>
    </div>
  );
}
