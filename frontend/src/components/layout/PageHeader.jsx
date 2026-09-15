import { useLocation } from "react-router-dom";
import { getPageMeta } from "../../constants/menu";

function PageHeader({ children }) {
  const { pathname } = useLocation();
  const { label, desc } = getPageMeta(pathname);

  return (
    <div className="mb-6">
      <div className="flex items-center gap-2.5">
        <h2 className="text-[22px] font-bold tracking-tight">{label}</h2>
        {children}
      </div>
      {desc && <p className="mt-1.5 text-[14px] text-muted">{desc}</p>}
    </div>
  );
}

export default PageHeader;
