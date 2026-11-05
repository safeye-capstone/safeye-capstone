"""Run YOLO s640 and per-track MediaPipe only around VLM collapse candidates."""
import logging
import math
import os
import re
import time
from copy import deepcopy
from pathlib import Path

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
FRAME_TIME = re.compile(r"^frame_(\d+(?:\.\d+)?)\.jpg$")
PRE_CONTEXT_SECONDS = 4.0
POST_CONTEXT_SECONDS = 2.0
MAX_VIDEO_SECONDS = 12.0


def candidate_windows(evidence_frames, context_seconds=PRE_CONTEXT_SECONDS, max_seconds=MAX_VIDEO_SECONDS,
                      post_seconds=POST_CONTEXT_SECONDS):
    """Merge overlaps and bound work without treating omitted footage as negative."""
    intervals = []
    for frame in evidence_frames:
        match = FRAME_TIME.fullmatch(str(frame))
        if match:
            timestamp = float(match.group(1))
            if math.isfinite(timestamp):
                intervals.append((max(0.0, timestamp - context_seconds), timestamp + post_seconds))
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    selected, remaining = [], max_seconds
    truncated = False
    for start, end in merged:
        if remaining <= 0:
            truncated = True
            break
        stop = min(end, start + remaining)
        selected.append((start, stop))
        remaining -= stop - start
        truncated |= stop < end
    return selected, truncated


def verify_windows(video_path, windows):
    """Decode native-rate candidate clips; no output rendering or full-video inference."""
    started = time.perf_counter()
    os.environ['YOLO_CONFIG_DIR'] = str(ROOT / 'pose_results' / 'yolo_config')
    os.environ['MPLCONFIGDIR'] = str(ROOT / 'pose_results' / 'mpl_config')
    os.environ['YOLO_AUTOINSTALL'] = 'false'
    import cv2
    import mediapipe as mp
    from ultralytics import YOLO
    import detect_collapse as base

    weights = ROOT / 'models' / 'yolo11s.pt'
    if not weights.is_file() or not base.MODEL.is_file():
        raise FileNotFoundError('YOLO 또는 MediaPipe 모델 파일이 없습니다.')
    cap = cv2.VideoCapture(str(video_path))
    events, clips = [], []
    try:
        fps, frame_count = cap.get(cv2.CAP_PROP_FPS), int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not cap.isOpened() or not math.isfinite(fps) or fps <= 0 or frame_count <= 0:
            raise ValueError('영상 또는 FPS를 읽을 수 없습니다.')
        model = YOLO(str(weights))
        options = mp.tasks.vision.PoseLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_buffer=base.MODEL.read_bytes()),
            running_mode=mp.tasks.vision.RunningMode.VIDEO, num_poses=1)
        for clip_index, (start, end) in enumerate(windows):
            first = min(frame_count, max(0, math.floor(start * fps)))
            stop = min(frame_count, math.ceil(end * fps))
            if first >= stop:
                clips.append({'start': start, 'end': end, 'status': 'OUT_OF_RANGE', 'frames': 0})
                continue
            cap.set(cv2.CAP_PROP_POS_FRAMES, first)
            if abs(cap.get(cv2.CAP_PROP_POS_FRAMES) - first) > 1:
                raise RuntimeError('후보 구간으로 이동하지 못했습니다.')
            if model.predictor is not None:
                for tracker in getattr(model.predictor, 'trackers', []):
                    tracker.reset()
            tracks, poses = {}, {}
            read_count, valid_joint_observations = 0, 0
            last_ms = -1
            try:
                for frame_index in range(first, stop):
                    ok, frame = cap.read()
                    if not ok:
                        raise RuntimeError('후보 구간의 영상 프레임을 읽지 못했습니다.')
                    read_count += 1
                    time_s = frame_index / fps
                    last_ms = max(last_ms + 1, round(time_s * 1000))
                    result = model.track(frame, persist=True, tracker='bytetrack.yaml', classes=[0], conf=0.25,
                                         imgsz=640, device='cpu', verbose=False)[0]
                    for tid in list(tracks):
                        if time_s - tracks[tid].last_seen > base.TRACK_TIMEOUT_SECONDS:
                            del tracks[tid]
                            if tid in poses:
                                poses.pop(tid).close()
                    if result.boxes.id is None:
                        continue
                    height, width = frame.shape[:2]
                    for tid, box in zip(result.boxes.id.int().cpu().tolist(), result.boxes.xyxy.cpu().tolist()):
                        x1, y1, x2, y2 = box
                        px, py = (x2-x1)*0.15, (y2-y1)*0.15
                        a, b = max(0, int(x1-px)), max(0, int(y1-py))
                        c, d = min(width, math.ceil(x2+px)), min(height, math.ceil(y2+py))
                        if c <= a or d <= b:
                            continue
                        track = tracks.setdefault(tid, base.Track(((x1+x2)/2, (y1+y2)/2), time_s))
                        track.last_seen = time_s
                        if tid not in poses:
                            poses[tid] = mp.tasks.vision.PoseLandmarker.create_from_options(options)
                        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame[b:d, a:c], cv2.COLOR_BGR2RGB))
                        result_pose = poses[tid].detect_for_video(image, last_ms)
                        points = {}
                        if result_pose.pose_landmarks:
                            points = {k: (x+a, y+b) for k, (x, y) in base.get_points(result_pose.pose_landmarks[0], c-a, d-b).items()}
                        valid_joint_observations += int(len(points) == 4)
                        before = track.fall_at
                        base.update_collapse(tid, track, points, time_s)
                        if before is None and track.fall_at is not None:
                            events.append({'clip_index': clip_index, 'track_id': tid,
                                           'suspected_start_seconds': track.fall_at, 'decision_seconds': time_s})
                            break
                    if events:
                        break
            finally:
                for pose in poses.values():
                    pose.close()
            clips.append({'start': first/fps, 'end': (first+read_count)/fps, 'requested_end': stop/fps,
                          'status': 'ANALYZED', 'stopped_after_event': bool(events),
                          'frames': read_count, 'four_joint_observations': valid_joint_observations})
            if events:
                break
    finally:
        cap.release()
    return {'status': 'FALL_SUSPECTED' if events else 'INCONCLUSIVE', 'events': events,
            'clips': clips, 'elapsed_seconds': round(time.perf_counter()-started, 3),
            'method': 'yolo11s_640_bytetrack_mediapipe_lite_lookback_v2', 'device': 'cpu'}


