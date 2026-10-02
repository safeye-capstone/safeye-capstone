import { useState } from "react";
import PageHeader from "../components/layout/PageHeader";
import VideoUploadForm from "../components/upload/VideoUploadForm";
import ResultList from "../components/upload/ResultList";
import { withClientMeta } from "../utils/result";

function AnalyzeVideoPage() {
  const [results, setResults] = useState([]);

  const handleResult = (dto) => {
    setResults((prev) => [withClientMeta(dto), ...prev]);
  };

  return (
    <>
      <PageHeader />
      <div className="flex flex-col lg:flex-row gap-6 items-start">
        <VideoUploadForm onResult={handleResult} />
        <div className="flex-1 min-w-0 w-full">
          <ResultList
            results={results}
            emptyMessage="영상을 올리면 분석 결과가 여기에 표시됩니다."
          />
        </div>
      </div>
    </>
  );
}

export default AnalyzeVideoPage;
