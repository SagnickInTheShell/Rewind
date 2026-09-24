import { Navigate, Route, Routes } from "react-router-dom";
import { TopBar } from "./components/ui/TopBar";
import UploadPage from "./pages/UploadPage";
import AnalysisPage from "./pages/AnalysisPage";
import RewindPage from "./pages/RewindPage";
import FixturesPage from "./pages/FixturesPage";

export default function App() {
  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <main className="min-h-0 flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/analysis" element={<AnalysisPage />} />
          <Route path="/rewind" element={<RewindPage />} />
          <Route path="/dev/fixtures" element={<FixturesPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
