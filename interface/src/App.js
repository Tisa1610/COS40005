import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';
import DataCollection from './components/DataCollection';
import ComplianceLogs from './components/ComplianceLogs';

function App() {
  return (
    <Router>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/data-collection" element={<DataCollection />} />
        <Route path="/compliance-logs" element={<ComplianceLogs />} />
      </Routes>
    </Router>
  );
}


