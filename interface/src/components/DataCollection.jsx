import React, { useEffect, useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';
import { ToastContainer, toast } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './DataCollection.css';

const API_BASE = 'http://localhost:8000'; // keep for dev; switch to env later

function DataCollection() {
  const [metrics, setMetrics] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [history, setHistory] = useState([]);
  const [paused, setPaused] = useState(false);
  const [error, setError] = useState(null);

  // load saved trend on mount
  useEffect(() => {
    const saved = localStorage.getItem('metricHistory');
    if (saved) {
      try { setHistory(JSON.parse(saved)); } catch {}
    }
  }, []);

  // save trend whenever updated
  useEffect(() => {
    if (history.length) {
      localStorage.setItem('metricHistory', JSON.stringify(history));
    }
  }, [history]);

  useEffect(() => {
    let isMounted = true;
    const fetchMetrics = async () => {
      try {
        const res = await fetch(`${API_BASE}/metrics`);
        if (!res.ok) throw new Error(`metrics ${res.status}`);
        const data = await res.json();
        if (!isMounted) return;
        setMetrics(data);

        if (!paused) {
          setHistory(prev => {
            const next = [
              ...prev.slice(-19),
              {
                time: new Date().toLocaleTimeString(),
                cpu: data.cpu_usage,
                ram: data.ram_usage
              }
            ];
            return next;
          });
        }
        setError(null);
      } catch (err) {
        console.error('Error fetching metrics:', err);
        setError('Could not load metrics');
      }
    };

    const fetchAlerts = async () => {
      try {
        const res = await fetch(`${API_BASE}/alerts`);
        if (!res.ok) throw new Error(`alerts ${res.status}`);
        const data = await res.json();
        if (!isMounted) return;
        setAlerts(data);
      } catch (err) {
        console.error('Error fetching alerts:', err);
      }
    };

    // initial pull
    fetchMetrics();
    fetchAlerts();

    // intervals
    const metricInterval = setInterval(fetchMetrics, 5000);
    const alertInterval = setInterval(fetchAlerts, 7000);

    return () => {
      isMounted = false;
      clearInterval(metricInterval);
      clearInterval(alertInterval);
    };
  }, [paused]);

  const exportAlertsToCSV = () => {
    if (!alerts || alerts.length === 0) return;
    const headers = ['Timestamp,Level,Message'];
    const rows = alerts.map(a => `${a.timestamp},${a.level},${a.message}`);
    const csvContent = [headers, ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'system_alerts.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Alerts CSV downloaded');
  };

  const exportMetricsToCSV = () => {
    if (!metrics) return;
    const headers = ['CPU Usage (%)', 'RAM Usage (%)', 'Temperature (°C)', 'Packet Count'];
    const row = `${metrics.cpu_usage},${metrics.ram_usage},${metrics.temperature},${metrics.packet_count}`;
    const csvContent = [headers.join(','), row].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'current_metrics.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Current metrics CSV downloaded');
  };

  const exportMetricHistoryToCSV = () => {
    if (!history || history.length === 0) return;
    const headers = ['Time', 'CPU Usage (%)', 'RAM Usage (%)'];
    const rows = history.map(r => `${r.time},${r.cpu},${r.ram}`);
    const csvContent = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'metric_history.csv';
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    toast.success('Metric history CSV downloaded');
  };

  return (
    <div className="data-layout">
      {/* Sidebar comes from Layout.jsx; only main content here */}
      <main className="data-main">
        <h2 className="page-title">Data Collection</h2>

        {error && <div className="error-banner">API error: {error}</div>}

        <div className="data-cards">
          <div className="card voltage-card">
            <div className="card-icon">⚡</div>
            <div className="card-label">CPU Usage</div>
            <div className="card-value">
              {metrics ? `${metrics.cpu_usage}%` : 'Loading...'}
            </div>
            <button className="export-btn small" onClick={exportMetricsToCSV}>
              Export Metrics CSV
            </button>
          </div>

          <div className="card current-card">
            <div className="card-icon">💾</div>
            <div className="card-label">RAM Usage</div>
            <div className="card-value">
              {metrics ? `${metrics.ram_usage}%` : 'Loading...'}
            </div>
          </div>

          <div className="card network-card">
            <div className="card-icon">🌡️</div>
            <div className="card-label">Temperature</div>
            <div className="card-value">
              {metrics ? `${metrics.temperature}°C` : 'Loading...'}
            </div>
          </div>

          <div className="card network-card">
            <div className="card-icon">📡</div>
            <div className="card-label">Packet Count</div>
            <div className="card-value">
              {metrics ? metrics.packet_count : 'Loading...'}
            </div>
          </div>
        </div>

        <div className="metric-section">
          <div className="metric-header">
            <h3 className="metric-title">Metric Trends (CPU & RAM)</h3>
            <div className="metric-controls">
              <button className="export-btn small" onClick={() => setPaused(p => !p)}>
                {paused ? 'Resume Live' : 'Pause Live'}
              </button>
              <button className="export-btn small" onClick={exportMetricHistoryToCSV}>
                Export Trend History CSV
              </button>
            </div>
          </div>

          <div className="metric-chart-container">
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" minTickGap={40} />
                <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} />
                <Tooltip
                  formatter={(v, name) =>
                    name.includes('CPU') || name.includes('RAM') ? [`${v}%`, name] : [v, name]
                  }
                />
                <Legend />
                <Line type="monotone" dataKey="cpu" stroke="#facc15" name="CPU Usage (%)" dot={false} />
                <Line type="monotone" dataKey="ram" stroke="#f87171" name="RAM Usage (%)" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="alert-section">
          <div className="alert-header">
            <h3 className="alert-title">System Alerts</h3>
            <button className="export-btn" onClick={exportAlertsToCSV}>
              Export Alerts to CSV
            </button>
          </div>

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
                alerts.slice().reverse().map((alert, index) => (
                  <tr key={index}>
                    <td>{alert.timestamp}</td>
                    <td>
                      <span className={`badge badge-${alert.level.toLowerCase()}`}>
                        {alert.level}
                      </span>
                    </td>
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
