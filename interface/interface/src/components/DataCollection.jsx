import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './DataCollection.css';

function DataCollection() {
  const [metrics, setMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await fetch("http://localhost:8000/metrics");
        const data = await response.json();
        setMetrics(data);
        setHistory(prev => [
          ...prev.slice(-19),
          {
            time: new Date().toLocaleTimeString(),
            cpu: data.cpu_usage,
            ram: data.ram_usage
          }
        ]);
      } catch (err) {
        console.error("Error fetching metrics:", err);
      }
    };

    const fetchAlerts = async () => {
      try {
        const response = await fetch("http://localhost:8000/alerts");
        const data = await response.json();
        setAlerts(data);
      } catch (err) {
        console.error("Error fetching alerts:", err);
      }
    };

    fetchMetrics();
    fetchAlerts();

    const metricInterval = setInterval(fetchMetrics, 5000);
    const alertInterval = setInterval(fetchAlerts, 7000);

    return () => {
      clearInterval(metricInterval);
      clearInterval(alertInterval);
    };
  }, []);

  const exportAlertsToCSV = () => {
    if (!alerts || alerts.length === 0) return;
    const headers = ['Timestamp,Level,Message'];
    const rows = alerts.map(alert =>
      `${alert.timestamp},${alert.level},${alert.message}`
    );
    const csvContent = [headers, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'system_alerts.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Alerts CSV downloaded');
  };

  const exportMetricsToCSV = () => {
    if (!metrics) return;
    const headers = ['CPU Usage (%)', 'RAM Usage (%)', 'Temperature (°C)', 'Packet Count'];
    const row = [
      `${metrics.cpu_usage},${metrics.ram_usage},${metrics.temperature},${metrics.packet_count}`
    ];
    const csvContent = [headers.join(','), ...row].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', 'current_metrics.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Current metrics CSV downloaded');
  };

  const exportMetricHistoryToCSV = () => {
  if (!history || history.length === 0) return;

  const headers = ['Time', 'CPU Usage (%)', 'RAM Usage (%)'];
  const rows = history.map(row =>
    `${row.time},${row.cpu},${row.ram}`
  );

  const csvContent = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');
  link.setAttribute('href', url);
  link.setAttribute('download', 'metric_history.csv');
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  toast.success('Metric history CSV downloaded');
};

  return (
    <div className="data-layout">
      <aside className="sidebar">
        <h2 className="brand">SecureScape</h2>
        <nav>
          <ul>
            <li className="active">Home</li>
            <li>Devices</li>
            <li>Incidents</li>
            <li>Backups</li>
            <li>Reports</li>
            <li>Settings</li>
            <li>Logout</li>
          </ul>
        </nav>
      </aside>

      <main className="data-main">
        <h2 className="page-title">Data Collection</h2>

        <div className="data-cards">
          <div className="card voltage-card">
            <div className="card-icon">⚡</div>
            <div className="card-label">CPU Usage</div>
            <div className="card-value">{metrics ? `${metrics.cpu_usage}%` : 'Loading...'}</div>
            <button className="export-btn small" onClick={exportMetricsToCSV}>Export Metrics CSV</button>
          </div>

          <div className="card current-card">
            <div className="card-icon">💾</div>
            <div className="card-label">RAM Usage</div>
            <div className="card-value">{metrics ? `${metrics.ram_usage}%` : 'Loading...'}</div>
          </div>

          <div className="card network-card">
            <div className="card-icon">🌡️</div>
            <div className="card-label">Temperature</div>
            <div className="card-value">{metrics ? `${metrics.temperature}°C` : 'Loading...'}</div>
          </div>

          <div className="card network-card">
            <div className="card-icon">📡</div>
            <div className="card-label">Packet Count</div>
            <div className="card-value">{metrics ? metrics.packet_count : 'Loading...'}</div>
          </div>
        </div>

         <div className="metric-section">
  <h3 className="metric-title">Metric Trends (CPU & RAM)</h3>
  
  <div className="metric-chart-container">
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={history}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="time" />
        <YAxis />
        <Tooltip />
        <Legend />
        <Line type="monotone" dataKey="cpu" stroke="#facc15" name="CPU Usage (%)" />
        <Line type="monotone" dataKey="ram" stroke="#f87171" name="RAM Usage (%)" />
      </LineChart>
    </ResponsiveContainer>

    <button className="export-btn small" onClick={exportMetricHistoryToCSV}>
      Export Trend History CSV
    </button>
  </div>
</div>

        <div className="alert-section">
          <h3 className="alert-title">System Alerts</h3>
          <button className="export-btn" onClick={exportAlertsToCSV}>
            Export Alerts to CSV
          </button>
          <table className="alert-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Level</th>
                <th>Message</th>
              </tr>
            </thead>
            <tbody>
              {alerts.length === 0 ? (
                <tr><td colSpan="3">No alerts found.</td></tr>
              ) : (
                alerts.map((alert, index) => (
                  <tr key={index}>
                    <td>{alert.timestamp}</td>
                    <td className={`alert-${alert.level.toLowerCase()}`}>{alert.level}</td>
                    <td>{alert.message}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <ToastContainer position="bottom-right" />
      </main>
    </div>
  );
}

export default DataCollection;
