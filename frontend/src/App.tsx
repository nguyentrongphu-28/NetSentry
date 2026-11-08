import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Audit from "./pages/Audit";
import Dashboard from "./pages/Dashboard";
import DeviceDetail from "./pages/DeviceDetail";
import Devices from "./pages/Devices";
import Findings from "./pages/Findings";
import Remediation from "./pages/Remediation";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="devices" element={<Devices />} />
        <Route path="devices/:id" element={<DeviceDetail />} />
        <Route path="findings" element={<Findings />} />
        <Route path="remediation" element={<Remediation />} />
        <Route path="audit" element={<Audit />} />
        <Route path="*" element={<div className="state">Page not found.</div>} />
      </Route>
    </Routes>
  );
}
