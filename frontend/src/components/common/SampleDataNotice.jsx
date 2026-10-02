function SampleDataNotice({
  children = "현재 화면은 샘플 데이터입니다. 조회 API 연동 후 실제 데이터가 표시됩니다.",
}) {
  return (
    <div className="mb-4 px-3 py-2 rounded-md bg-warn-bg border border-warn text-xs text-warn">
      {children}
    </div>
  );
}

export default SampleDataNotice;
