import { useState, useRef } from "react";
import { DEV_ZONE_ID, UPLOAD_VIDEO_ENDPOINT, MAX_VIDEO_SIZE_MB } from "../constants/config";
import { getApiErrorMessage } from "../utils/apiError";

function VideoUploadForm() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);
  const [fileError, setFileError] = useState(null);

  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setUploadStatus(null);

    if (!file) {
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    const sizeMB = file.size / (1024 * 1024);
    if (sizeMB > MAX_VIDEO_SIZE_MB) {
      setFileError(
        `파일이 너무 큽니다 (${sizeMB.toFixed(1)}MB). ${MAX_VIDEO_SIZE_MB}MB 이하만 가능합니다.`,
      );
      setSelectedFile(null);
      setPreviewUrl(null);
      return;
    }

    setFileError(null);
    setSelectedFile(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append("file", selectedFile);
    formData.append("zoneId", DEV_ZONE_ID);

    setUploading(true);
    setUploadStatus(null);

    try {
      const response = await fetch(
        `${import.meta.env.VITE_API_URL}${UPLOAD_VIDEO_ENDPOINT}`,
        {
          method: "POST",
          body: formData,
        },
      );

      if(response.status === 413) {
        throw new Error("파일 용량이 서버 제한을 초과했습니다.");
      }

      const json = await response.json();

      if(!response.ok || !json.success) {
        throw new Error(getApiErrorMessage(json, "업로드 실패"));
      }

      const data = json.data;
      console.log("분석 결과:", data);
      setUploadStatus("success");
    } catch (error) {
      console.error("전송 실패:", error);
      setErrorMessage(error.mesage);
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
      <h2 className="text-[14.5px] font-bold mb-4">영상 업로드</h2>
      <p className="text-xs text-warn font-semibold mb-3">
        영상 분석은 현재 준비 중입니다. 업로드는 가능하지만 분석 결과가 제공되지는 않습니다.
      </p>
      <input
        type="file"
        accept=".mp4, .avi, .mov"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
      />

      <div
        onClick={() => fileInputRef.current.click()}
        className={`border-2 border-dashed rounded-[10px] p-8 flex flex-col items-center justify-center gap-2 cursor-pointer transition-colors ${fileError ? "border-danger bg-danger-bg" : "border-border hover:border-accent hover:bg-accent-bg"}`}
      >
        {previewUrl ? (
          <video
            src={previewUrl}
            controls
            onClick={(e) => e.stopPropagation()}
            className="max-w-full max-h-[220px] rounded-[8px]"
          />
        ) : (
          <>
            <span className="text-sm font-semibold text-ink">
              클릭하여 영상 선택
            </span>
            <span className="text-xs text-muted">
              최대 {MAX_VIDEO_SIZE_MB}MB까지 가능합니다.
            </span>
          </>
        )}
      </div>

      {selectedFile && (
        <p className="text-sm text-muted mt-2">
          선택된 파일: {selectedFile.name} (
          {(selectedFile.size / (1024 * 1024)).toFixed(1)}MB)
        </p>
      )}
      {fileError && (
        <p className="text-danger text-sm font-semibold mt-2">{fileError}</p>
      )}

      <button
        type="submit"
        disabled={uploading || !selectedFile}
        className="w-full mt-4 py-3.5 rounded-[10px] bg-accent text-white text-sm font-bold disabled:opacity-50 disabled:cursor-not-allowd"
      >
        {uploading ? "업로드 중..." : "제출"}
      </button>

      {uploadStatus === "success" && (
        <p className="text-safe text-sm font-semibold mt-2">업로드 성공!</p>
      )}
      {uploadStatus === "error" && (
        <p className="text-danger text-sm font-semibold mt-2">
          {errorMessage ?? "업로드 실패. 다시 시도해주세요."}
        </p>
      )}
    </form>
  );
}

export default VideoUploadForm;
