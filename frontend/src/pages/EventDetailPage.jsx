import { Link, useParams } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { getDecisionView, isReviewRequired } from "../constants/decisionState";
import { useEventDetail } from "../hooks/useEventDetail";

function formatDateTime(value) {
  if (!value) return "-";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "-" : date.toLocaleString("ko-KR");
}

function Section({ title, children }) {
  return (
    <section className="rounded-[12px] border border-border bg-white p-5">
      <h2 className="text-sm font-bold text-muted mb-2">{title}</h2>
      <div className="text-ink leading-relaxed whitespace-pre-line">
        {children}
      </div>
    </section>
  );
}

function EventDetailPage() {
  const { id } = useParams();
  const { event } = useEventDetail(id);

  if (!event) {
    return (
      <div className="max-w-3xl mx-auto py-16 text-center">
        <p className="text-ink font-bold mb-2">경보를 찾을 수 없습니다.</p>
        <p className="text-sm text-muted mb-6">
          새로고침하면 실시간 경보 정보가 사라집니다. 이력에서 다시 열어 주세요.
        </p>
        <Link
          to="/history"
          className="text-sm font-semibold text-ink underline"
        >
          이력으로 가기
        </Link>
      </div>
    );
  }

  const { label, tone } = getDecisionView(event);
  const isVideo = event.fileUrl?.includes("/videos/");

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <Link
        to="/history"
        className="inline-flex items-center gap-1 text-sm text-muted hover:text-ink w-fit"
      >
        <ArrowLeft size={16} />
        이력
      </Link>

      <header className={`rounded-[12px] border p-5 ${tone.box}`}>
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-lg font-bold ${tone.text}`}>{label}</span>
          <span className="text-sm text-muted">{event.zoneName}</span>
        </div>
        <p className="text-sm text-muted">{formatDateTime(event.detectedAt)}</p>
        {isReviewRequired(event) && (
          <p className={`mt-2 text-sm font-semibold ${tone.text}`}>
            AI가 확신하지 못한 경보입니다. 현장에서 직접 확인해 주세요.
          </p>
        )}
      </header>

      {event.fileUrl &&
        (isVideo ? (
          <video
            src={event.fileUrl}
            controls
            className="w-full rounded-[12px] border border-border bg-black"
          />
        ) : (
          <img
            src={event.fileUrl}
            alt={`${event.zoneName} 현장 이미지`}
            className="w-full rounded-[12px] border border-border object-contain bg-white"
          />
        ))}

      <Section title="AI 분석">{event.vlmDescription || "-"}</Section>
      {event.violatedRegulation && (
        <Section title="위반 규정">{event.violatedRegulation}</Section>
      )}
      {event.actionGuide && (
        <Section title="조치 방법">{event.actionGuide}</Section>
      )}
    </div>
  );
}

export default EventDetailPage;
