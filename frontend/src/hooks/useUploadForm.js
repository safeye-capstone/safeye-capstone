import { useEffect, useState, useRef } from "react";
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
  const [elapsedSec, setElapsedSec] = useState(0);
  const submittingRef = useRef(false);
  const abortRef = useRef(null);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    if (status !== "uploading") return;

    const startedAt = Date.now();
    const timer = setInterval(() => {
      setElapsedSec(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    const warn = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);

    return () => {
      clearInterval(timer);
      window.removeEventListener("beforeunload", warn);
    };
  }, [status]);

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
    if (submittingRef.current) return;
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
    if (submittingRef.current) return;
    setZoneId(id);
    setAutoMatched(false);
  };

  const submit = async () => {
    if (!file || submittingRef.current) return;

    if (!zoneId) {
      setErrorMessage("구역을 선택해주세요.");
      setStatus("error");
      return;
    }

    submittingRef.current = true;
    setElapsedSec(0);
    setStatus("uploading");
    setErrorMessage(null);

    const controller = new AbortController();
    abortRef.current = controller;

    let data;
    try {
      data = await upload(file, zoneId, { signal: controller.signal });
    } catch (err) {
      // 화면을 벗어나 취소된 요청은 실패로 표시하지 않는다
      if (controller.signal.aborted) return;

      console.error("업로드 실패:", err);
      setErrorMessage(err.message);
      setStatus("error");
      return;
    } finally {
      submittingRef.current = false;
      if (abortRef.current === controller) abortRef.current = null;
    }

    // 목 응답처럼 취소가 전달되지 않는 경우에도, 벗어난 뒤에 온 결과는 버린다
    if (controller.signal.aborted) return;

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
    elapsedSec,
    errorMessage,
    selectFile,
    selectZone,
    submit,
  };
}
