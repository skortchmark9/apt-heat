import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { HomePage } from './components/HomePage';
import { BatteryPage } from './components/BatteryPage';
import { BottomNav } from './components/BottomNav';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/battery" element={<BatteryPage />} />
      </Routes>
      <BottomNav />
    </BrowserRouter>
  );
}
