import { useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import AlertToast from "../AlertToast";
import { useDangerAlerts } from "../../hooks/useDangerAlerts";

function AppLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const { alerts, connected } = useDangerAlerts();

  const toggleSidebar = () => {
    setIsSidebarOpen((prev) => !prev);
  };

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar isOpen={isSidebarOpen} />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar onToggleSidebar={toggleSidebar} />
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet context={{ alerts, connected }} />
        </main>
      </div>
      <AlertToast alerts={alerts} />
    </div>
  );
}

export default AppLayout;
