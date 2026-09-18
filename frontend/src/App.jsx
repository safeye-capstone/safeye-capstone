import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import DashboardPage from "./pages/DashboardPage";
import AnalyzeImagePage from "./pages/AnalyzeImagePage";
import AnalyzeVideoPage from "./pages/AnalyzeVideoPage";
import ComingSoonPage from "./pages/ComingSoonPage";
import AppLayout from "./components/layout/AppLayout";
import MonitorPage from "./pages/MonitorPage";
import HistoryPage from "./pages/HistoryPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppLayout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/monitor" element={<MonitorPage />} />
          <Route path="/analyze/image" element={<AnalyzeImagePage />} />
          <Route path="/analyze/video" element={<AnalyzeVideoPage />} />
          <Route path="/history" element={<HistoryPage />} />

          <Route path="/history/:id" element={<ComingSoonPage />} />
          <Route path="/compliance" element={<ComingSoonPage />} />
          <Route path="/compliance/:no" element={<ComingSoonPage />} />
          <Route path="/report" element={<ComingSoonPage />} />
          <Route path="/settings" element={<ComingSoonPage />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
