import asyncio

from pathlib import Path
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    HTTPException,
    UploadFile,
)

from starlette.concurrency import (
    run_in_threadpool,
)

from app.api_schemas import (
    AIAnalysisResponse,
)

from app.image_pipeline import (
    analyze_image_for_api,
)

from app.video_pipeline import (
    analyze_video_for_api,
)

from app.local.config import (
    VIDEO_DIR,
)


app = FastAPI(
    title="safEYE AI API",
    version="1.1.0",
)


# ============================================================
# 기본 경로
# ============================================================

BASE_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)


IMAGE_UPLOAD_DIR = (
    BASE_DIR
    / "data"
    / "uploads"
)

IMAGE_UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


VIDEO_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# 지원 파일 형식
# ============================================================

ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}


ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/x-msvideo",
    "video/quicktime",
}


IMAGE_SUFFIX_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


VIDEO_SUFFIX_MAP = {
    "video/mp4": ".mp4",
    "video/x-msvideo": ".avi",
    "video/quicktime": ".mov",
}


# ============================================================
# 영상 Pipeline 동시 실행 방지
#
# 현재 pipeline.py가 공용 FRAME_DIR을 사용하므로
# 영상 요청 두 개가 동시에 실행되면 프레임이 섞일 수 있다.
# 프로토타입에서는 한 번에 하나씩 분석한다.
# ============================================================

VIDEO_ANALYSIS_LOCK = asyncio.Lock()


# ============================================================
# Health Check
# ============================================================

@app.get(
    "/health"
)
async def health():

    return {
        "status": "ok"
    }


# ============================================================
# 이미지 분석
# ============================================================

@app.post(
    "/api/vlm/analyze",
    response_model=AIAnalysisResponse,
)
async def analyze_image_endpoint(
    image: UploadFile = File(...),
):

    if (
        image.content_type
        not in ALLOWED_IMAGE_CONTENT_TYPES
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "지원하지 않는 이미지 형식입니다. "
                "JPEG, PNG, WEBP만 지원합니다."
            ),
        )

    suffix = IMAGE_SUFFIX_MAP[
        image.content_type
    ]

    temp_path = (
        IMAGE_UPLOAD_DIR
        / f"{uuid4().hex}{suffix}"
    )

    try:

        content = await image.read()

        if not content:

            raise HTTPException(
                status_code=400,
                detail="빈 이미지 파일입니다.",
            )

        temp_path.write_bytes(
            content
        )

        result = await run_in_threadpool(
            analyze_image_for_api,
            temp_path,
        )

        return result

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "AI 이미지 분석 중 오류가 "
                f"발생했습니다: {error}"
            ),
        ) from error

    finally:

        if temp_path.exists():

            try:
                temp_path.unlink()

            except OSError:
                pass


# ============================================================
# 영상 분석
# ============================================================

@app.post(
    "/api/vlm/analyze/video",
    response_model=AIAnalysisResponse,
)
async def analyze_video_endpoint(
    video: UploadFile = File(...),
):

    if (
        video.content_type
        not in ALLOWED_VIDEO_CONTENT_TYPES
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "지원하지 않는 영상 형식입니다. "
                "MP4, AVI, MOV만 지원합니다."
            ),
        )

    suffix = VIDEO_SUFFIX_MAP[
        video.content_type
    ]

    # pipeline.py의 analyze_video()가
    # VIDEO_DIR에서 파일을 찾기 때문에
    # 영상은 VIDEO_DIR에 임시 저장한다.
    temp_path = (
        VIDEO_DIR
        / f"{uuid4().hex}{suffix}"
    )

    try:

        content = await video.read()

        if not content:

            raise HTTPException(
                status_code=400,
                detail="빈 영상 파일입니다.",
            )

        temp_path.write_bytes(
            content
        )

        # 현재 FRAME_DIR을 공유하므로
        # 영상 Pipeline은 순차 실행
        async with VIDEO_ANALYSIS_LOCK:

            result = await run_in_threadpool(
                analyze_video_for_api,
                temp_path,
            )

        return result

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                "AI 영상 분석 중 오류가 "
                f"발생했습니다: {error}"
            ),
        ) from error

    finally:

        if temp_path.exists():

            try:
                temp_path.unlink()

            except OSError:
                pass