import { useEffect, useState } from 'react';
import { getSettings, updateSettings } from '../services/api';
import { Save, AlertTriangle } from 'lucide-react';

export default function SettingsPage() {
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [warnings, setWarnings] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getSettings().then(res => {
      setSettings(res.data.settings || {});
      setWarnings(res.data.warnings || []);
    });
  }, []);

  const handleChange = (key: string, value: string) => {
    setSettings(prev => ({ ...prev, [key]: value }));
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(settings)) {
        if (v === 'true' || v === 'false') payload[k] = v === 'true';
        else if (!isNaN(Number(v)) && v !== '') payload[k] = Number(v);
        else payload[k] = v;
      }
      await updateSettings(payload);
      setSaved(true);
      const res = await getSettings();
      setWarnings(res.data.warnings || []);
    } finally {
      setSaving(false);
    }
  };

  const groups = [
    {
      title: 'Trading Configuration',
      fields: [
        { key: 'symbol', label: 'Trading Pair', type: 'select', options: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT', 'DOGE/USDT', 'ADA/USDT'] },
        { key: 'timeframe', label: 'Timeframe', type: 'select', options: ['1m', '5m', '15m', '1h', '4h', '1d'] },
        { key: 'trading_mode', label: 'Trading Mode', type: 'select', options: ['backtest', 'paper', 'live'] },
        { key: 'initial_balance', label: 'Initial Balance (USDT)', type: 'number' },
      ],
    },
    {
      title: 'Fee & Slippage',
      fields: [
        { key: 'fee_pct', label: 'Fee %', type: 'number' },
        { key: 'slippage_pct', label: 'Slippage %', type: 'number' },
        { key: 'min_profit_over_fees', label: 'Min Profit > Fees', type: 'toggle' },
      ],
    },
    {
      title: 'Risk Management',
      fields: [
        { key: 'max_position_pct', label: 'Max Position Size %', type: 'number' },
        { key: 'stop_loss_pct', label: 'Stop Loss %', type: 'number' },
        { key: 'take_profit_pct', label: 'Take Profit %', type: 'number' },
        { key: 'daily_max_loss_pct', label: 'Daily Max Loss %', type: 'number' },
        { key: 'max_drawdown_stop_pct', label: 'Max Drawdown Stop %', type: 'number' },
        { key: 'cooldown_seconds', label: 'Cooldown (seconds)', type: 'number' },
        { key: 'monthly_target_return_pct', label: 'Monthly Target Return %', type: 'number' },
        { key: 'min_confidence_threshold', label: 'Min Confidence Threshold', type: 'number' },
      ],
    },
    {
      title: 'Binance API (Live Trading)',
      fields: [
        { key: 'binance_api_key', label: 'API Key', type: 'password' },
        { key: 'binance_api_secret', label: 'API Secret', type: 'password' },
        { key: 'live_trading_enabled', label: 'Enable Live Trading', type: 'toggle' },
      ],
    },
  ];

  return (
    <div className="p-6 space-y-6 max-w-4xl">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Settings</h2>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50 transition-colors"
        >
          <Save size={16} />
          {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Settings'}
        </button>
      </div>

      {warnings.length > 0 && (
        <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 text-yellow-400 font-medium text-sm mb-2">
            <AlertTriangle size={16} />
            Warnings
          </div>
          {warnings.map((w, i) => (
            <p key={i} className="text-xs text-yellow-400/80 mt-1">{w}</p>
          ))}
        </div>
      )}

      {groups.map(group => (
        <div key={group.title} className="bg-gray-900 border border-gray-800 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-300 mb-4">{group.title}</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {group.fields.map(field => (
              <div key={field.key}>
                <label className="block text-xs text-gray-500 mb-1">{field.label}</label>
                {field.type === 'select' ? (
                  <select
                    value={settings[field.key] || ''}
                    onChange={e => handleChange(field.key, e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
                  >
                    {field.options?.map(opt => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : field.type === 'toggle' ? (
                  <button
                    onClick={() => handleChange(field.key, settings[field.key] === 'true' ? 'false' : 'true')}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      settings[field.key] === 'true' ? 'bg-emerald-600' : 'bg-gray-700'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                        settings[field.key] === 'true' ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                ) : (
                  <input
                    type={field.type === 'password' ? 'password' : 'text'}
                    value={settings[field.key] || ''}
                    onChange={e => handleChange(field.key, e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm text-gray-200 focus:outline-none focus:border-emerald-500"
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
