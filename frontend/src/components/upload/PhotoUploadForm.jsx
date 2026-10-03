// components/upload/PhotoUploadForm.jsx
import { useOutletContext } from "react-router-dom";
import FileUploadForm from "./FileUploadForm";
import { uploadImage } from "../../api/upload";
import { MAX_IMAGE_SIZE_MB } from "../../constants/config";

function PhotoUploadForm({ onResult }) {
  const { pushAlert } = useOutletContext() ?? {};

  const handleSuccess = (data) => {
    if (!data) return;
    onResult?.(data);

    pushAlert?.(data);
  };

  return (
    <FileUploadForm
      title="이미지 업로드"
      accept=".jpg,.jpeg,.png,.webp"
      maxSizeMB={MAX_IMAGE_SIZE_MB}
      hint={`JPG, PNG, WEBP • 최대 ${MAX_IMAGE_SIZE_MB}MB`}
      upload={uploadImage}
      pendingHint="AI가 사진을 분석하고 있습니다. (약 10초 소요)"
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
