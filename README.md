# SAFEye-capstone

산업 현장 위험 상황 맥락 인지를 위한 VLM 및 추론 엔진 (SAFEye 관제 시스템)


# 실행 방법

## 0. 전체 시스템 실행 순서

전체 시스템을 실행할 때는 아래 순서로 실행합니다.

1. Docker Desktop 실행
2. PostgreSQL 실행
3. FastAPI VLM 서버 실행
4. Spring Backend 실행
5. Frontend 실행

사용 포트:

```text
PostgreSQL      : 5434
Spring Backend  : 8080
FastAPI VLM     : 8100
Frontend        : 5173
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


## 4. Ollama 모델 설치

현재 사용 모델:

```text
qwen2.5vl:7b-q4_K_M
```

설치:

```powershell
ollama pull qwen2.5vl:7b-q4_K_M
```

설치 확인:

```powershell
ollama list
```


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

현재 VLM 서버 설정:

```yaml
vlm:
  server:
    url: http://localhost:8100
    timeout: 300
```


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


## ZONE-001

DB에 존재하지 않는 Zone ID를 사용한 경우입니다.

현재 Zone ID 확인:

```powershell
curl.exe http://localhost:8080/api/zones
```