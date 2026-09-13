import {
  useRef,
  useState,
} from "react";

import {
  DEV_ZONE_ID,
  MAX_VIDEO_SIZE_MB,
  UPLOAD_VIDEO_ENDPOINT,
} from "../constants/config";

import {
  getApiErrorMessage,
} from "../utils/apiError";


function VideoUploadForm({
  onAnalysisComplete,
}) {

  const [selectedFile, setSelectedFile] =
    useState(null);

  const [previewUrl, setPreviewUrl] =
    useState(null);

  const [uploading, setUploading] =
    useState(false);

  const [uploadStatus, setUploadStatus] =
    useState(null);

  const [errorMessage, setErrorMessage] =
    useState(null);

  const [fileError, setFileError] =
    useState(null);


  const fileInputRef = useRef(null);


  const handleFileChange = (e) => {

    const file = e.target.files[0];

    setUploadStatus(null);
    setErrorMessage(null);

    if (!file) {

      setSelectedFile(null);
      setPreviewUrl(null);

      return;
    }


    const sizeMB =
      file.size / (1024 * 1024);


    if (
      sizeMB
      > MAX_VIDEO_SIZE_MB
    ) {

      setFileError(
        `파일이 너무 큽니다 (${sizeMB.toFixed(1)}MB). `
        + `${MAX_VIDEO_SIZE_MB}MB 이하만 가능합니다.`,
      );

      setSelectedFile(null);
      setPreviewUrl(null);

      return;
    }


    setFileError(null);

    setSelectedFile(
      file
    );

    setPreviewUrl(
      URL.createObjectURL(file)
    );
  };


  const handleSubmit = async (e) => {

    e.preventDefault();

    if (!selectedFile) {
      return;
    }


    const formData =
      new FormData();


    formData.append(
      "file",
      selectedFile
    );

    formData.append(
      "zoneId",
      DEV_ZONE_ID
    );


    setUploading(true);
    setUploadStatus(null);
    setErrorMessage(null);


    try {

      const response =
        await fetch(
          `${import.meta.env.VITE_API_URL}${UPLOAD_VIDEO_ENDPOINT}`,
          {
            method: "POST",
            body: formData,
          },
        );


      if (
        response.status === 413
      ) {

        throw new Error(
          "파일 용량이 서버 제한을 초과했습니다."
        );
      }


      /*
       * response.json()을 바로 호출하지 않고
       * text로 먼저 받는다.
       *
       * 서버가 빈 응답을 반환할 경우
       * Unexpected end of JSON input이 발생하는 것을 방지한다.
       */

      const responseText =
        await response.text();


      if (!responseText) {

        throw new Error(
          "서버에서 응답을 받지 못했습니다."
        );
      }


      let json;


      try {

        json = JSON.parse(
          responseText
        );

      } catch (parseError) {

        console.error(
          "JSON 파싱 실패:",
          responseText,
          parseError
        );

        throw new Error(
          "서버 응답 형식이 올바르지 않습니다."
        );
      }


      if (
        !response.ok
        || !json.success
      ) {

        throw new Error(
          getApiErrorMessage(
            json,
            "영상 분석 실패"
          )
        );
      }


      const data =
        json.data;


      console.log(
        "분석 결과:",
        data
      );


      if (
        onAnalysisComplete
      ) {

        onAnalysisComplete(
          data
        );
      }


      setUploadStatus(
        "success"
      );


    } catch (error) {

      console.error(
        "전송 실패:",
        error
      );

      setErrorMessage(
        error.message
      );

      setUploadStatus(
        "error"
      );

    } finally {

      setUploading(
        false
      );
    }
  };


  return (
    <form
      onSubmit={handleSubmit}
      className="
        bg-white
        border
        border-border
        rounded-[14px]
        p-6
        w-full
        max-w-[420px]
      "
    >

      <h2
        className="
          text-[14.5px]
          font-bold
          mb-4
        "
      >
        영상 업로드
      </h2>


      <p
        className="
          text-xs
          text-muted
          font-semibold
          mb-3
        "
      >
        영상을 업로드하면 AI가 위험 요소와
        관련 법령을 분석합니다.
      </p>


      <input
        type="file"
        accept=".mp4,.avi,.mov"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
      />


      <div
        onClick={
          () =>
            fileInputRef.current?.click()
        }
        className={`
          border-2
          border-dashed
          rounded-[10px]
          p-8
          flex
          flex-col
          items-center
          justify-center
          gap-2
          cursor-pointer
          transition-colors

          ${
            fileError
              ? "border-danger bg-danger-bg"
              : "border-border hover:border-accent hover:bg-accent-bg"
          }
        `}
      >

        {previewUrl ? (

          <video
            src={previewUrl}
            controls
            onClick={
              (e) =>
                e.stopPropagation()
            }
            className="
              max-w-full
              max-h-[220px]
              rounded-[8px]
            "
          />

        ) : (

          <>

            <span
              className="
                text-sm
                font-semibold
                text-ink
              "
            >
              클릭하여 영상 선택
            </span>

            <span
              className="
                text-xs
                text-muted
              "
            >
              최대 {MAX_VIDEO_SIZE_MB}MB까지 가능합니다.
            </span>

          </>

        )}

      </div>


      {selectedFile && (

        <p
          className="
            text-sm
            text-muted
            mt-2
          "
        >

          선택된 파일:{" "}
          {selectedFile.name}{" "}
          (
          {
            (
              selectedFile.size
              / (1024 * 1024)
            ).toFixed(1)
          }
          MB)

        </p>

      )}


      {fileError && (

        <p
          className="
            text-danger
            text-sm
            font-semibold
            mt-2
          "
        >
          {fileError}
        </p>

      )}


      <button
        type="submit"
        disabled={
          uploading
          || !selectedFile
        }
        className="
          w-full
          mt-4
          py-3.5
          rounded-[10px]
          bg-accent
          text-white
          text-sm
          font-bold
          disabled:opacity-50
          disabled:cursor-not-allowed
        "
      >

        {
          uploading
            ? "분석 중..."
            : "제출"
        }

      </button>


      {uploadStatus === "success" && (

        <p
          className="
            text-safe
            text-sm
            font-semibold
            mt-2
          "
        >
          영상 분석 완료!
        </p>

      )}


      {uploadStatus === "error" && (

        <p
          className="
            text-danger
            text-sm
            font-semibold
            mt-2
          "
        >

          {
            errorMessage
            ?? "영상 분석에 실패했습니다."
          }

        </p>

      )}

    </form>
  );
}


export default VideoUploadForm;