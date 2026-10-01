import { useOutletContext } from "react-router-dom";
import FileUploadForm from "./FileUploadForm";
import { uploadVideo } from "../../api/upload";
import { MAX_VIDEO_SIZE_MB } from "../../constants/config";
import { isAlertSeverity } from "../../constants/severity";

function VideoUploadForm({ onResult }) {
  const { pushAlert } = useOutletContext() ?? {};

  const handleSuccess = (data) => {
    onResult?.(data);

    if (isAlertSeverity(data?.severity)) {
      pushAlert?.(data);
    }
  };

  return (
    <FileUploadForm
      title="영상 업로드"
      accept=".mp4, .avi, .mov"
      maxSizeMB={MAX_VIDEO_SIZE_MB}
      hint={`MP4, AVI, MOV • 최대 ${MAX_VIDEO_SIZE_MB}MB`}
      upload={uploadVideo}
      pendingHint="AI가 영상을 분석하고 있습니다. (영상 길이에 따라 더 오래 걸릴 수 있습니다."
      onSuccess={handleSuccess}
      renderPreview={(url) => (
        <video
          src={url}
          controls
          onClick={(e) => e.stopPropagation()}
          className="max-w-full max-h-[220px] rounded-[8px]"
        />
      )}
    />
  );
}

export default VideoUploadForm;