def apply_collapse_verification(hazards, video_path, *, verifier=None):
    """Only review-state COLLAPSE candidates incur vision work; failure stays pending."""
    results = deepcopy(hazards)
    for hazard in results:
        if (hazard.get('risk_type') != 'COLLAPSE' or not hazard.get('detected')
                or hazard.get('final_decision') != 'REVIEW_REQUIRED'):
            continue
        windows, truncated = candidate_windows(hazard.get('evidence_frames', []))
        if not windows:
            hazard['collapse_verification'] = {'status': 'NO_VALID_WINDOW', 'events': []}
            continue
        try:
            verification = (verifier or verify_windows)(video_path, windows)
        except Exception as error:
            logger.exception('쓰러짐 후보 구간 검증 실패')
            verification = {'status': 'ERROR', 'error': str(error), 'events': []}
        verification['requested_windows'] = windows
        verification['coverage_limited'] = truncated
        hazard['collapse_verification'] = verification
        hazard['final_decision_method'] = 'candidate_clip_yolo_mediapipe_v1'
        # A heuristic event supports the candidate but does not establish a medical cause.
        if verification.get('events') and verification.get('status') == 'FALL_SUSPECTED':
            hazard['final_decision'] = 'CONFIRMED'
            hazard['final_decision_reason'] = '후보 전후 영상에서 기존 자세·하강·유지시간 조건을 만족하는 쓰러짐 의심 동작이 확인됨'
            evidence = hazard.get('evidence', [])
            if isinstance(evidence, str):
                evidence = [evidence]
            hazard['evidence'] = list(evidence) + [hazard['final_decision_reason']]
        else:
            hazard['final_decision_reason'] = '추가 분석에서 쓰러짐 조건을 확인하지 못했거나 분석이 불완전하여 검토 상태를 유지함'
    return results
