import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider } from './auth/AuthContext';
import RequireAuth from './auth/RequireAuth';
import Home from './pages/Home';
import JobDetails from './pages/JobDetails';
import JobsDashboard from './pages/JobsDashboard';
import Login from './pages/Login';
import AllCandidates from './pages/AllCandidates';
import AnnualBudget from './pages/AnnualBudget';
import MaternityLeave from './pages/MaternityLeave';
import ResetPassword from './pages/ResetPassword';
import TalentPool from './pages/TalentPool';
import UserManagement from './pages/UserManagement';

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          {/* Public: SMS-verified password reset (also used signed-in to change the password) */}
          <Route path="/reset-password" element={<ResetPassword />} />

          {/* Any authorized user */}
          <Route element={<RequireAuth />}>
            <Route path="/" element={<Home />} />
            <Route path="/jobs" element={<JobsDashboard />} />
            <Route path="/jobs/:jobId" element={<JobDetails />} />
            <Route path="/talent-pool" element={<TalentPool />} />
            <Route path="/candidates" element={<AllCandidates />} />
            <Route path="/maternity" element={<MaternityLeave />} />
            <Route path="/budgets" element={<AnnualBudget />} />
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
