import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import Home from './pages/Home';
import JobDetails from './pages/JobDetails';
import JobsDashboard from './pages/JobsDashboard';
import MaternityLeave from './pages/MaternityLeave';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/jobs" element={<JobsDashboard />} />
        <Route path="/jobs/:jobId" element={<JobDetails />} />
        <Route path="/maternity" element={<MaternityLeave />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
