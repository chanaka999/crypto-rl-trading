import { useEffect, useState } from 'react';
import { trainModel, getTrainingStatus, listModels, downloadData } from '../services/api';
import { Brain, Play, RefreshCw } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface ModelRun {
  id: number;
  model_type: string;
  model_name: string;
  symbol: string;
  timeframe: string;
  total_timesteps: number;
  training_reward: number | null;
  eval_return_pct: number | null;
  eval_sharpe: number | null;
  eval_max_drawdown: number | null;
  status: string;
  created_at: string;
}

interface TrainingStatus {
  running: boolean;
  progress: string;
  result: Record<string, unknown> | null;
}

export default function ModelPage() {
  const [models, setModels] = useState<ModelRun[]>([]);
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus>({ running: false, progress: '', result: null });
  const [modelType, setModelType] = useState('PPO');
  const [timesteps, setTimesteps] = useState(50000);
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [timeframe, setTimeframe] = useState('1h');
  const [since, setSince] = useState('2024-01-01');
  const [until, setUntil] = useState('2024-06-30');
  const [balance, setBalance] = useState(10);
  const [lr, setLr] = useState(0.0003);
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    try {
      const [modelsRes, statusRes] = await Promise.all([
        listModels(),
        getTrainingStatus(),
      ]);
      setModels(modelsRes.data.models || []);
      setTrainingStatus(statusRes.data);
    } catch {
      console.error('Failed to fetch model data');
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const handleTrain = async () => {
    setLoading(true);
    try {
      await downloadData({ symbol, timeframe, since, until });
      await trainModel({
        model_type: modelType,
        total_timesteps: timesteps,
        symbol, timeframe, since, until,
        initial_balance: balance,
        learning_rate: lr,
      });
      await fetchData();
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      alert(err?.response?.data?.detail || 'Training failed');
    } finally {
      setLoading(false);
    }
  };

  const rewardHistory = trainingStatus.result?.reward_history as number[] | undefined;

  return (
    <div className="p-6 space-y-6">
      <h2 className="text-2xl font-bold flex items-center gap-2">
        <Brain size={24} /> Model Training & Evaluation
      </h2>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-300 mb-4">Train New Model</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Model Type</label>
            <select value={modelType} onChange={e => setModelType(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
              {['PPO', 'A2C', 'DQN'].map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Timesteps</label>
            <input type="number" value={timesteps} onChange={e => setTimesteps(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Pair</label>
            <select value={symbol} onChange={e => setSymbol(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
              {['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Timeframe</label>
            <select value={timeframe} onChange={e => setTimeframe(e.target.value)}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200">
              {['1m', '5m', '15m', '1h', '4h', '1d'].map(t => <option key={t} value={t}>{t}</option>)}
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
            <label className="block text-xs text-gray-500 mb-1">Balance</label>
            <input type="number" value={balance} onChange={e => setBalance(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Learning Rate</label>
            <input type="number" step="0.0001" value={lr} onChange={e => setLr(Number(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200" />
          </div>
        </div>
        <div className="mt-4 flex items-center gap-4">
          <button onClick={handleTrain} disabled={loading || trainingStatus.running}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50">
            <Play size={16} /> {trainingStatus.running ? 'Training...' : 'Train Model'}
          </button>
          <button onClick={fetchData} className="flex items-center gap-2 text-gray-400 hover:text-gray-200 text-sm">
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {trainingStatus.running && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 text-blue-400 text-sm">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-400" />
            Training in progress: {trainingStatus.progress}
          </div>
        </div>
      )}

      {trainingStatus.result && !trainingStatus.running && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-3">Latest Training Result</h3>
          {trainingStatus.result.error ? (
            <p className="text-red-400 text-sm">{String(trainingStatus.result.error)}</p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div><span className="text-gray-500">Model:</span> <span className="text-gray-200">{String(trainingStatus.result.model_name || '')}</span></div>
              <div><span className="text-gray-500">Type:</span> <span className="text-gray-200">{String(trainingStatus.result.model_type || '')}</span></div>
              <div><span className="text-gray-500">Reward:</span> <span className="text-emerald-400">{Number(trainingStatus.result.training_reward || 0).toFixed(2)}</span></div>
              <div><span className="text-gray-500">Return:</span> <span className="text-emerald-400">{String((trainingStatus.result.metrics as Record<string, unknown>)?.return_pct || 0)}%</span></div>
            </div>
          )}
        </div>
      )}

      {rewardHistory && rewardHistory.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h3 className="text-sm font-medium text-gray-400 mb-4">Training Reward History</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={rewardHistory.map((r, i) => ({ episode: i, reward: r }))}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
              <XAxis dataKey="episode" stroke="#6b7280" tick={{ fontSize: 10 }} />
              <YAxis stroke="#6b7280" tick={{ fontSize: 10 }} />
              <Tooltip contentStyle={{ backgroundColor: '#111827', border: '1px solid #374151', borderRadius: 8 }} />
              <Line type="monotone" dataKey="reward" stroke="#10b981" dot={false} strokeWidth={1.5} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-400 mb-4">Model Registry</h3>
        {models.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="text-gray-500 border-b border-gray-800">
                <tr>
                  <th className="text-left py-2 px-2">Name</th>
                  <th className="text-left py-2 px-2">Type</th>
                  <th className="text-left py-2 px-2">Symbol</th>
                  <th className="text-right py-2 px-2">Timesteps</th>
                  <th className="text-right py-2 px-2">Reward</th>
                  <th className="text-right py-2 px-2">Return %</th>
                  <th className="text-right py-2 px-2">Sharpe</th>
                  <th className="text-left py-2 px-2">Status</th>
                  <th className="text-left py-2 px-2">Created</th>
                </tr>
              </thead>
              <tbody>
                {models.map(m => (
                  <tr key={m.id} className="border-b border-gray-800/50 hover:bg-gray-800/30">
                    <td className="py-1.5 px-2 text-gray-200 font-medium">{m.model_name}</td>
                    <td className="py-1.5 px-2 text-gray-400">{m.model_type}</td>
                    <td className="py-1.5 px-2 text-gray-400">{m.symbol}</td>
                    <td className="py-1.5 px-2 text-right text-gray-400">{m.total_timesteps.toLocaleString()}</td>
                    <td className="py-1.5 px-2 text-right text-gray-300">{m.training_reward?.toFixed(2) ?? '-'}</td>
                    <td className={`py-1.5 px-2 text-right ${(m.eval_return_pct ?? 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {m.eval_return_pct?.toFixed(2) ?? '-'}%
                    </td>
                    <td className="py-1.5 px-2 text-right text-gray-300">{m.eval_sharpe?.toFixed(2) ?? '-'}</td>
                    <td className="py-1.5 px-2">
                      <span className={`px-2 py-0.5 rounded text-xs ${
                        m.status === 'completed' ? 'bg-emerald-500/20 text-emerald-400' :
                        m.status === 'training' ? 'bg-blue-500/20 text-blue-400' :
                        m.status === 'failed' ? 'bg-red-500/20 text-red-400' :
                        'bg-gray-700 text-gray-400'
                      }`}>
                        {m.status}
                      </span>
                    </td>
                    <td className="py-1.5 px-2 text-gray-500">{m.created_at?.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-gray-600 text-sm text-center py-8">No models trained yet.</p>
        )}
      </div>
    </div>
  );
}
