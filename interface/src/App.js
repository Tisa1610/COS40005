import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './components/Dashboard';
import DataCollection from './components/DataCollection';
import ComplianceLogs from './components/ComplianceLogs';

// Placeholder: Prepared for backend integration (8010 endpoints)
function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Layout />}>
          {/* Default route */}
          <Route index element={<Dashboard />} />

          {/* Page routes */}
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="data-collection" element={<DataCollection />} />
          <Route path="compliance-logs" element={<ComplianceLogs />} />
        </Route>

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Router>
  );
}

export default App;
