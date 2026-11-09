"""Local smoke test: simulated VLM/RAG, real video decoding and YOLO/MediaPipe."""
import json
import sys
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import pipeline
from app.video_pipeline import build_rag_metadata, get_video_decision_state


def fake_vlm(path):
    hazards = []
    if path.name == 'frame_0002.00.jpg':
        hazards = [{'risk_type': 'COLLAPSE', 'detected': True, 'confidence': 'MEDIUM',
                    'proximity': 'IMMEDIATE', 'evidence': '사람이 넘어지는 것으로 의심됨'}]
    return json.dumps({'workers': [], 'hazards': hazards, 'scene_description': '테스트 후보'}, ensure_ascii=False)


with patch.object(pipeline, 'analyze_image', side_effect=fake_vlm), \
        patch.object(pipeline, 'search_regulations', return_value=[]) as rag:
    result = pipeline.analyze_video('1_2collapse.mp4')
    record = result['consolidated_hazards'][0]
    assert record['risk_type'] == 'COLLAPSE', record
    assert record['collapse_verification']['status'] == 'FALL_SUSPECTED', record
    assert record['final_decision'] == 'CONFIRMED', record
    assert record['collapse_verification']['clips'][0]['stopped_after_event']
    assert record['collapse_verification']['clips'][0]['frames'] < 100
    assert get_video_decision_state(result) == 'CONFIRMED'
    assert build_rag_metadata(result)['hazards'][0]['collapse_verification']['events']
    assert '[RISK_TYPE=COLLAPSE]' in rag.call_args.kwargs['query']
    output = ROOT / 'pose_results' / 'collapse_pipeline_smoke.json'
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'decision':record['final_decision'], 'verification':record['collapse_verification'],
                      'timings_seconds':result['timings_seconds']}, ensure_ascii=True), flush=True)
    print(output, flush=True)
