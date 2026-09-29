import FileUploadForm from "./FileUploadForm";
import { uploadVideo } from "../../api/upload";
import { MAX_VIDEO_SIZE_MB } from "../../constants/config";

function VideoUploadForm() {
  return (
    <FileUploadForm
      title="영상 업로드"
      notice="영상 분석은 현재 준비 중입니다. 업로드는 가능하지만 분석 결과가 제공되지 않습니다."
      accept=".mp4, .avi, .mov"
      maxSizeMB={MAX_VIDEO_SIZE_MB}
      hint={`MP4, AVI, MOV / 최대 ${MAX_VIDEO_SIZE_MB}MB`}
      upload={uploadVideo}
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
