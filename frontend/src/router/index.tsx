import { Navigate, Route, Routes } from 'react-router-dom';
import AppShell from '../components/layout/AppShell';
import Attribution from '../pages/Attribution';
import FunnelDefs from '../pages/FunnelDefs';
import FunnelResult from '../pages/FunnelResult';
import Login from '../pages/Login';
import PathAnalysis from '../pages/PathAnalysis';
import { RequireAuth, RequirePermission } from './guards';

function Protected({ permission, children }: { permission: string; children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>
        <RequirePermission permission={permission}>{children}</RequirePermission>
      </AppShell>
    </RequireAuth>
  );
}

export default function AppRouter() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/funnels" replace />} />
      <Route
        path="/funnels"
        element={
          <Protected permission="funnel:read">
            <FunnelDefs />
          </Protected>
        }
      />
      <Route
        path="/results"
        element={
          <Protected permission="run:read">
            <FunnelResult />
          </Protected>
        }
      />
      <Route
        path="/paths"
        element={
          <Protected permission="run:read">
            <PathAnalysis />
          </Protected>
        }
      />
      <Route
        path="/reports"
        element={
          <Protected permission="report:read">
            <Attribution />
          </Protected>
        }
      />
      <Route path="*" element={<Navigate to="/funnels" replace />} />
    </Routes>
  );
}
