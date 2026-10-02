import { useLocation } from "react-router-dom";
import { Hammer, Check } from "lucide-react";
import { getPageMeta } from "../constants/menu";
import PageHeader from "../components/layout/PageHeader";

export default function ComingSoonPage() {
  const { pathname } = useLocation();
  const meta = getPageMeta(pathname);

  return (
    <div className="max-w-5xl">
      <PageHeader>
        <span
          className="flex items-center gap-1 px-2 py-1 rounded-md text-[11.5px]
        font-bold bg-warn-bg text-warn"
        >
          <Hammer size={12} /> 개발 예정
        </span>
      </PageHeader>

      {meta.preview?.length > 0 && (
        <div className="rounded-[14px] border border-border bg-white p-6 mb-6">
          <h3 className="text-[15px] font-bold mb-4">이 화면에 들어갈 기능</h3>
          <ul className="space-y-2.5">
            {meta.preview.map((f) => (
              <li
                key={f}
                className="flex items-start gap-2.5 text-[14px] text-muted"
              >
                <span
                  className="mt-0.5 w-4 h-4 rounded-full bg-border flex items-center
                                justify-center shrink-0"
                >
                  <Check size={11} className="text-muted" />
                </span>
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="relative rounded-[14px] border border-border bg-white p-6 overflow-hidden">
        <div className="opacity-40 animate-pulse select-none pointer-events-none">
          <div className="grid grid-cols-4 gap-4 mb-6">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="rounded-lg border border-border p-4">
                <div className="h-2.5 w-14 rounded bg-border mb-3" />
                <div className="h-6 w-16 rounded bg-muted/40" />
              </div>
            ))}
          </div>
          <div className="h-2.5 w-24 rounded bg-border mb-4" />
          <div className="space-y-2.5">
            {["w-3/4", "w-2/3", "w-3/5", "w-1/2", "w-2/5"].map((w, i) => (
              <div key={i} className="flex gap-3">
                <div className="h-9 w-9 rounded bg-border shrink-0" />
                <div className="flex-1 space-y-2 py-1">
                  <div className={`h-2.5 rounded bg-border ${w}`} />
                  <div className="h-2.5 w-1/3 rounded bg-border/60" />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div
          className="absolute inset-0 flex items-center justify-center
        bg-gradient-to-b from-white/50 to-white/90"
        >
          <span className="text-[13px] font-semibold text-muted">
            화면 레이아웃 준비 중
          </span>
        </div>
      </div>
    </div>
  );
}
