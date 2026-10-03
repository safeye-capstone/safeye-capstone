function GenerateReportButton({
  hasReport,
  generating,
  disabled,
  error,
  onGenerate,
}) {
  return (
    <div className="border border-border rounded-lg bg-white p-4 mb-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs text-muted">
          현재까지의 중간 집계입니다. 최종 리포트는 자정 이후 자동 생성됩니다.
        </p>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating || disabled}
          className="shrink-0 px-3 py-1.5 rounded-md border border-border bg-white text-sm font-bold text-ink disabled:opacity-40"
        >
          {generating
            ? "집계 중..."
            : hasReport
              ? "다시 집계"
              : "오늘 리포트 생성"}
        </button>
      </div>

      {error && (
        <p role="alert" className="text-xs text-danger mt-2 text-right">
          {error}
        </p>
      )}
    </div>
  );
}

export default GenerateReportButton;
