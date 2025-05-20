import React from 'react';
import './Dashboard.css'; // You’ll create this for styling

function Dashboard() {
  return (
    <div className="dashboard-container">
      {/* Sidebar */}
      <aside className="sidebar">
        <h2>SecureScape</h2>
        <nav>
          <ul>
            <li>Dashboard</li>
            <li>Home</li>
            <li>Devices</li>
            <li>Incidents</li>
            <li>Backups</li>
            <li>Reports</li>
            <li>Settings</li>
            <li>Logout</li>
          </ul>
        </nav>
      </aside>

      {/* Main Dashboard */}
      <main className="main-panel">
        <div className="top-cards">
          <div className="card green">
            <h3>Devices Online</h3>
            <p>124</p>
            <span>Active ransomware</span>
          </div>
          <div className="card purple">
            <h3>Threats Detected</h3>
            <p>5</p>
            <span>In the past 24h</span>
          </div>
          <div className="card blue">
            <h3>Backup Status</h3>
            <p>Active</p>
          </div>
          <div className="card yellow">
            <h3>Compliance</h3>
            <p>98%</p>
          </div>
        </div>

        {/* Graph + Alerts */}
        <div className="middle-section">
          <div className="graph-placeholder">
            <h3>Network Activity</h3>
            <div className="fake-graph">[Graph Placeholder]</div>
          </div>

          <div className="recent-incidents">
            <h3>Recent Incidents</h3>
            <ul>
              <li><strong>8:45 AM</strong> – Malware detected on HMi-3 <span className="badge red">HIGH</span></li>
              <li><strong>7:12 AM</strong> – Unauthorized access <span className="badge yellow">MEDIUM</span></li>
              <li><strong>Yesterday</strong> – Ransomware isolated <span className="badge dark-red">CRITICAL</span></li>
            </ul>
          </div>
        </div>

        {/* Bottom Buttons */}
        <div className="bottom-buttons">
          <button className="secure-btn blue">Secure Communication</button>
          <button className="secure-btn yellow">Secure Communication</button>
        </div>
      </main>
    </div>
  );
}

export default Dashboard;
