import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Overview from './pages/Overview';
import SettingsPage from './pages/SettingsPage';
import BacktestPage from './pages/BacktestPage';
import PaperPage from './pages/PaperPage';
import LivePage from './pages/LivePage';
import ModelPage from './pages/ModelPage';
import HistoryPage from './pages/HistoryPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Overview />} />
          <Route path="/settings" element={<SettingsPage />} />
          <Route path="/backtest" element={<BacktestPage />} />
          <Route path="/paper" element={<PaperPage />} />
          <Route path="/live" element={<LivePage />} />
          <Route path="/model" element={<ModelPage />} />
          <Route path="/history" element={<HistoryPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
