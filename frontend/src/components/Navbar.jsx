import { Briefcase } from 'lucide-react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import { HR_MODULES } from '../constants/modules';
import GlobalSearch from './GlobalSearch';
import UserMenu from './UserMenu';

export default function Navbar() {
  const { pathname } = useLocation();
  // Global candidate search (jobs + talent pool) belongs to the candidate modules
  const showSearch = ['/jobs', '/candidates'].some((p) => pathname.startsWith(p));

  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-30 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center h-16 gap-4">
          <Link to="/" className="flex items-center gap-2 flex-shrink-0" title="דף הבית">
            <div className="bg-blue-600 text-white p-1.5 rounded-lg">
              <Briefcase className="h-5 w-5" />
            </div>
            <span className="text-lg font-bold text-gray-900 tracking-tight">HireTrack</span>
          </Link>

          {/* Module tabs */}
          <div className="hidden md:flex items-center gap-1 border-r border-gray-200 pr-4">
            {HR_MODULES.map(({ key, path, title, icon: Icon }) => (
              <NavLink
                key={key}
                to={path}
                title={title}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive || pathname.startsWith(`${path}/`)
                      ? 'bg-gray-100 text-gray-900'
                      : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'
                  }`
                }
              >
                <Icon className="h-4 w-4 flex-shrink-0" />
                {/* The modules don't fit as text next to the search box on mid-size screens */}
                <span className="hidden xl:inline whitespace-nowrap">{title}</span>
              </NavLink>
            ))}
          </div>

          <div className="flex-1 flex justify-end">{showSearch && <GlobalSearch />}</div>
          <UserMenu />
        </div>
      </div>
    </nav>
  );
}
