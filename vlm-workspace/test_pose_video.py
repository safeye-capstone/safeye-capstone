import argparse
import math
from pathlib import Path

import cv2
import mediapipe as mp

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "models" / "pose_landmarker_lite.task"
JOINTS = {11: "L shoulder", 12: "R shoulder", 23: "L hip", 24: "R hip"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("video", type=Path, help="입력 MP4 경로")
    args = parser.parse_args()
    if not MODEL.is_file():
        raise SystemExit(f"모델 파일이 없습니다: {MODEL}")
    if not args.video.is_file():
        raise SystemExit(f"영상 파일이 없습니다: {args.video}")

    output = ROOT / "pose_results" / f"{args.video.stem}_pose.mp4"
    output.parent.mkdir(exist_ok=True)
    capture = cv2.VideoCapture(str(args.video))
    writer = None
    frames = visible_frames = 0
    last_ms = -1
    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not capture.isOpened() or not math.isfinite(fps) or fps <= 0:
            raise SystemExit("영상을 열 수 없거나 FPS를 읽을 수 없습니다.")

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=MODEL.read_bytes()),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=1,
        )
        with mp.tasks.vision.PoseLandmarker.create_from_options(options) as model:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                height, width = frame.shape[:2]
                if writer is None:
                    writer = cv2.VideoWriter(
                        str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
                    )
                    if not writer.isOpened():
                        raise SystemExit(f"출력 영상을 만들 수 없습니다: {output}")

                last_ms = max(last_ms + 1, round(frames * 1000 / fps))
                image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                )
                result = model.detect_for_video(image, last_ms)
                visible = 0
                if result.pose_landmarks:
                    pose = result.pose_landmarks[0]
                    for index, label in JOINTS.items():
                        joint = pose[index]
                        if (joint.visibility or 0) < 0.5:
                            continue
                        if not (0 <= joint.x < 1 and 0 <= joint.y < 1):
                            continue
                        x, y = int(joint.x * width), int(joint.y * height)
                        cv2.circle(frame, (x, y), 6, (0, 255, 0), -1)
                        cv2.putText(frame, label, (x + 8, y), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.5, (0, 255, 0), 1)
                        visible += 1
                visible_frames += int(visible == len(JOINTS))
                cv2.putText(frame, f"{frames / fps:.2f}s | joints {visible}/4",
                            (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                writer.write(frame)
                frames += 1
    finally:
        capture.release()
        if writer is not None:
            writer.release()

    if not frames:
        raise SystemExit("읽을 수 있는 영상 프레임이 없습니다.")
    print(f"결과: {output}")
    print(f"어깨·엉덩이 4점이 모두 표시된 프레임: {visible_frames}/{frames}")


if __name__ == "__main__":
    main()