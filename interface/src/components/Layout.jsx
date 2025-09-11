import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import './Layout.css';

export default function Layout() {
  const [open, setOpen] = useState(true);
  const location = useLocation();

  const isMobile = () => window.innerWidth <= 1024;

  // Default: open on desktop, closed on mobile
  useEffect(() => {
    const apply = () => setOpen(!isMobile());
    apply();
    window.addEventListener('resize', apply);
    return () => window.removeEventListener('resize', apply);
  }, []);

  // Lock body scroll when sidebar open on mobile
  useEffect(() => {
    if (isMobile()) {
      document.body.style.overflow = open ? 'hidden' : '';
    } else {
      document.body.style.overflow = '';
    }
    return () => { document.body.style.overflow = ''; };
  }, [open]);

  // Close menu on route change (mobile)
  useEffect(() => {
    if (isMobile()) setOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // Close on Escape (mobile)
  useEffect(() => {
    const onKey = (e) => {
      if (!isMobile()) return;
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  // Close when clicking a link (mobile)
  const handleNavClick = () => {
    if (isMobile()) setOpen(false);
  };

  return (
    <div className={`layout ${open ? 'sidebar-open' : 'sidebar-closed'}`}>
      {/* Mobile toggle */}
      <button
        className="sidebar-toggle"
        aria-label="Toggle sidebar"
        aria-controls="app-sidebar"
        aria-expanded={open}
        onClick={() => setOpen(o => !o)}
      >
        ☰
      </button>

      {/* Dim background on mobile when open */}
      <div
        className="sidebar-overlay"
        onClick={() => setOpen(false)}
        aria-hidden
      />

      {/* Sidebar */}
      <aside className="sidebar" id="app-sidebar">
        <h2 className="logo">SecureScape</h2>
        <nav>
          <ul>
            <li>
              <NavLink to="/dashboard" className={({ isActive }) => (isActive ? 'active-link' : '')} onClick={handleNavClick}>
                🏠 Home
              </NavLink>
            </li>
            <li>
              <NavLink to="/data-collection" className={({ isActive }) => (isActive ? 'active-link' : '')} onClick={handleNavClick}>
                📊 Data Collection
              </NavLink>
            </li>
            <li>
              <NavLink to="/devices" className={({ isActive }) => (isActive ? 'active-link' : '')} onClick={handleNavClick}>
                💻 Devices
              </NavLink>
            </li>
            <li>
              <NavLink to="/incidents" className={({ isActive }) => (isActive ? 'active-link' : '')} onClick={handleNavClick}>
                ⚡ Incidents
              </NavLink>
            </li>
            <li>
              <NavLink to="/backups" className={({ isActive }) => (isActive ? 'active-link' : '')} onClick={handleNavClick}>
                🔐 Backups
              </NavLink>
            </li>
            <li>
              <NavLink to="/compliance-logs" className={({ isActive }) => (isActive ? 'active-link' : '')} onClick={handleNavClick}>
                📄 Compliance Logs
              </NavLink>
            </li>
            <li>
              <NavLink to="/settings" className={({ isActive }) => (isActive ? 'active-link' : '')} onClick={handleNavClick}>
                ⚙️ Settings
              </NavLink>
            </li>
            <li>
              <NavLink to="/logout" className={({ isActive }) => (isActive ? 'active-link' : '')} onClick={handleNavClick}>
                🔌 Logout
              </NavLink>
            </li>
          </ul>
        </nav>
      </aside>

      {/* Main content */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
