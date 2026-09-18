import { useState, useRef } from "react";
import { useOutletContext } from "react-router-dom";
import {
  UPLOAD_IMAGE_ENDPOINT,
  MAX_IMAGE_SIZE_MB,
  API_BASE,
} from "../constants/config";
import { getApiErrorMessage } from "../utils/apiError";
import { matchZone } from "../utils/zone";
import { useZones } from "../hooks/useZones";

function PhotoUploadForm({ onResult }) {
  const { pushAlert } = useOutletContext() ?? {};
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null); // "success" | "error" | null
  const [errorMessage, setErrorMessage] = useState(null);
  const [fileError, setFileError] = useState(null);
  const { zones } = useZones();
  const [zoneId, setZoneId] = useState("");
  const [autoMatched, setAutoMatched] = useState(false);

  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setUploadStatus(null);

    if (!file) {
      setSelectedFile(null);
      setPreviewUrl(null);
      setZoneId("");
      setAutoMatched(false);
      return;
    }

    const sizeMB = file.size / (1024 * 1024);

    if (sizeMB > MAX_IMAGE_SIZE_MB) {
      setFileError(
        `파일이 너무 큽니다 (${sizeMB.toFixed(1)}MB). ${MAX_IMAGE_SIZE_MB}MB 이하만 가능합니다.`,
      );
      setSelectedFile(null);
      setPreviewUrl(null);
      setZoneId("");
      setAutoMatched(false);
      return;
    }

    setFileError(null);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));

    const hit = matchZone(zones, file.name);
    setZoneId(hit?.id ?? "");
    setAutoMatched(Boolean(hit));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    if (!zoneId) {
      setErrorMessage("구역을 선택해주세요.");
      setUploadStatus("error");
      return;
    }

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("zoneId", zoneId);

    setUploading(true);
    setUploadStatus(null);

    try {
      const response = await fetch(`${API_BASE}${UPLOAD_IMAGE_ENDPOINT}`, {
        method: "POST",
        body: formData,
      });

      if (response.status === 413) {
        throw new Error("파일 용량이 서버 제한을 초과했습니다.");
      }

      const json = await response.json();

      if (!response.ok || !json.success) {
        throw new Error(getApiErrorMessage(json, "업로드 실패"));
      }

      const data = json.data;
      onResult?.(data);

      if (
        pushAlert &&
        (data.severity === "CRITICAL" || data.severity === "WARNING")
      ) {
        pushAlert(data);
      }

      setUploadStatus("success");
    } catch (error) {
      console.error("전송 실패:", error);
      setErrorMessage(error.message);
      setUploadStatus("error");
    } finally {
      setUploading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white border border-border rounded-[14px] p-6 max-w-[420px]"
    >
      <h2 className="text-[14.5px] font-bold mb-4">이미지 업로드</h2>

      <input
        type="file"
        accept=".jpg, .jpeg, .png, .webp"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
      />

      <div
        onClick={() => fileInputRef.current.click()}
        className="border-2 border-dashed border-border rounded-[10px] p-8 flex flex-col items-center justify-center gap-2 cursor-pointer hover:border-accent hover:bg-accent-bg transition-colors"
      >
        {previewUrl ? (
          <img
            src={previewUrl}
            alt="미리보기"
            className="max-w-full max-h-[220px] block rounded-[8px]"
          />
        ) : (
          <>
            <span className="text-sm font-semibold text-ink">
              클릭하여 이미지 선택
            </span>
            <span className="text-xs text-muted">
              JPG, PNG, WEBP • 최대 {MAX_IMAGE_SIZE_MB}MB
            </span>
          </>
        )}
      </div>

      {selectedFile && (
        <p className="text-sm text-muted mb-2">
          선택된 파일: {selectedFile.name} (
          {(selectedFile.size / (1024 * 1024)).toFixed(1)}MB)
        </p>
      )}
      {fileError && (
        <p className="text-danger text-sm font-semibold mt-2">{fileError}</p>
      )}

      {selectedFile && (
        <div>
          <label>구역</label>
          <select
            value={zoneId}
            onChange={(e) => {
              setZoneId(e.target.value);
              setAutoMatched(false);
            }}
          >
            <option value="">구역 선택</option>
            {zones.map((z) => (
              <option key={z.id} value={z.id}>
                {z.zoneName}
              </option>
            ))}
          </select>

          {autoMatched ? (
            <p>파일명에서 구역을 자동 인식했습니다.</p>
          ) : (
            <p>파일명에서 구역을 찾지 못했습니다. 직접 선택해주세요.</p>
          )}
        </div>
      )}

      <button
        type="submit"
        disabled={uploading || !selectedFile}
        className="w-full mt-4 py-3.5 rounded-[10px] bg-accent text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {uploading ? "업로드 중..." : "제출"}
      </button>

      {uploadStatus === "success" && (
        <p className="text-safe text-sm font-semibold mt-2">업로드 성공</p>
      )}
      {uploadStatus === "error" && (
        <p className="text-danger text-sm font-semibold mt-2">
          {errorMessage ?? "업로드 실패. 다시 시도해주세요."}
        </p>
      )}
    </form>
  );
}

export default PhotoUploadForm;
