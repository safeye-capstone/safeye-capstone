# API metadata 전달 범위
이미지·영상 API의 기본 응답 5개 필드와 판정 규칙은 유지합니다. `ragMetadata`는 응답 직렬화 시 아래 항목만 전달합니다.

| 항목 | 전달 내용 |
| --- | --- |
| `vlm_decision_state` | 전체 판정 상태 |
| `hazards` | 위험 종류(`COLLAPSE` 포함), 최종 판정·이유, 대표·연관 위험 관계, 검토 순서 |
| `hazards[].collapse_verification` | 쓰러짐 검증 상태, 실제 분석 구간, 발생·판정 시각 |
| `review_queue`, `review_order_policy` | 한 분석 결과 안의 검토 확인 순서와 정렬 규칙 |
| `review_required_regulations` | 검토 후보의 참고 법령명·조문·제목 |
| `related_regulations` | 기존 응답에 `review_required_regulations`가 없을 때만 유지하는 참고 법령 대체 필드 |

참고 법령은 기존 프론트가 읽는 `metadata.law_name`, `metadata.article`, `metadata.article_title` 구조를 유지합니다. 법령 본문·검색 점수·검색어와 중복된 확정 법령 목록은 전달하지 않습니다. 확정 위험의 법령 표시는 기존 `violated_regulation`을 사용합니다.

`hazards` 배열에서 기각·보조 위험을 제거하거나 순서를 바꾸지 않으므로 `review_queue[].hazard_index`는 같은 배열 항목을 가리킵니다. 검토 후보가 있어도 확정 위험이 없으면 `is_danger=false`인 기존 정책을 유지합니다.

쓰러짐 검증을 실행한 `COLLAPSE` 항목에는 다음 요약을 전달합니다. 시각 단위는 초이며 원본 영상 시작을 기준으로 합니다.

| 필드 | 의미 |
| --- | --- |
| `status` | `FALL_SUSPECTED`(의심 동작 조건 충족), `INCONCLUSIVE`(조건 확인 불충분), `ERROR`(실행 실패), `NO_VALID_WINDOW`(유효한 후보 구간 없음) |
| `clips[].start`, `clips[].end` | 실제 분석한 구간. 조기 종료했다면 실제 종료 시각이며, 요청 구간이나 범위 밖 구간은 포함하지 않음 |
| `events[].suspected_start_seconds` | 쓰러짐 의심 동작 시작 시각 |
| `events[].decision_seconds` | 검증 조건을 충족한 판정 시각 |

실행 실패·이벤트 미확인 시 `clips` 또는 `events`는 빈 배열일 수 있습니다. 빈 배열을 정상 판정으로 해석하지 않고 `status`와 위험의 최종 판정을 함께 확인합니다. 검증을 실행하지 않은 후보에는 요약을 임의로 생성하지 않습니다. 추적 ID·모델 정보·프레임 수·오류 원문은 전달하지 않습니다.

프레임별 관찰·근거 수·일관성 점수, 확대 이미지 경로·좌표·개별 검사 결과, 쓰러짐 모델 처리 내역, 장면 맥락·언어 오류·원본 후보 등은 API 응답에서 제외합니다. 내부 분석 결과와 판정 로직은 유지하며, 응답으로 내보낼 때 허용한 항목만 추출합니다. 상세 기록을 별도 저장하거나 조회하는 API는 이번 변경에 추가하지 않습니다.

백엔드·프론트 코드는 수정하지 않습니다. 이미 DB에 저장된 과거 metadata는 그대로이며, 변경 후 생성하는 API 응답부터 축소됩니다.
