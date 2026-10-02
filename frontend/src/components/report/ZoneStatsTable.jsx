function ZoneStatsTable({ zoneStats }) {
  const rows = zoneStats ?? [];

  return (
    <section className="border border-border rounded-lg bg-white p-5">
      <h2 className="text-[13px] font-bold text-ink mb-4">구역별 통계</h2>

      {rows.length === 0 ? (
        <p className="text-sm text-muted">구역별 집계가 없습니다.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-xs text-muted text-left">
              <th className="py-2 font-normal">구역</th>
              <th className="py-2 font-normal text-right">분석</th>
              <th className="py-2 font-normal text-right">확정 위험</th>
              <th className="py-2 font-normal text-right">검토 대기</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((zone) => (
              <tr
                key={zone.zoneId}
                className="border-b border-border last:border-b-0"
              >
                <td className="py-2 text-ink">{zone.zoneName}</td>
                <td className="py-2 text-right text-ink">
                  {zone.analyzedCount ?? 0}
                </td>
                <td className="py-2 text-right text-ink">
                  {zone.confirmedCount ?? 0}
                </td>
                <td className="py-2 text-right text-ink">
                  {zone.reviewRequiredCount ?? 0}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

export default ZoneStatsTable;
