import { useState } from 'react';
import { runBacktest, downloadData } from '../services/api';
import { Play, Download } from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, BarChart, Bar
} from 'recharts';

interface BacktestResult {
  run_id: number;
  symbol: string;
  timeframe: string;
  start_date: string;
  end_date: string;
  initial_balance: number;
  final_balance: number;
  net_profit: number;
  return_pct: number;
  max_drawdown: number;
  num_trades: number;
  win_rate: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  sharpe_ratio: number;
  trades: Array<Record<string, unknown>>;
  equity_curve: Array<{ step: number; equity: number; drawdown: number }>;
  monthly_returns: Array<{ month: string; return_pct: number }>;
}

export default function BacktestPage() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [since, setSince] = useState('2024-01-01');
  const [until, setUntil] = useState('2024-06-30');
  const [balance, setBalance] = useState(10);
  const [feePct, setFeePct] = useState(0.1);
  const [slippagePct, setSlippagePct] = useState(0.05);
  const [stopLoss, setStopLoss] = useState(5);
  const [takeProfit, setTakeProfit] = useState(10);
  const [modelName, setModelName] = useState('');
  const [modelType, setModelType] = useState('PPO');
  const [running, setRunning] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [error, setError] = useState('');

  const handleDownload = async () => {
    setDownloading(true);
    setError('');
    try {
      const res = await downloadData({ symbol, timeframe, since, until });
      alert(`Downloaded ${res.data.rows} candles`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Download failed';
      setError(msg);
    } finally {
      setDownloading(false);
    }
  };

  const handleRun = async () => {
    setRunning(true);
    setError('');
    setResult(null);
    try {
      const res = await runBacktest({
        symbol, timeframe, since, until,
        initial_balance: balance,
        fee_pct: feePct,
        slippage_pct: slippagePct,
        stop_loss_pct: stopLoss,
        take_profit_pct: takeProfit,
        model_name: modelName || undefined,
        model_type: modelType,
      });
      setResult(res.data);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail || 'Backtest failed');
    } finally {
      setRunning(false);
    }
  };

  const exportCSV = () => {
    if (!result?.trades) return;
    const headers = ['timestamp', 'side', 'price', 'quantity', 'fee', 'slippage', 'pnl', 'balance_before', 'balance_after'];
    const csv = [headers.join(','), ...result.trades.map(t => headers.map(h => String(t[h] ?? '')).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `backtest_${result.symbol}_${result.start_date}_${result.end_date}.csv`;
    a.click();
  };

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold">Backtesting</h2>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Configuration</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Pair</label>
            <select value={symbol} onChange={e => setSymbol(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
              {['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Timeframe</label>
            <select value={timeframe} onChange={e => setTimeframe(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
              {['1m', '5m', '15m', '1h', '4h', '1d'].map(t => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">From</label>
            <input type="date" value={since} onChange={e => setSince(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Until</label>
            <input type="date" value={until} onChange={e => setUntil(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Initial Balance</label>
            <input type="number" value={balance} onChange={e => setBalance(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Fee %</label>
            <input type="number" step="0.01" value={feePct} onChange={e => setFeePct(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Slippage %</label>
            <input type="number" step="0.01" value={slippagePct} onChange={e => setSlippagePct(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Stop Loss %</label>
            <input type="number" step="0.1" value={stopLoss} onChange={e => setStopLoss(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Take Profit %</label>
            <input type="number" step="0.1" value={takeProfit} onChange={e => setTakeProfit(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Model Name (optional)</label>
            <input type="text" value={modelName} onChange={e => setModelName(e.target.value)} placeholder="Leave empty for random"
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Model Type</label>
            <select value={modelType} onChange={e => setModelType(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
              {['PPO', 'A2C', 'DQN'].map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
        </div>

        <div className="flex gap-3 mt-5">
          <button onClick={handleDownload} disabled={downloading}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
            <Download size={16} />
            {downloading ? 'Downloading...' : 'Download Data'}
          </button>
          <button onClick={handleRun} disabled={running}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
            <Play size={16} />
            {running ? 'Running...' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg p-3 text-sm">{error}</div>
      )}

      {result && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Final Balance</p>
              <p className={`text-lg font-semibold ${result.net_profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                ${result.final_balance.toFixed(4)}
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Return</p>
              <p className={`text-lg font-semibold ${result.return_pct >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                {result.return_pct.toFixed(2)}%
              </p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Max Drawdown</p>
              <p className="text-lg font-semibold text-yellow-400">{result.max_drawdown.toFixed(2)}%</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Win Rate</p>
              <p className="text-lg font-semibold text-gray-200">{result.win_rate.toFixed(1)}%</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Sharpe Ratio</p>
              <p className="text-lg font-semibold text-gray-200">{result.sharpe_ratio.toFixed(2)}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Trades</p>
              <p className="text-lg font-semibold text-gray-200">{result.num_trades}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Avg Win</p>
              <p className="text-lg font-semibold text-emerald-400">${result.avg_win.toFixed(4)}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Avg Loss</p>
              <p className="text-lg font-semibold text-red-400">${result.avg_loss.toFixed(4)}</p>
            </div>
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-3">
              <p className="text-xs text-gray-500">Profit Factor</p>
              <p className="text-lg font-semibold text-gray-200">{result.profit_factor.toFixed(2)}</p>
            </div>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-4">Equity Curve</h3>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={result.equity_curve}>
                <defs>
                  <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="step" stroke="#6b7280" tick={{ fontSize: 10 }} />
                <YAxis stroke="#6b7280" tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }} />
                <Area type="monotone" dataKey="equity" stroke="#10b981" fill="url(#eqGrad)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-4">Drawdown</h3>
            <ResponsiveContainer width="100%" height={150}>
              <AreaChart data={result.equity_curve}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                <XAxis dataKey="step" stroke="#6b7280" tick={{ fontSize: 10 }} />
                <YAxis stroke="#6b7280" tick={{ fontSize: 10 }} />
                <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }} />
                <Area type="monotone" dataKey="drawdown" stroke="#ef4444" fill="#ef444420" strokeWidth={1.5} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {result.monthly_returns && result.monthly_returns.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
              <h3 className="text-sm font-medium text-gray-400 mb-4">Monthly Returns</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={result.monthly_returns}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="month" stroke="#6b7280" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#6b7280" tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }} />
                  <Bar dataKey="return_pct" fill="#10b981" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}

          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-gray-400">Trade History ({result.trades.length})</h3>
              <button onClick={exportCSV}
                className="flex items-center gap-1 text-xs text-emerald-400 hover:text-emerald-300">
                <Download size={14} /> Export CSV
              </button>
            </div>
            <div className="overflow-x-auto max-h-64 overflow-y-auto">
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
                  {result.trades.map((t, i) => (
                    <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                      <td className="py-1.5 px-2 text-gray-400">{String(t.timestamp || '').slice(0, 19)}</td>
                      <td className={`py-1.5 px-2 font-medium ${t.side === 'BUY' ? 'text-emerald-400' : 'text-red-400'}`}>
                        {String(t.side)}
                      </td>
                      <td className="py-1.5 px-2 text-right text-gray-300">{Number(t.price).toFixed(2)}</td>
                      <td className="py-1.5 px-2 text-right text-gray-300">{Number(t.quantity).toFixed(6)}</td>
                      <td className="py-1.5 px-2 text-right text-gray-500">{Number(t.fee).toFixed(4)}</td>
                      <td className={`py-1.5 px-2 text-right font-medium ${Number(t.pnl) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {Number(t.pnl).toFixed(4)}
                      </td>
                      <td className="py-1.5 px-2 text-right text-gray-300">{Number(t.balance_after).toFixed(4)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
