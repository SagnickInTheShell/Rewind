import { Navigate, Route, Routes } from "react-router-dom";
import { Sidebar } from "./components/layout/Sidebar";
import HomePage from "./pages/HomePage";
import AnalysisPage from "./pages/AnalysisPage";
import RewindPage from "./pages/RewindPage";
import InsightsPage from "./pages/InsightsPage";
import UploadPage from "./pages/UploadPage";
import FixturesPage from "./pages/FixturesPage";

export default function App() {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090D14]">
      {/* Sleek Fixed Left Sidebar */}
      <Sidebar />

      {/* Main Content Area */}
      <main className="flex-1 min-w-0 overflow-y-auto flex flex-col">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/rewind" element={<RewindPage />} />
          <Route path="/insights" element={<InsightsPage />} />
          <Route path="/upload" element={<UploadPage />} />
          <Route path="/dev/fixtures" element={<FixturesPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
