from pathlib import Path

import cv2


def clear_frames(
    output_dir: str | Path,
) -> None:
    """
    이전 테스트에서 생성된 프레임 JPG를 삭제한다.
    """

    output_dir = Path(output_dir)

    if not output_dir.exists():
        return

    for file in output_dir.glob("frame_*.jpg"):
        file.unlink()


def extract_frames(
    video_path: str | Path,
    output_dir: str | Path,
    interval_sec: float = 2.0,
) -> list[Path]:
    """
    영상을 일정 시간 간격으로 JPG 프레임으로 추출한다.
    """

    video_path = Path(video_path)
    output_dir = Path(output_dir)

    if not video_path.exists():
        raise FileNotFoundError(
            f"영상 파일을 찾을 수 없습니다: {video_path}"
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    cap = cv2.VideoCapture(str(video_path))

    if not cap.isOpened():
        raise ValueError(
            f"영상을 열 수 없습니다: {video_path}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        cap.release()
        raise ValueError(
            "영상의 FPS를 확인할 수 없습니다."
        )

    frame_interval = max(
        1,
        round(fps * interval_sec),
    )

    frame_index = 0
    saved_frames: list[Path] = []

    while True:
        success, frame = cap.read()

        if not success:
            break

        if frame_index % frame_interval == 0:
            timestamp = frame_index / fps
            filename = f"frame_{timestamp:07.2f}.jpg"
            frame_path = output_dir / filename

            success, encoded_image = cv2.imencode(".jpg", frame)

            if not success:
                raise RuntimeError(
                    f"프레임 인코딩 실패: {frame_path}"
                )

            encoded_image.tofile(str(frame_path))
            saved_frames.append(frame_path)

        frame_index += 1

    cap.release()

    return saved_frames


if __name__ == "__main__":
    from app.local.config import FRAME_DIR, VIDEO_DIR

    video_path = VIDEO_DIR / "test.mp4"

    clear_frames(FRAME_DIR)

    frames = extract_frames(
        video_path,
        FRAME_DIR,
        interval_sec=2.0,
    )

    print(f"총 {len(frames)}개의 프레임 추출 완료")

    for frame in frames:
        print(frame)
