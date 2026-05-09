import { useEffect, useState } from 'react';
import { startLive, stopLive, emergencyStop, getLiveStatus, getTrades } from '../services/api';
import { Play, Square, AlertOctagon, AlertTriangle, Shield } from 'lucide-react';
import StatCard from '../components/StatCard';

interface LiveStatus {
  running: boolean;
  connected: boolean;
  symbol: string;
  balance: number;
  coin_held: number;
  equity: number;
  avg_buy_price: number;
  num_trades: number;
  emergency_stop_active: boolean;
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

export default function LivePage() {
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const fetchData = async () => {
    try {
      const [statusRes, tradesRes] = await Promise.all([
        getLiveStatus(),
        getTrades({ mode: 'live', limit: 50 }),
      ]);
      setStatus(statusRes.data);
      setTrades(tradesRes.data.trades || []);
    } catch {
      console.error('Failed to fetch live status');
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleStart = async () => {
    setShowConfirm(true);
  };

  const handleConfirmStart = async () => {
    setShowConfirm(false);
    setLoading(true);
    try {
      const res = await startLive(true);
      if (res.data.status === 'error') {
        alert(res.data.message);
      }
      await fetchData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      alert(err?.response?.data?.detail || 'Failed to start live trading');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await stopLive();
      await fetchData();
    } finally {
      setLoading(false);
    }
  };

  const handleEmergencyStop = async () => {
    if (!confirm('EMERGENCY STOP: This will immediately stop trading and sell all positions. Continue?')) return;
    setLoading(true);
    try {
      await emergencyStop();
      await fetchData();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      {status?.running && (
        <div className="bg-red-500/10 border-2 border-red-500/50 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3 text-red-400">
            <AlertTriangle size={20} className="animate-pulse" />
            <div>
              <p className="font-bold text-sm">LIVE TRADING IS ACTIVE</p>
              <p className="text-xs text-red-400/70">Real money is being used. Monitor carefully.</p>
            </div>
          </div>
          <button onClick={handleEmergencyStop} disabled={loading}
            className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white px-5 py-2.5 rounded-lg text-sm font-bold disabled:opacity-50 animate-pulse">
            <AlertOctagon size={18} /> EMERGENCY STOP
          </button>
        </div>
      )}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Live Trading</h2>
          <p className="text-gray-500 text-sm mt-1">Binance Spot Trading — Real Money</p>
        </div>
        <div className="flex gap-2">
          {status?.running ? (
            <button onClick={handleStop} disabled={loading}
              className="flex items-center gap-2 bg-yellow-600 hover:bg-yellow-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
              <Square size={16} /> Stop Trading
            </button>
          ) : (
            <button onClick={handleStart} disabled={loading}
              className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
              <Play size={16} /> Start Live Trading
            </button>
          )}
        </div>
      </div>

      {showConfirm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
          <div className="bg-gray-900 border border-red-500/50 rounded-xl p-6 max-w-md">
            <div className="flex items-center gap-3 text-red-400 mb-4">
              <AlertTriangle size={24} />
              <h3 className="text-lg font-bold">Confirm Live Trading</h3>
            </div>
            <div className="text-sm text-gray-300 space-y-2 mb-6">
              <p>You are about to enable <strong>LIVE trading</strong> with <strong>REAL money</strong> on Binance.</p>
              <p className="text-yellow-400">Losses are possible and NOT recoverable. Past backtest performance does NOT guarantee future results.</p>
              <p>Make sure:</p>
              <ul className="list-disc pl-5 text-gray-400 space-y-1">
                <li>Your Binance API key is configured</li>
                <li>You have tested with paper trading first</li>
                <li>You understand the risks involved</li>
                <li>You have set appropriate stop-loss limits</li>
              </ul>
            </div>
            <div className="flex gap-3 justify-end">
              <button onClick={() => setShowConfirm(false)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm">Cancel</button>
              <button onClick={handleConfirmStart}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-bold">
                I Understand, Start Trading
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className={`bg-gray-900 border rounded-lg p-3 ${status?.connected ? 'border-emerald-500/30' : 'border-red-500/30'}`}>
          <div className="flex items-center gap-2">
            <Shield size={14} className={status?.connected ? 'text-emerald-400' : 'text-red-400'} />
            <span className="text-xs text-gray-500">Connection</span>
          </div>
          <p className={`text-sm font-medium mt-1 ${status?.connected ? 'text-emerald-400' : 'text-red-400'}`}>
            {status?.connected ? 'Connected to Binance' : 'Not Connected'}
          </p>
        </div>
        <div className={`bg-gray-900 border rounded-lg p-3 ${status?.emergency_stop_active ? 'border-red-500/30' : 'border-gray-800'}`}>
          <div className="flex items-center gap-2">
            <AlertOctagon size={14} className={status?.emergency_stop_active ? 'text-red-400' : 'text-gray-600'} />
            <span className="text-xs text-gray-500">Emergency Stop</span>
          </div>
          <p className={`text-sm font-medium mt-1 ${status?.emergency_stop_active ? 'text-red-400' : 'text-gray-400'}`}>
            {status?.emergency_stop_active ? 'ACTIVE' : 'Not Active'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="Balance" value={`$${status?.balance?.toFixed(4) || '0'}`} />
        <StatCard title="Equity" value={`$${status?.equity?.toFixed(4) || '0'}`} />
        <StatCard title="Coin Holdings" value={status?.coin_held?.toFixed(8) || '0'} />
        <StatCard title="Trades" value={status?.num_trades || 0} />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-4">Live Trade History</h3>
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
          <p className="text-gray-600 text-sm text-center py-8">No live trades yet.</p>
        )}
      </div>
    </div>
  );
}
