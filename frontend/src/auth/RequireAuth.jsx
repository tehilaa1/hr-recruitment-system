import { Loader2 } from 'lucide-react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from './AuthContext';

/* Route guard: renders child routes only for authorized users (optionally with a given role) */
export default function RequireAuth({ role }) {
  const { profile, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <Loader2 className="h-8 w-8 text-blue-500 animate-spin" />
      </div>
    );
  }
  if (!profile) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  if (role && profile.role !== role) {
    return <Navigate to="/" replace />;
  }
  return <Outlet />;
}
