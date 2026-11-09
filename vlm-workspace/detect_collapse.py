import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import cv2
import mediapipe as mp

ROOT = Path(__file__).resolve().parent
MODEL = ROOT / "models" / "pose_landmarker_lite.task"
JOINTS = {11: "L shoulder", 12: "R shoulder", 23: "L hip", 24: "R hip"}
PREVIEW_WINDOW = "Collapse detection"

UPRIGHT_DEG = 30
TILTED_DEG = 60
DROP_RATIO = 0.5
TRANSITION_SECONDS = 1.0
HOLD_SECONDS = 0.5
MAX_HOLD_GAP_SECONDS = 0.20
MAX_UPRIGHT_GAP_SECONDS = 0.25

TRACK_TIMEOUT_SECONDS = 0.75
MATCH_DISTANCE_RATIO = 0.12

Point = tuple[float, float]


@dataclass
class Track:
    center: Point
    last_seen: float
    last_valid_time: float | None = None
    upright: tuple[float, float, float] | None = None
    tilted_since: float | None = None
    fall_at: float | None = None


def get_points(pose, width: int, height: int) -> dict[int, Point]:
    points = {}
    for index in JOINTS:
        joint = pose[index]
        if (joint.visibility or 0) >= 0.5 and 0 <= joint.x < 1 and 0 <= joint.y < 1:
            points[index] = (joint.x * width, joint.y * height)
    return points


def get_center(points: dict[int, Point]) -> Point:
    return (
        sum(x for x, _ in points.values()) / len(points),
        sum(y for _, y in points.values()) / len(points),
    )


def match_tracks(
    tracks: dict[int, Track], centers: list[Point], max_distance: float
) -> dict[int, int]:
    candidates = []
    for index, center in enumerate(centers):
        for track_id, track in tracks.items():
            distance = math.dist(center, track.center)
            if distance <= max_distance:
                candidates.append((distance, index, track_id))

    matches = {}
    used_ids = set()
    for _, index, track_id in sorted(candidates):
        if index not in matches and track_id not in used_ids:
            matches[index] = track_id
            used_ids.add(track_id)
    return matches


def update_collapse(
    track_id: int, track: Track, points: dict[int, Point], time_s: float
) -> float | None:
    if len(points) != len(JOINTS):
        return None

    if track.last_valid_time is not None:
        gap = round(time_s - track.last_valid_time, 3)
        if gap > MAX_HOLD_GAP_SECONDS:
            track.tilted_since = None
        if gap > MAX_UPRIGHT_GAP_SECONDS:
            track.upright = None
    track.last_valid_time = time_s

    shoulder_x = (points[11][0] + points[12][0]) / 2
    shoulder_y = (points[11][1] + points[12][1]) / 2
    hip_x = (points[23][0] + points[24][0]) / 2
    hip_y = (points[23][1] + points[24][1]) / 2
    dx = abs(shoulder_x - hip_x)
    dy = abs(shoulder_y - hip_y)
    torso_length = math.hypot(dx, dy)

    if torso_length < 1:
        track.tilted_since = None
        return None

    angle = math.degrees(math.atan2(dx, dy))
    if angle <= UPRIGHT_DEG and shoulder_y < hip_y:
        track.upright = (time_s, shoulder_y, torso_length)
        track.tilted_since = None
    elif angle >= TILTED_DEG and track.upright is not None:
        upright_time, upright_y, upright_length = track.upright
        dropped = shoulder_y - upright_y >= DROP_RATIO * upright_length
        if not dropped:
            track.tilted_since = None
        elif track.tilted_since is None:
            if time_s - upright_time <= TRANSITION_SECONDS:
                track.tilted_since = time_s
        elif track.fall_at is None and time_s - track.tilted_since >= HOLD_SECONDS:
            track.fall_at = track.tilted_since
            print(
                f"ID {track_id} | 쓰러짐 의심 구간 시작: {track.fall_at:.2f}초, "
                f"판정 시각: {time_s:.2f}초"
            )
    else:
        track.tilted_since = None
    return angle


