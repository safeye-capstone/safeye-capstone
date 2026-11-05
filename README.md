# SAFEye-capstone

산업 현장 위험 상황 맥락 인지를 위한 VLM 및 추론 엔진 (SAFEye 관제 시스템)

# 서빙 아키텍처 / 엔드포인트 안내

`vlm-workspace/app`에는 실행 진입점이 여러 개 있어 헷갈리기 쉽습니다. **실제로 전체 시스템(Frontend → Spring Backend → VLM)이 동작하는 경로는 아래 하나뿐입니다.**

```text
uvicorn app.api:app --host 0.0.0.0 --port 8100
```

이 진입점(`app/api.py`)이 노출하는 엔드포인트:

```text
POST /api/vlm/analyze         (이미지 분석)
POST /api/vlm/analyze/video   (영상 분석)
```

Spring Backend(`VlmApiService`)는 이제 `/api/vlm/analyze`를 호출하도록 되어 있습니다.

아래 두 파일은 같은 저장소 안에 있지만 **기본 실행 흐름과는 무관한 별도 진입점**이므로, 혼동하지 않도록 구분해 둡니다.

```text
app/mock_server.py     → POST /v1/analyze, /v1/analyze_internal
                          VLM/Ollama 없이 프론트/백엔드만 테스트할 때 쓰는 목(mock) 서버.
                          (Render 배포용, deploy/Dockerfile.mock 참고)

app/local/serve.py      → POST /v1/analyze_internal
app/backends/local.py     게이트웨이와 로컬 노드를 프로세스 2개로 분리하는 구조(develop 브랜치용).
                          현재 이 브랜치의 app/api.py는 이 구조를 쓰지 않고
                          app/local/ollama_client.py를 직접 호출합니다.
```

즉, **로컬/서버에서 실제로 띄워야 하는 건 `app.api:app` 하나뿐**이며, 나머지 두 진입점은 실행하지 않아도 됩니다.

# 실행 방법

## 0. 전체 시스템 실행 순서

전체 시스템을 실행할 때는 아래 순서로 실행합니다.

1. Docker Desktop 실행
2. PostgreSQL 실행
3. FastAPI VLM 서버 실행 (`app.api:app`)
4. Spring Backend 실행
5. Frontend 실행

Ollama는 개인 PC에 설치하지 않고, 아래 고정 원격 서버를 공용으로 사용합니다.

```text
http://166.104.223.60:11434
```

사용 포트:

```text
PostgreSQL      : 5434
Spring Backend  : 8080
FastAPI VLM     : 8100
Frontend        : 5173
Ollama (원격)   : 166.104.223.60:11434
```

## 1. VLM 작업폴더 이동

```powershell
cd vlm-workspace
```

