import {
  LayoutDashboard,
  MonitorPlay,
  Camera,
  Clapperboard,
  History,
  ShieldCheck,
  FileBarChart2,
  Settings2,
} from "lucide-react";

export const MENU_GROUPS = [
  {
    label: "main",
    items: [
      {
        id: "dashboard",
        label: "대시보드",
        path: "/",
        icon: LayoutDashboard,
        desc: "현장 전체의 위험 현황과 실시간 경보를 한눈에 확인합니다.",
        ready: true,
      },
      {
        id: "monitor",
        label: "실시간 감시",
        path: "/monitor",
        icon: MonitorPlay,
        desc: "엣지 카메라 스트림을 구역별로 감시하고 위험을 즉시 경보합니다.",
        ready: false,
        preview: [
          "구역별 라이브 스트림 그리드",
          "위험 감지 시 화면 오버레이 표시",
          "경보 발생 타임라인",
        ],
      },
      {
        id: "photo",
        label: "사진 분석",
        path: "/analyze/image",
        icon: Camera,
        desc: "현장 사진을 업로드해 안전장비 착용 상태와 위험 요소를 분석합니다.",
        ready: true,
      },
      {
        id: "video",
        label: "영상 분석",
        path: "/analyze/video",
        icon: Clapperboard,
        desc: "현장 영상을 업로드해 프레임 단위로 위험 상황을 분석합니다.",
        ready: true,
      },
      {
        id: "history",
        label: "분석 이력",
        path: "/history",
        icon: History,
        desc: "지금까지 분석한 결과를 조회하고 상세 내용을 확인합니다.",
        ready: false,
        preview: [
          "구역/기간/위험등급 필터",
          "이력 테이블 및 페이지네이션",
          "개별 이벤트 상세 보기",
        ],
      },
      {
        id: "compliance",
        label: "중대재해법 증명",
        path: "/compliance",
        icon: ShieldCheck,
        desc: "중대재해처벌법 9대 의무(시행령 제 4조) 이행 내역을 점검하고 증빙합니다.",
        ready: false,
        preview: [
          "9대 의무별 이행 현황",
          "의무별 증빙 자료 연결",
          "점검 결과 내보내기",
        ],
      },
      {
        id: "report",
        label: "자동 리포트",
        path: "/report",
        icon: FileBarChart2,
        desc: "기간별 안전 통계를 자동으로 집계해 리포트로 생성합니다.",
        ready: false,
        preview: [
          "주간/월간 리포트 자동 생성",
          "위험 유형별 추이 그래프",
          "PDF 내보내기",
        ],
      },
    ],
  },
  {
    id: "system",
    items: [
      {
        id: "settings",
        label: "설정",
        path: "/settings",
        icon: Settings2,
        desc: "감시 구역, 알림 방식, 분석 옵션을 설정합니다.",
        ready: false,
        preview: [
          "감시 구역 등록 및 관리",
          "경보 알림 채널 설정",
          "분석 민감도 조정",
        ],
      },
    ],
  },
];

export const MENU_ITEMS = MENU_GROUPS.flatMap((g) => g.items);

export function getPageMeta(pathname) {
  const exact = MENU_ITEMS.find((i) => i.path === pathname);
  if (exact) return exact;

  const matched = MENU_ITEMS.filter(
    (i) => i.path !== "/" && pathname.startsWith(i.path + "/"),
  ).sort((a, b) => b.path.length - a.path.length)[0];

  return matched ?? { id: "unknown", label: "SAFEye", desc: "", ready: true };
}