def draw_track(frame, track_id: int, track: Track, points, angle):
    color = (0, 0, 255) if track.fall_at is not None else (0, 255, 0)
    for x, y in points.values():
        cv2.circle(frame, (int(x), int(y)), 6, color, -1)

    label = f"ID {track_id} | joints {len(points)}/4"
    if angle is not None:
        label += f" | {angle:.0f} deg"
    if track.fall_at is not None:
        label += " | FALL SUSPECTED"

    height, width = frame.shape[:2]
    text_width = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0][0]
    x = max(0, min(int(track.center[0]), width - text_width - 4))
    y = max(20, min(int(min(y for _, y in points.values())) - 10, height - 4))
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)


def main():
    parser = argparse.ArgumentParser(description="영상에서 사람별 쓰러짐 의심 구간 찾기")
    parser.add_argument("video", type=Path, help="입력 영상 경로")
    parser.add_argument("--max-people", type=int, default=2, help="최대 자세 감지 인원")
    args = parser.parse_args()
    if args.max_people < 1:
        parser.error("--max-people은 1 이상이어야 합니다.")
    if not MODEL.is_file():
        raise SystemExit(f"모델 파일이 없습니다: {MODEL}")
    if not args.video.is_file():
        raise SystemExit(f"영상 파일이 없습니다: {args.video}")

    output = ROOT / "pose_results" / f"{args.video.stem}_collapse.mp4"
    output.parent.mkdir(exist_ok=True)
    capture = cv2.VideoCapture(str(args.video))
    writer = None
    preview_open = False
    tracks: dict[int, Track] = {}
    next_id = 1
    frames = fall_count = 0
    last_ms = -1

    try:
        fps = capture.get(cv2.CAP_PROP_FPS)
        if not capture.isOpened() or not math.isfinite(fps) or fps <= 0:
            raise SystemExit("영상을 열 수 없거나 FPS를 읽을 수 없습니다.")

        preview_delay_ms = max(1, round(1000 / fps))
        try:
            cv2.namedWindow(PREVIEW_WINDOW, cv2.WINDOW_NORMAL)
            preview_open = True
        except cv2.error:
            print("미리보기 창을 열 수 없어 분석과 결과 저장만 진행합니다.")

        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=MODEL.read_bytes()),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_poses=args.max_people,
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
                time_s = last_ms / 1000
                image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                )
                result = model.detect_for_video(image, last_ms)
                detections = []
                for pose in result.pose_landmarks:
                    points = get_points(pose, width, height)
                    if len(points) >= 2:
                        detections.append(points)

                tracks = {
                    track_id: track for track_id, track in tracks.items()
                    if time_s - track.last_seen <= TRACK_TIMEOUT_SECONDS
                }
                centers = [get_center(points) for points in detections]
                matches = match_tracks(
                    tracks, centers, MATCH_DISTANCE_RATIO * math.hypot(width, height)
                )

                for index, points in enumerate(detections):
                    track_id = matches.get(index)
                    if track_id is None:
                        track_id = next_id
                        next_id += 1
                        tracks[track_id] = Track(centers[index], time_s)
                    track = tracks[track_id]
                    track.center = centers[index]
                    track.last_seen = time_s
                    already_detected = track.fall_at is not None
                    angle = update_collapse(track_id, track, points, time_s)
                    if not already_detected and track.fall_at is not None:
                        fall_count += 1
                    draw_track(frame, track_id, track, points, angle)

                status = f"{time_s:.2f}s | poses: {len(result.pose_landmarks)} | tracked: {len(detections)}"
                cv2.putText(
                    frame, status, (12, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    1.0, (0, 255, 255), 2,
                )
                writer.write(frame)
                frames += 1

                if preview_open:
                    try:
                        cv2.imshow(PREVIEW_WINDOW, frame)
                        key = cv2.waitKey(preview_delay_ms) & 0xFF
                        if cv2.getWindowProperty(PREVIEW_WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                            preview_open = False
                        elif key in (ord("q"), ord("Q"), 27):
                            cv2.destroyWindow(PREVIEW_WINDOW)
                            preview_open = False
                    except cv2.error:
                        preview_open = False
    finally:
        capture.release()
        if writer is not None:
            writer.release()
        if preview_open:
            try:
                cv2.destroyWindow(PREVIEW_WINDOW)
            except cv2.error:
                pass

    if not frames:
        raise SystemExit("읽을 수 있는 영상 프레임이 없습니다.")
    print(f"결과: {output}")
    print(f"처리한 프레임: {frames}, 쓰러짐 의심 판정: {fall_count}건")


if __name__ == "__main__":
    main()