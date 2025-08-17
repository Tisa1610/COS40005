import React from 'react';
import './ComplianceLogs.css';
import { FaShieldAlt } from 'react-icons/fa';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';

function ComplianceLogs() {
  const handleExport = () => {
    // Dummy CSV export logic
    const headers = ['Timestamp,Action,Status'];
    const rows = ['2025-05-01 10:00,Backup,Success', '2025-05-02 14:22,Audit,Complete'];
    const csvContent = [headers, ...rows].join('\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'compliance_logs.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    toast.success('Compliance logs exported successfully!');
  };

  return (
    <div className="compliance-page">
      <aside className="sidebar">
        <h2 className="logo">SecureScape</h2>
        <nav>
          <ul>
            <li>Home</li>
            <li>Devices</li>
            <li>Incidents</li>
            <li>Backups</li>
            <li className="active">Reports</li>
            <li>Settings</li>
            <li>Logout</li>
          </ul>
        </nav>
      </aside>

      <main className="compliance-main">
        <h1 className="compliance-title">Compliance</h1>
        <div className="compliance-card">
          <FaShieldAlt className="compliance-icon" />
          <h2>Compliance Logs</h2>
          <p>Audit ready logs are active</p>
          <button className="export-btn" onClick={handleExport}>Export Logs</button>
        </div>
        <ToastContainer position="bottom-right" />
      </main>
    </div>
  );
}

export default ComplianceLogs;
