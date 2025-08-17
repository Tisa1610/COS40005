import React from 'react';
import './Layout.css';
import { Link } from 'react-router-dom';

function Layout({ children }) {
  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <h2 className="logo">SecureScape</h2>
        <nav>
          <ul>
            <li><Link to="/dashboard">🏠 Home</Link></li>
            <li><Link to="#">💻 Devices</Link></li>
            <li><Link to="#">⚡ Incidents</Link></li>
            <li><Link to="#">🔐 Backups</Link></li>
            <li><Link to="/compliance-logs">📄 Reports</Link></li>
            <li><Link to="#">⚙️ Settings</Link></li>
            <li><Link to="#">🔌 Logout</Link></li>
          </ul>
        </nav>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        {children}
      </main>
    </div>
  );
}

export default Layout;
