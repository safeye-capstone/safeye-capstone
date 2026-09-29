import { useEffect, useState } from "react";
import { useZones } from "./useZones";
import { matchZone } from "../utils/zone";

const toMB = (bytes) => bytes / (1024 * 1024);

export function useUploadForm({ maxSizeMB, upload, onSuccess }) {
  const { zones, loading: zonesLoading, error: zonesError } = useZones();

  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [fileError, setFileError] = useState(null);
  const [zoneId, setZoneId] = useState("");
  const [autoMatched, setAutoMatched] = useState(false);
  const [status, setStatus] = useState("idle");
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    if (!previewUrl) return;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const clearFile = () => {
    setFile(null);
    setPreviewUrl(null);
    setZoneId("");
    setAutoMatched(false);
  };

  const selectFile = (nextFile) => {
    setStatus("idle");
    setErrorMessage(null);

    if (!nextFile) {
      setFileError(null);
      clearFile();
      return;
    }

    const sizeMB = toMB(nextFile.size);
    if (sizeMB > maxSizeMB) {
      setFileError(
        `파일이 너무 큽니다 (${sizeMB.toFixed(1)}MB). ${maxSizeMB}MB 이하만 가능합니다.`,
      );
      clearFile();
      return;
    }

    setFileError(null);
    setFile(nextFile);
    setPreviewUrl(URL.createObjectURL(nextFile));

    const hit = matchZone(zones, nextFile.name);
    setZoneId(hit?.id ?? "");
    setAutoMatched(Boolean(hit));
  };

  const selectZone = (id) => {
    setZoneId(id);
    setAutoMatched(false);
  };

  const submit = async () => {
    if (!file) return;

    if (!zoneId) {
      setErrorMessage("구역을 선택해주세요.");
      setStatus("error");
      return;
    }

    setStatus("uploading");
    setErrorMessage(null);

    try {
      const data = await upload(file, zoneId);
      onSuccess?.(data);
      setStatus("success");
    } catch (err) {
      console.error("업로드 실패:", err);
      setErrorMessage(err.message);
      setStatus("error");
    }
  };

  return {
    zones,
    zonesLoading,
    zonesError,
    file,
    fileSizeMB: file ? toMB(file.size) : 0,
    previewUrl,
    fileError,
    zoneId,
    autoMatched,
    status,
    errorMessage,
    selectFile,
    selectZone,
    submit,
  };
}
