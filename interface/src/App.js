import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import Layout from "./components/Layout";
import Dashboard from "./components/Dashboard";
import DataCollection from "./components/DataCollection";
import ComplianceLogs from "./components/ComplianceLogs";
import Settings from "./components/Settings";
import Auth from "./components/Auth"; // login/signup screen

function App() {
  return (
    <Router>
      <Routes>
        {/* Public (optional) auth routes */}
        <Route path="/auth" element={<Auth />} />

        {/* App shell */}
        <Route path="/" element={<Layout />}>
          {/* Default: dashboard (home) */}
          <Route index element={<Dashboard />} />
          <Route path="dashboard" element={<Dashboard />} />

          {/* Other pages */}
          <Route path="data-collection" element={<DataCollection />} />
          <Route path="compliance-logs" element={<ComplianceLogs />} />
          <Route path="settings" element={<Settings />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  );
}

export default App;
