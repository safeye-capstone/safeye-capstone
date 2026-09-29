// components/upload/PhotoUploadForm.jsx
import { useOutletContext } from "react-router-dom";
import FileUploadForm from "./FileUploadForm";
import { uploadImage } from "../../api/upload";
import { MAX_IMAGE_SIZE_MB } from "../../constants/config";

function PhotoUploadForm({ onResult }) {
  const { pushAlert } = useOutletContext() ?? {};

  const handleSuccess = (data) => {
    onResult?.(data);

    if (data.severity === "CRITICAL" || data.severity === "WARNING") {
      pushAlert?.(data);
    }
  };

  return (
    <FileUploadForm
      title="이미지 업로드"
      accept=".jpg,.jpeg,.png,.webp"
      maxSizeMB={MAX_IMAGE_SIZE_MB}
      hint={`JPG, PNG, WEBP • 최대 ${MAX_IMAGE_SIZE_MB}MB`}
      upload={uploadImage}
      onSuccess={handleSuccess}
      renderPreview={(url) => (
        <img
          src={url}
          alt="미리보기"
          className="max-w-full max-h-[220px] block rounded-[8px]"
        />
      )}
    />
  );
}

export default PhotoUploadForm;
