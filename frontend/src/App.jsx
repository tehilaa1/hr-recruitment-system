import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import RequireAuth from './auth/RequireAuth';
import Home from './pages/Home';
import JobDetails from './pages/JobDetails';
import JobsDashboard from './pages/JobsDashboard';
import Login from './pages/Login';
import MaternityLeave from './pages/MaternityLeave';
import UserManagement from './pages/UserManagement';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />

          {/* Any authorized user */}
          <Route element={<RequireAuth />}>
            <Route path="/" element={<Home />} />
            <Route path="/jobs" element={<JobsDashboard />} />
            <Route path="/jobs/:jobId" element={<JobDetails />} />
            <Route path="/maternity" element={<MaternityLeave />} />
          </Route>

          {/* Admins only */}
          <Route element={<RequireAuth role="admin" />}>
            <Route path="/admin/users" element={<UserManagement />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
