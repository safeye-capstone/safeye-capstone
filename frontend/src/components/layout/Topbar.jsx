import { useLocation } from "react-router-dom";
import { Menu } from "lucide-react";
import { getPageMeta } from "../../constants/menu";

function Topbar({ onToggleSidebar }) {
  const location = useLocation();
  const { label } = getPageMeta(location.pathname);

  return (
    <header className="h-16 shrink-0 bg-white border-b border-border flex items-center gap-4 px-8">
      <button
        type="button"
        onClick={onToggleSidebar}
        aria-label="사이드바 열기/닫기"
        className="text-muted hover:text-black transition-colors"
      >
        <Menu size={20} />
      </button>

      <h1 className="text-lg font-bold tracking-tight">{label}</h1>
    </header>
  );
}

export default Topbar;