## 2. 가상환경 생성 및 활성화

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Python 패키지 설치

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.local.txt
```

### 3-1. 11.06 작업본 추가 패키지 설치

사람 위치 기반 확대 검토와 쓰러짐 후보 검증까지 실행하려면 아래 설치를 추가합니다. 기존 `.venv`를 사용하는 팀원도 활성화 후 실행합니다. 로컬에서 확인한 환경은 Windows 64비트, Python 3.12.7이며, 아래는 CPU 실행 기준입니다.

```powershell
python -m pip install torch==2.9.1 torchvision==0.24.1 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.collapse.txt
python -m pip check
```

`requirements.collapse.txt`는 `requirements.local.txt`를 포함하므로 새 환경에서도 위 명령으로 기본 서버·RAG 의존성과 추가 의존성을 함께 설치할 수 있습니다.

| 추가 패키지 | 버전 | 용도 |
| --- | --- | --- |
| ultralytics | 8.4.202 | YOLO11s 사람 검출, ByteTrack 추적 |
| mediapipe | 1.2.2 | 후보 구간에서 사람별 자세·쓰러짐 조건 확인 |
| lap | 0.5.14 | ByteTrack의 검출·추적 연결 |
| torch / torchvision | 2.9.1+cpu / 0.24.1+cpu | 로컬에서 확인한 CPU 추론 조합 |

현재 사람 검출과 쓰러짐 검증 코드는 `device='cpu'`를 사용합니다. CUDA 패키지 설치만으로 GPU 실행으로 바뀌지는 않습니다. `torch`와 `torchvision`의 버전이 맞지 않으면 `torchvision::nms` 등의 오류가 발생할 수 있으므로 두 패키지를 함께 맞춥니다.

### 3-2. YOLO·MediaPipe 모델 준비

모델 파일은 Git에 포함되지 않으므로 각자 한 번 내려받아야 합니다. 아래 명령은 `vlm-workspace`에서 실행하며, 이미 있는 모델은 덮어쓰지 않습니다.

```powershell
New-Item -ItemType Directory -Force models | Out-Null
if (-not (Test-Path models/yolo11s.pt)) {
    curl.exe --fail --location "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s.pt" --output models/yolo11s.pt
}
if (-not (Test-Path models/pose_landmarker_lite.task)) {
    curl.exe --fail --location "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task" --output models/pose_landmarker_lite.task
}
```

필요한 파일은 `models/yolo11s.pt`와 `models/pose_landmarker_lite.task`입니다. YOLO는 자세 모델인 `yolo11s-pose.pt`가 아니라 사람 검출 모델을 사용합니다. 모델 안내: [Ultralytics YOLO11](https://docs.ultralytics.com/models/yolo11/), [MediaPipe Pose Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker).

패키지와 모델 로딩 확인:

```powershell
python -c "import torch, torchvision, mediapipe, lap; from ultralytics import YOLO; from pathlib import Path; YOLO('models/yolo11s.pt'); p=mediapipe.tasks.vision.PoseLandmarker.create_from_options(mediapipe.tasks.vision.PoseLandmarkerOptions(base_options=mediapipe.tasks.BaseOptions(model_asset_buffer=Path('models/pose_landmarker_lite.task').read_bytes()))); p.close(); print('패키지 및 모델 로딩 완료')"
```

모델이나 패키지가 없으면 확대 검토·쓰러짐 추가 검증이 실패하고 위험 후보가 검토 상태로 남을 수 있습니다. 서버의 `/health` 응답만으로 이 추가 기능의 준비 상태까지 확인할 수는 없습니다.

## 4. Ollama 연결 확인 (고정 원격 서버)

Ollama는 각자 PC에 설치하지 않습니다. 아래 고정 원격 주소를 공용으로 사용합니다.

```text
http://166.104.223.60:11434
```

`vlm-workspace/app/local/config.py`(로컬 노드용)와 `vlm-workspace/app/config.py`(호환용)의
`ollama_base_url` 기본값이 이미 위 주소로 설정되어 있으므로, 별도 설정 없이 바로 사용하면 됩니다.

현재 사용 모델:

```text
qwen2.5vl:7b-q4_K_M
```

접속 확인 (모델이 원격 서버에 이미 설치되어 있는지 확인):

```powershell
curl.exe http://166.104.223.60:11434/api/tags
```

응답 JSON의 `models` 목록에 `qwen2.5vl:7b-q4_K_M`이 보이면 정상입니다.
(개인 PC에서 `ollama pull`을 실행해도 원격 서버의 모델 목록에는 반영되지 않습니다.)

> 다른 Ollama 주소를 써야 하는 경우(예: 임시로 개인 기기 사용)에만
> `vlm-workspace/.env.local`에 아래처럼 덮어쓰면 됩니다. 평소에는 만들 필요 없습니다.
>
> ```env
> LN_OLLAMA_BASE_URL=http://127.0.0.1:11434
> ```

## 5. RAG Vector DB 구축

```powershell
python scripts/build_vector_db.py
```

ChromaDB는 Git에 포함하지 않으므로 각 개발 환경에서 직접 구축합니다.

## 6. PostgreSQL 실행

Docker Desktop을 먼저 실행합니다.

```powershell
cd backend
docker compose up -d
```

실행 상태 확인:

```powershell
docker compose ps
```

DB는 기본적으로 다음 포트를 사용합니다.

```text
localhost:5434
```

## 7. FastAPI 실행

`vlm-workspace` 폴더에서 실행합니다.

```powershell
uvicorn app.api:app --host 0.0.0.0 --port 8100 --reload
```

정상 실행 후 Swagger 접속:

```text
http://localhost:8100/docs
```

### 이미지 분석

```text
POST /api/vlm/analyze
```

→ Try it out  
→ image 파일 선택  
→ Execute

### 영상 분석

```text
POST /api/vlm/analyze/video
```

→ Try it out  
→ video 파일 선택  
→ Execute

## 8. Spring Backend 실행

Java 17이 필요합니다.

Java 버전 확인:

```powershell
java -version
```

`backend` 폴더에서:

```powershell
.\gradlew bootRun
```

정상 실행 시:

```text
Started BackendApplication
```

이 출력됩니다.

Backend 주소:

```text
http://localhost:8080
```

현재 VLM 서버 설정 (`backend/src/main/resources/application.yaml`):

```yaml
vlm:
  server:
    url: http://localhost:8100
    timeout: 30 # VLM 통신 타임아웃 (초)
