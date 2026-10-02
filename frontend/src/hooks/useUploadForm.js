import { useEffect, useState } from "react";
import { useZones } from "./useZones";
import { matchZone } from "../utils/zone";

const toMB = (bytes) => bytes / (1024 * 1024);

const parseExts = (accept = "") =>
  accept
    .split(",")
    .map((ext) => ext.trim().toLowerCase())
    .filter(Boolean);

const getExt = (filename) => {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot).toLowerCase();
};

export function useUploadForm({ maxSizeMB, accept, upload, onSuccess }) {
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

    const allowedExts = parseExts(accept);
    if (
      allowedExts.length > 0 &&
      !allowedExts.includes(getExt(nextFile.name))
    ) {
      setFileError(
        `지원하지 않는 파일 형식입니다. ${allowedExts
          .map((ext) => ext.slice(1).toUpperCase())
          .join(", ")} 파일만 올릴 수 있습니다.`,
      );
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

    let data;
    try {
      data = await upload(file, zoneId);
    } catch (err) {
      console.error("업로드 실패:", err);
      setErrorMessage(err.message);
      setStatus("error");
      return;
    }

    setStatus("success");
    try {
      onSuccess?.(data);
    } catch (err) {
      console.error("분석 결과 처리 중 오류:", err);
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
