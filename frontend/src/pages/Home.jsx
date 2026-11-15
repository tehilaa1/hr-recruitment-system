import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import Navbar from '../components/Navbar';
import { HR_MODULES } from '../constants/modules';

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />

      <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="text-center mb-12">
          <h1 className="text-3xl font-bold text-gray-900">ברוכים הבאים ל-HireTrack</h1>
          <p className="text-gray-500 mt-2">בחרו את המודול שברצונכם לנהל</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {HR_MODULES.map(({ key, path, title, description, icon: Icon, accent }) => (
            <Link
              key={key}
              to={path}
              className={`group bg-white rounded-2xl border border-gray-100 shadow-sm p-7 flex flex-col gap-5 transition-all hover:shadow-lg ${accent.ring}`}
            >
              <div className={`w-fit rounded-2xl p-4 ${accent.icon}`}>
                <Icon className="h-8 w-8" />
              </div>
              <div className="flex-1">
                <h2 className="text-xl font-bold text-gray-900">{title}</h2>
                <p className="text-sm text-gray-500 mt-2 leading-relaxed">{description}</p>
              </div>
              <span className={`flex items-center gap-1.5 text-sm font-semibold ${accent.cta}`}>
                כניסה למודול
                <ArrowLeft className="h-4 w-4 transition-transform group-hover:-translate-x-1" />
              </span>
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