```

`vlm.server.url`은 FastAPI VLM 서버(`app.api:app`)의 주소이며, Ollama 주소가 아닙니다.
Spring Backend → FastAPI VLM → Ollama(원격) 순으로 호출되므로, Spring이 Ollama 주소를 직접 알 필요는 없습니다.

## 9. Frontend 실행

`frontend/.env.local` 파일에 다음 내용을 설정합니다.

```env
VITE_API_URL=http://localhost:8080
```

Frontend 실행:

```powershell
cd frontend
npm install
npm run dev
```

접속:

```text
http://localhost:5173
```

## 10. Work Zone 확인

현재 DB에 생성된 작업 구역은 다음 API로 확인할 수 있습니다.

```powershell
curl.exe http://localhost:8080/api/zones
```

DB를 새로 생성하면 Zone UUID가 변경될 수 있으므로

```text
frontend/src/constants/config.js
```

의 `DEV_ZONE_ID`와 실제 DB의 Zone ID가 일치하는지 확인합니다.

# VLM 영상 파이프라인 단독 실행

Frontend / Backend를 거치지 않고 VLM 영상 분석 Pipeline만 테스트할 경우:

```powershell
cd vlm-workspace
python -m app.pipeline
```

> `python -m app.pipeline`은 전체 SAFEye 시스템 실행 명령이 아니라  
> VLM 영상 Pipeline 단독 테스트용 명령입니다.

# 영상자료 위치

```text
vlm-workspace\data\videos\test.mp4
```

영상 분석 결과는 다음 위치에 저장됩니다.

```text
vlm-workspace\data\results\test_analysis.json
```

## 11.06 작업본 테스트 영상 실행 안내

`data/videos/`의 MP4 7개는 이전 커밋에 포함돼 있습니다: `1_2collapse.mp4`, `collapse.mp4`, `collapse_back.mp4`, `demo2.mp4`, `squat.mp4`, `test2.mp4`, `test3.mp4`.

위의 `python -m app.pipeline` 예시는 `data/videos/test.mp4`를 고정으로 읽습니다. 저장소에 포함된 영상을 바로 시험하려면 FastAPI의 `/docs`에서 `POST /api/vlm/analyze/video`에 MP4를 선택하거나, `vlm-workspace`에서 아래처럼 파일명을 지정합니다. 실제 VLM·법령 검색 시험에는 원격 Ollama 연결과 앞서 안내한 RAG Vector DB 구축이 필요합니다.

```powershell
python -c "from app.pipeline import analyze_video, save_result; print(save_result(analyze_video('1_2collapse.mp4', verbose=True)))"
```

쓰러짐 연동만 빠르게 확인하는 스모크 테스트:

```powershell
New-Item -ItemType Directory -Force pose_results | Out-Null
python scripts/smoke_collapse_pipeline.py
```

스모크 테스트는 실제 영상을 디코딩하고 YOLO·MediaPipe를 실행하지만, VLM 후보 생성과 법령 검색은 모의 응답을 사용합니다. 따라서 실제 VLM·RAG 동작 확인은 위의 영상 API 또는 `analyze_video` 실행으로 진행합니다. 스모크 테스트 결과는 `pose_results/collapse_pipeline_smoke.json`에 저장되며 Git 업로드 대상에서는 제외됩니다.

# 영상 분석 흐름

```text
영상
→ 프레임 추출
→ 프레임별 VLM 분석
→ Temporal Aggregation
→ Confidence Recalibration
→ Semantic Prompt Reverification
→ Final Decision
→ Hazard Consolidation
→ RAG 법령 검색
→ 최종 응답
```

# 프로젝트 구조

```text
safEYE-capstone/

