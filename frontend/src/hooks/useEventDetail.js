import { useLocation, useOutletContext } from "react-router-dom";

export function getEventDetailPath(id) {
  return `/history/${encodeURIComponent(id)}`;
}

// 경보 상세 데이터를 어디서 가져올지 정하는 곳
// 단건 조회 API(GET /api/events/{id})가 생기면 여기 바꾸기
export function useEventDetail(id) {
  const location = useLocation();
  const { alerts = [] } = useOutletContext() ?? {};

  const fromList = alerts.find((a) => String(a.id) === id);
  const fromState = location.state?.event;
  const matchedState =
    fromState && String(fromState.id) === id ? fromState : null;

  return { event: fromList ?? matchedState ?? null };
}
