import { api } from "./client";

function toFormData(file, zoneId) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("zoneId", zoneId);
  return formData;
}

export const uploadImage = (file, zoneId) =>
  api.post("/api/upload/file", toFormData(file, zoneId));

export const uploadVideo = (file, zoneId) =>
  api.post("/api/upload/file", toFormData(file, zoneId));
