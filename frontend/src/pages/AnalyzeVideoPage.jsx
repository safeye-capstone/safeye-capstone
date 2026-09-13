import { useState } from "react";

import VideoUploadForm from "../components/VideoUploadForm";
import ResultList from "../components/ResultList";


function AnalyzeVideoPage() {
  const [analysisResult, setAnalysisResult] = useState(null);

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">

      <VideoUploadForm
        onAnalysisComplete={setAnalysisResult}
      />

      {analysisResult && (
        <div className="w-full max-w-[620px]">
          <ResultList
            results={[analysisResult]}
          />
        </div>
      )}

    </div>
  );
}


export default AnalyzeVideoPage;