import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "../components/layout/PageHeader";
import SeverityBadge from "../components/SeverityBadge";
import { SEVERITY_BADGE, SEVERITY_ORDER } from "../constants/severity";
import { MOCK_HISTORY } from "../fixtures/mockHistory";
import { formatDate } from "../utils/formatDate";

const PAGE_SIZE = 15;

function HistoryPage() {
  const [selected, setSelected] = useState([]);
  const [page, setPage] = useState(1);

  const toggle = (severity) => {
    setSelected((prev) =>
      prev.includes(severity)
        ? prev.filter((s) => s !== severity)
        : [...prev, severity],
    );
    setPage(1);
  };

  const filtered = useMemo(
    () =>
      selected.length === 0
        ? MOCK_HISTORY
        : MOCK_HISTORY.filter((item) => selected.includes(item.severity)),
    [selected],
  );

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const current = Math.min(page, totalPages);
  const rows = filtered.slice((current - 1) * PAGE_SIZE, current * PAGE_SIZE);

  return (
    <div className="w-full">
      <PageHeader />

      <div className="flex flex-wrap items-center gap-2 mb-4">
        {SEVERITY_ORDER.map((severity) => {
          const active = selected.includes(severity);
          return (
            <button
              key={severity}
              type="button"
              onClick={() => toggle(severity)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-full border transition ${
                active
                  ? "bg-ink text-white border-ink"
                  : "bg-white text-muted border-border hover:border-ink"
              }`}
            >
              {SEVERITY_BADGE[severity].label}
            </button>
          );
        })}

        {selected.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setSelected([]);
              setPage(1);
            }}
            className="text-xs text-muted underline ml-1"
          >
            필터 해제
          </button>
        )}

        <span className="ml-auto text-xs text-muted">
          총 {filtered.length}건
        </span>
      </div>

      <div className="border border-border rounded-lg overflow-hidden bg-white">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-white border-b border-border">
              <tr className="text-left text-xs text-muted">
                <th className="px-4 py-3 font-semibold w-24">등급</th>
                <th className="px-4 py-3 font-semibold w-40 whitespace-nowrap">
                  발생 시각
                </th>
                <th className="px-4 py-3 font-semibold w-36">구역</th>
                <th className="px-4 py-3 font-semibold">분석 내용</th>
                <th className="px-4 py-3 font-semibold w-20" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-10 text-center text-muted">
                    조건에 맞는 이력이 없습니다.
                  </td>
                </tr>
              ) : (
                rows.map((item) => (
                  <tr
                    key={item.id}
                    className="border-b border-border last:border-0 hover:bg-black/[0.02]"
                  >
                    <td className="px-4 py-3">
                      <SeverityBadge severity={item.severity} />
                    </td>
                    <td className="px-4 py-3 text-xs text-muted whitespace-nowrap">
                      {formatDate(item.detectedAt)}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted truncate">
                      {item.zoneName}
                    </td>
                    <td className="px-4 py-3 text-ink">
                      <span className="line-clamp-1 break-keep">
                        {item.vlmDescription}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link
                        to={`/history/${item.id}`}
                        className="text-xs font-semibold text-accent no-underline whitespace-nowrap"
                      >
                        상세
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 mt-4">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={current === 1}
            className="text-xs px-3 py-1.5 rounded-md border border-border bg-white disabled:opacity-40"
          >
            이전
          </button>
          <span className="text-xs text-muted px-2">
            {current} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={current === totalPages}
            className="text-xs px-3 py-1.5 rounded-md border border-border bg-white disabled:opacity-40"
          >
            다음
          </button>
        </div>
      )}
    </div>
  );
}

export default HistoryPage;
