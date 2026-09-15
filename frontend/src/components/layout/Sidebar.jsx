import { NavLink } from "react-router-dom";
import { MENU_GROUPS } from "../../constants/menu";

export default function Sidebar({ isOpen = true }) {
  const collapsed = !isOpen;
  return (
    <aside
      className={`${collapsed ? "w-[76px]" : "w-[260px]"} shrink-0 flex flex-col
    bg-sidebar px-4 py-6 overflow-hidden
    transition-[width] duration-200`}
    >
      <div className="flex items-center gap-2.5 px-3 pt-2 pb-7">
        <div className="w-8 h-8 rounded-lg bg-brand shrink-0" />
        {!collapsed && (
          <span className="text-white font-bold text-[17px] tracking-tight whitespace-nowrap">
            SAFEye
          </span>
        )}
      </div>

      <nav className="flex-1 min-h-0 overflow-auto">
        {MENU_GROUPS.map((group, gi) => (
          <div key={group.id}>
            {gi > 0 && <div className="h-px bg-sidebar-divider mx-2 my-3" />}
            {group.items.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.id}
                  to={item.path}
                  end={item.path === "/"}
                  title={item.label}
                  className={({ isActive }) =>
                    `flex items-center gap-3 p-3 mb-1 rounded-[10px] transition-colors whitespace-nowrap overflow-hidden ${
                      isActive
                        ? "bg-sidebar-active text-white"
                        : "text-sidebar-text hover:bg-sidebar-hover"
                    }`
                  }
                >
                  <Icon size={20} className="shrink-0" />
                  {!collapsed && (
                    <>
                      <span className="text-[14.5px] font-semibold whitespace-nowrap">
                        {item.label}
                      </span>
                      {!item.ready && (
                        <span
                          className="ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded 
                    bg-sidebar-hover text-sidebar-muted"
                        >
                          준비중
                        </span>
                      )}
                    </>
                  )}
                </NavLink>
              );
            })}
          </div>
        ))}
      </nav>
      {!collapsed && (
        <div className="shrink-0 px-3 pt-3 text-[11.5px] leading-relaxed text-sidebar-muted">
          © 2026 SAFEye
          <br />
          안전관리 지원 시스템
        </div>
      )}
    </aside>
  );
}
