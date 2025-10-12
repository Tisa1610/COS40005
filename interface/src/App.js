import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import Layout from "./components/Layout";
import Dashboard from "./components/Dashboard";
import DataCollection from "./components/DataCollection";
import ComplianceLogs from "./components/ComplianceLogs";
import Settings from "./components/Settings";
import Devices from "./components/Devices";
import Auth from "./components/Auth";

function App() {
  return (
    <Router>
      <Routes>
        {/* App shell with sidebar/header */}
        <Route path="/" element={<Layout />}>
          {/* Default: dashboard */}
          <Route index element={<Dashboard />} />
          <Route path="dashboard" element={<Dashboard />} />

          {/* Pages */}
          <Route path="data-collection" element={<DataCollection />} />
          <Route path="compliance-logs" element={<ComplianceLogs />} />
          <Route path="settings" element={<Settings />} />
          <Route path="devices" element={<Devices />} />

          {/* Auth INSIDE layout so menu shows */}
          <Route path="auth" element={<Auth variant="card" startMode="login" />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
