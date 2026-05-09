import { useEffect, useState } from 'react';
import { getTrades } from '../services/api';
import { Download, Filter } from 'lucide-react';

interface Trade {
  id: number;
  timestamp: string;
  mode: string;
  symbol: string;
  side: string;
  price: number;
  quantity: number;
  fee: number;
  slippage: number;
  pnl: number;
  balance_before: number;
  balance_after: number;
  model_action: number | null;
  reason: string | null;
  confidence: number | null;
}

export default function HistoryPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [modeFilter, setModeFilter] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchTrades = async () => {
    setLoading(true);
    try {
      const res = await getTrades({ mode: modeFilter || undefined, limit: 200 });
      setTrades(res.data.trades || []);
    } catch {
      console.error('Failed to fetch trades');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTrades();
  }, [modeFilter]);

  const exportCSV = () => {
    const headers = ['id', 'timestamp', 'mode', 'symbol', 'side', 'price', 'quantity', 'fee', 'slippage', 'pnl', 'balance_before', 'balance_after', 'model_action', 'reason', 'confidence'];
    const csv = [
      headers.join(','),
      ...trades.map(t => headers.map(h => {
        const val = t[h as keyof Trade];
        return val === null || val === undefined ? '' : String(val);
      }).join(','))
    ].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `trading_history_${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Trading History</h2>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-gray-500" />
            <select value={modeFilter} onChange={e => setModeFilter(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-sm text-gray-200">
              <option value="">All Modes</option>
              <option value="backtest">Backtest</option>
              <option value="paper">Paper</option>
              <option value="live">Live</option>
            </select>
          </div>
          <button onClick={exportCSV}
            className="flex items-center gap-2 bg-gray-700 hover:bg-gray-600 text-white px-3 py-1.5 rounded-lg text-sm">
            <Download size={14} /> Export CSV
          </button>
        </div>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-emerald-400" />
          </div>
        ) : trades.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-gray-500 border-b border-gray-800 bg-gray-900/80 sticky top-0">
                <tr>
                  <th className="text-left py-2.5 px-3">ID</th>
                  <th className="text-left py-2.5 px-3">Date/Time</th>
                  <th className="text-left py-2.5 px-3">Mode</th>
                  <th className="text-left py-2.5 px-3">Pair</th>
                  <th className="text-left py-2.5 px-3">Side</th>
                  <th className="text-right py-2.5 px-3">Entry Price</th>
                  <th className="text-right py-2.5 px-3">Quantity</th>
                  <th className="text-right py-2.5 px-3">Fee</th>
                  <th className="text-right py-2.5 px-3">Slippage</th>
                  <th className="text-right py-2.5 px-3">P&L</th>
                  <th className="text-right py-2.5 px-3">Bal Before</th>
                  <th className="text-right py-2.5 px-3">Bal After</th>
                  <th className="text-center py-2.5 px-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {trades.map(t => (
                  <tr key={t.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-1.5 px-3 text-gray-500">{t.id}</td>
                    <td className="py-1.5 px-3 text-gray-400">{t.timestamp?.slice(0, 19)}</td>
                    <td className="py-1.5 px-3">
                      <span className={`px-1.5 py-0.5 rounded text-xs ${
                        t.mode === 'live' ? 'bg-red-500/20 text-red-400' :
                        t.mode === 'paper' ? 'bg-blue-500/20 text-blue-400' :
                        'bg-gray-700 text-gray-400'
                      }`}>{t.mode}</span>
                    </td>
                    <td className="py-1.5 px-3 text-gray-300">{t.symbol}</td>
                    <td className={`py-1.5 px-3 font-medium ${t.side === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>{t.side}</td>
                    <td className="py-1.5 px-3 text-right text-gray-300">{Number(t.price).toFixed(2)}</td>
                    <td className="py-1.5 px-3 text-right text-gray-300">{Number(t.quantity).toFixed(6)}</td>
                    <td className="py-1.5 px-3 text-right text-gray-500">{Number(t.fee).toFixed(4)}</td>
                    <td className="py-1.5 px-3 text-right text-gray-500">{Number(t.slippage).toFixed(4)}</td>
                    <td className={`py-1.5 px-3 text-right font-medium ${Number(t.pnl) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {Number(t.pnl).toFixed(4)}
                    </td>
                    <td className="py-1.5 px-3 text-right text-gray-400">{Number(t.balance_before).toFixed(4)}</td>
                    <td className="py-1.5 px-3 text-right text-gray-300">{Number(t.balance_after).toFixed(4)}</td>
                    <td className="py-1.5 px-3 text-center text-gray-500">{t.model_action ?? '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12 text-gray-600 text-sm">
            No trades found. Run a backtest or start trading to see history.
          </div>
        )}
      </div>

      <div className="text-xs text-gray-600 text-center">
        Showing {trades.length} trades {modeFilter ? `(filtered: ${modeFilter})` : '(all modes)'}
      </div>
    </div>
  );
}