├─ backend/                         # Spring Boot
├─ frontend/                        # React / Vite Frontend
│
└─ vlm-workspace/
   ├─ app/
   │  ├─ local/                     # VLM 호출 및 이미지/영상 처리
   │  ├─ rag/                       # 위험 통합, 신뢰도 평가 및 RAG
   │  │  ├─ aggregator.py
   │  │  ├─ confidence_calibrator.py
   │  │  ├─ reverification.py
   │  │  ├─ final_decision.py
   │  │  ├─ hazard_consolidator.py
   │  │  ├─ query_builder.py
   │  │  └─ regulation_retriever.py
   │  │
   │  ├─ api.py                     # FastAPI
   │  ├─ api_schemas.py             # API Schema
   │  ├─ image_pipeline.py          # 이미지 분석 Pipeline
   │  ├─ video_pipeline.py          # 영상 API 연결
   │  ├─ pipeline.py                # 영상 전체 분석 Pipeline
   │  ├─ response_builder.py        # 최종 응답 생성
   │  └─ severity.py                # 위험도 산정
   │
   ├─ data/
   │  ├─ raw_laws/                  # 법령 원문
   │  ├─ processed/                 # HWPX 추출 TXT
   │  ├─ parsed/
   │  │  └─ regulations.jsonl       # 파싱된 RAG Dataset
   │  ├─ frames/                    # 영상 추출 프레임
   │  ├─ videos/                    # 테스트 영상
   │  ├─ results/                   # 분석 결과
   │  └─ rag/
   │     └─ chroma_db/              # Local Vector DB
   │
   ├─ prompts/
   │  └─ video_analysis.txt
   │
   ├─ scripts/
   │  ├─ extract_hwpx.py
   │  ├─ parse_articles.py
   │  └─ build_vector_db.py
   │
   └─ requirements.local.txt
```

# API 응답 형식

FastAPI와 Spring Backend 사이의 AI 분석 응답은 다음 5개 필드를 사용합니다.

```json
{
  "is_danger": true,
  "severity": "CRITICAL",
  "vlm_description": "고소작업자의 안전고리 미체결이 확인되었습니다.",
  "violated_regulation": "산업안전보건기준에 관한 규칙 제44조",
  "action_guide": "즉시 고소작업을 중지하고 안전고리를 적절한 부착설비에 체결하세요."
}
```

Severity:

```text
CRITICAL
WARNING
INFO
```

# 주요 API

Frontend → Spring Backend:

```text
POST /api/upload/file
```

Multipart:

```text
file
zoneId
```

Spring Backend는 업로드된 파일 형식에 따라 FastAPI를 자동으로 분기합니다.

```text
이미지
→ POST /api/vlm/analyze

영상
→ POST /api/vlm/analyze/video
```

> 영상 분기는 현재 `VlmApiService`에 아직 구현되어 있지 않고 이미지 분석(`analyzeFile`)만
> `/api/vlm/analyze`를 호출합니다. 영상 업로드 시 Spring이 FastAPI의 `/api/vlm/analyze/video`를
> 호출하도록 연결하는 작업은 별도로 필요합니다.

# Troubleshooting

## JAVA_HOME is not set

Java 17 설치 여부를 확인합니다.

```powershell
java -version
```

Java가 없다면:

```powershell
winget install EclipseAdoptium.Temurin.17.JDK
```

설치 후 VS Code를 재시작합니다.

## Connection to localhost:5434 refused

PostgreSQL이 실행되지 않은 상태입니다.

```powershell
cd backend
docker compose up -d
```

## Docker Desktop - WSL not installed

관리자 PowerShell에서:

```powershell
wsl --install
```

설치 후 Windows를 재부팅합니다.

## ModuleNotFoundError: No module named 'app'

FastAPI를 `backend` 폴더가 아니라 반드시 `vlm-workspace`에서 실행합니다.

```powershell
cd vlm-workspace
uvicorn app.api:app --host 0.0.0.0 --port 8100 --reload
```

## ollama unreachable: http://166.104.223.60:11434

VLM 서버(FastAPI) 로그에 위 메시지가 뜨면 원격 Ollama 서버에 연결하지 못한 상태입니다.

```powershell
curl.exe http://166.104.223.60:11434/api/tags
```

위 명령이 실패한다면:

- 원격 서버(`166.104.223.60`)가 켜져 있는지, Ollama 프로세스가 살아있는지 확인
- 같은 네트워크/VPN에 연결되어 있는지 확인 (외부망에서는 접근이 막혀 있을 수 있음)
- 방화벽에서 `11434` 포트가 막혀있지 않은지 확인

개인 기기에서 임시로 로컬 Ollama를 써야 한다면 위 "Ollama 연결 확인" 절의
`LN_OLLAMA_BASE_URL` 오버라이드를 사용하세요.

## ZONE-001

DB에 존재하지 않는 Zone ID를 사용한 경우입니다.

현재 Zone ID 확인:

```powershell
curl.exe http://localhost:8080/api/zones
```
