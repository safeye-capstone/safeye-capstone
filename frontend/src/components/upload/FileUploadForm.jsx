import { useId, useRef } from "react";
import { useUploadForm } from "../../hooks/useUploadForm";

function FileUploadForm({
  title,
  accept,
  maxSizeMB,
  hint,
  notice,
  pendingHint,
  upload,
  onSuccess,
  renderPreview,
}) {
  const form = useUploadForm({ maxSizeMB, accept, upload, onSuccess });
  const inputRef = useRef(null);
  const zoneSelectId = useId();

  const uploading = form.status === "uploading";

  const openPicker = () => inputRef.current?.click();

  const handleDropzoneKeyDown = (e) => {
    if (e.target !== e.currentTarget) return;
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openPicker();
    }
  };

  const handleFileChange = (e) => {
    form.selectFile(e.target.files[0]);
    e.target.value = "";
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    form.submit();
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white border border-border rounded-[14px] p-6 max-w-[420px]"
    >
      <h2 className="text-[14.5px] font-bold mb-4">{title}</h2>

      {notice && (
        <p className="text-xs text-warn font-semibold mb-3">{notice}</p>
      )}

      <input
        type="file"
        accept={accept}
        ref={inputRef}
        onChange={handleFileChange}
        className="hidden"
      />

      <div
        role="button"
        tabIndex={0}
        onClick={openPicker}
        onKeyDown={handleDropzoneKeyDown}
        className={`border-2 border-dashed rounded-[10px] p-8 flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors ${
          form.fileError
            ? "border-danger bg-danger-bg"
            : "border-border hover:border-accent hover:bg-accent-bg"
        }`}
      >
        {form.previewUrl ? (
          renderPreview(form.previewUrl)
        ) : (
          <>
            <span className="text-sm font-semibold text-ink">
              클릭하여 파일 선택
            </span>
            <span className="text-xs text-muted">{hint}</span>
          </>
        )}
      </div>

      {form.file && (
        <p className="text-sm text-muted mt-2">
          선택된 파일: {form.file.name} ({form.fileSizeMB.toFixed(1)}MB)
        </p>
      )}
      {form.fileError && (
        <p className="text-danger text-sm font-semibold mt-2">
          {form.fileError}
        </p>
      )}

      {form.file && (
        <div className="mt-4">
          <label
            htmlFor={zoneSelectId}
            className="block text-[13px] font-semibold text-muted mb-1.5"
          >
            구역
          </label>
          <select
            id={zoneSelectId}
            value={form.zoneId}
            onChange={(e) => form.selectZone(e.target.value)}
            disabled={form.zonesLoading}
            className="w-full border border-border rounded-[10px] px-3 py-2.5 text-sm bg-white focus:outline-none focus:border-accent disabled:opacity-50"
          >
            <option value="">
              {form.zonesLoading ? "구역 불러오는 중..." : "구역 선택"}
            </option>
            {form.zones.map((z) => (
              <option key={z.id} value={z.id}>
                {z.zoneName}
              </option>
            ))}
          </select>

          {form.zonesError ? (
            <p className="text-xs text-danger mt-1.5">
              구역 목록을 불러오지 못했습니다.
            </p>
          ) : form.autoMatched ? (
            <p className="text-xs text-safe mt-1.5">
              파일명에서 구역을 자동 인식했습니다.
            </p>
          ) : (
            !form.zoneId && (
              <p className="text-xs text-muted mt-1.5">
                파일명에서 구역을 찾지 못했습니다. 직접 선택해주세요.
              </p>
            )
          )}
        </div>
      )}

      <button
        type="submit"
        disabled={uploading || !form.file}
        className="w-full mt-4 py-3.5 rounded-[10px] bg-accent text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {uploading ? "분석 중..." : "제출"}
      </button>

      {uploading && pendingHint && (
        <p className="text-xs text-muted mt-2">{pendingHint}</p>
      )}

      {form.status === "success" && (
        <p className="text-safe text-sm font-semibold mt-2">업로드 성공</p>
      )}
      {form.status === "error" && (
        <p className="text-danger text-sm font-semibold mt-2">
          {form.errorMessage ?? "업로드 실패. 다시 시도해주세요."}
        </p>
      )}
    </form>
  );
}

export default FileUploadForm;
