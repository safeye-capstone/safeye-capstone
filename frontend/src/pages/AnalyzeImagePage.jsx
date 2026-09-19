import { useState } from "react";
import PhotoUploadForm from "../components/PhotoUploadForm";
import ResultList from "../components/ResultList";
import { MOCK_RESULTS } from "../fixtures/mockResults";
import PageHeader from "../components/layout/PageHeader";

const useMock = new URLSearchParams(window.location.search).has("mock");

const withClientMeta = (dto) => ({
  ...dto,
  clientId: crypto.randomUUID(),
  receivedAt: new Date().toISOString(),
});

function AnalyzeImagePage() {
  const [results, setResults] = useState(() =>
    useMock ? MOCK_RESULTS.map(withClientMeta) : [],
  );

  const handleResult = (dto) => {
    setResults((prev) => [withClientMeta(dto), ...prev]);
  };

  return (
    <div className="flex flex-col lg:flex-row gap-6 items-start">
      <PageHeader />
      <PhotoUploadForm onResult={handleResult} />
      <div className="flex-1 min-w-0 w-full">
        <ResultList results={results} />
      </div>
    </div>
  );
}

export default AnalyzeImagePage;
