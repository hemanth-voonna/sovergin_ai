import { Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Documents from "./pages/Documents";
import RagChat from "./pages/RagChat";
import Agents from "./pages/Agents";
import OCRPage from "./pages/OCRPage";
import ValidationPage from "./pages/ValidationPage";
import SandboxPage from "./pages/SandboxPage";
import SettingsPage from "./pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      {/* Public Login Route */}
      <Route path="/login" element={<Login />} />

      {/* Protected Routes */}
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/chat" element={<RagChat />} />
          <Route path="/agents" element={<Agents />} />
          <Route path="/ocr" element={<OCRPage />} />
          <Route path="/validation" element={<ValidationPage />} />
          <Route path="/sandbox" element={<SandboxPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Route>

      {/* Wildcard Fallback */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}