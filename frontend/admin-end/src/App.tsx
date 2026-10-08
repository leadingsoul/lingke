import { Routes, Route, Navigate } from 'react-router-dom';
import { ProtectedRoute } from './router';
import AdminLayout from './components/AdminLayout';
import LoginPage from './views/LoginPage';
import DashboardPage from './views/DashboardPage';
import KnowledgePage from './views/KnowledgePage';
import StaffPage from './views/StaffPage';
import TicketPage from './views/TicketPage';
import EvolutionPage from './views/EvolutionPage';
import StatisticsPage from './views/StatisticsPage';
import SystemLogPage from './views/SystemLogPage';

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/knowledge" element={<KnowledgePage />} />
        <Route path="/staff" element={<StaffPage />} />
        <Route path="/tickets" element={<TicketPage />} />
        <Route path="/evolution" element={<EvolutionPage />} />
        <Route path="/statistics" element={<StatisticsPage />} />
        <Route path="/logs" element={<SystemLogPage />} />
      </Route>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}
