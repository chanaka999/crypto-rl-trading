import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
});

// Settings
export const getSettings = () => api.get('/settings');
export const updateSettings = (data: Record<string, unknown>) => api.post('/settings', data);

// Data
export const downloadData = (data: { symbol: string; timeframe: string; since?: string; until?: string }) =>
  api.post('/data/download', data);

// Model
export const trainModel = (data: Record<string, unknown>) => api.post('/model/train', data);
export const getTrainingStatus = () => api.get('/model/status');
export const evaluateModel = (data: Record<string, unknown>) => api.post('/model/evaluate', data);
export const listModels = () => api.get('/model/list');

// Backtest
export const runBacktest = (data: Record<string, unknown>) => api.post('/backtest/run', data);
export const getBacktestResults = (id: number) => api.get(`/backtest/results/${id}`);
export const listBacktests = () => api.get('/backtest/list');

// Paper Trading
export const startPaper = () => api.post('/paper/start');
export const stopPaper = () => api.post('/paper/stop');
export const resetPaper = () => api.post('/paper/reset');
export const getPaperStatus = () => api.get('/paper/status');

// Live Trading
export const startLive = (confirmed: boolean) => api.post(`/live/start?confirmed=${confirmed}`);
export const stopLive = () => api.post('/live/stop');
export const emergencyStop = () => api.post('/live/emergency-stop');
export const getLiveStatus = () => api.get('/live/status');

// Trades & Metrics
export const getTrades = (params?: { mode?: string; symbol?: string; limit?: number }) =>
  api.get('/trades', { params });
export const getEquityCurve = (params?: { mode?: string; limit?: number }) =>
  api.get('/equity-curve', { params });
export const getMetrics = () => api.get('/metrics');
export const getHealth = () => api.get('/health');

export default api;
