import { BrowserRouter, useLocation } from 'react-router-dom';
import { HomePage } from './components/HomePage';
import { BatteryPage } from './components/BatteryPage';
import { HistoryPage } from './components/HistoryPage';
import { SettingsPage } from './components/SettingsPage';
import { BottomNav } from './components/BottomNav';

function AppContent() {
  const location = useLocation();
  const path = location.pathname;

  return (
    <>
      <div style={{ display: path === '/' ? 'block' : 'none' }}>
        <HomePage isActive={path === '/'} />
      </div>
      <div style={{ display: path === '/battery' ? 'block' : 'none' }}>
        <BatteryPage isActive={path === '/battery'} />
      </div>
      <div style={{ display: path === '/history' ? 'block' : 'none' }}>
        <HistoryPage isActive={path === '/history'} />
      </div>
      <div style={{ display: path === '/settings' ? 'block' : 'none' }}>
        <SettingsPage isActive={path === '/settings'} />
      </div>
      <BottomNav />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppContent />
    </BrowserRouter>
  );
}
