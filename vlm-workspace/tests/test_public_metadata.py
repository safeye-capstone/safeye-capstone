import json
import unittest
from copy import deepcopy
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import app
from app.public_metadata import build_public_metadata
from app.review_order import attach_review_order, REVIEW_ORDER_POLICY
from app.schemas import VLMResponse
from app.video_pipeline import build_rag_metadata


def regulation(article="제44조"):
    return {
        "metadata": {"law_name": "산업안전보건기준에 관한 규칙", "article": article,
                     "article_title": "안전대의 부착설비 등", "internal": "PRIVATE"},
        "document": "PRIVATE 법령 본문", "distance": 0.2,
    }


def detailed_metadata():
    records, queue = attach_review_order([
        {"risk_type": "NO_HELMET", "final_decision": "REJECTED"},
        {"risk_type": "COLLAPSE", "final_decision": "REVIEW_REQUIRED",
         "final_decision_reason": "연속 영상 추가 확인 필요",
         "collapse_verification": {"status": "ERROR", "error": "PRIVATE"},
         "focused_verification": {"spatial_review": {"path": "PRIVATE"}},
         "confirmation_missing": ["PRIVATE"], "new_internal_field": "PRIVATE"},
        {"risk_type": "FALL_HAZARD", "final_decision": "REVIEW_REQUIRED",
         "is_primary_hazard": False, "parent_risk_type": "UNFASTENED_SAFETY_HARNESS"},
    ])
    return {
        "vlm_decision_state": "REVIEW_REQUIRED", "hazards": records,
        "review_queue": queue, "review_order_policy": REVIEW_ORDER_POLICY,
        "review_required_regulations": [regulation(), regulation()],
        "related_regulations": [regulation("제42조")],
        "confirmed_regulations": [regulation("제43조")],
        "language_status": "FAILED", "scene_context": {"evidence": "PRIVATE"},
        "raw_hazards": [{"evidence": "PRIVATE"}], "new_internal_field": "PRIVATE",
    }


class PublicMetadataTests(unittest.TestCase):
    def test_public_contract_keeps_queue_indexes_and_does_not_mutate_internal_records(self):
        metadata = detailed_metadata()
        before = deepcopy(metadata)
        public = build_public_metadata(metadata)
        self.assertEqual(metadata, before)
        self.assertEqual(set(public), {"vlm_decision_state", "hazards", "review_queue",
                                      "review_order_policy", "review_required_regulations"})
        self.assertEqual(len(public["hazards"]), 3)
        for entry in public["review_queue"]:
            target = public["hazards"][entry["hazard_index"]]
            self.assertEqual(target["risk_type"], entry["risk_type"])
            self.assertEqual(target["final_decision"], "REVIEW_REQUIRED")
        self.assertEqual(public["hazards"][2]["parent_risk_type"], "UNFASTENED_SAFETY_HARNESS")
        self.assertNotIn("PRIVATE", json.dumps(public))
        self.assertEqual(public["review_required_regulations"], [{"metadata": {
            "law_name": "산업안전보건기준에 관한 규칙", "article": "제44조",
            "article_title": "안전대의 부착설비 등"}}])

    def test_reference_fallback_and_empty_preferred_list_keep_frontend_semantics(self):
        public = build_public_metadata({"related_regulations": [regulation()]})
        self.assertEqual(len(public["related_regulations"]), 1)
        self.assertNotIn("review_required_regulations", public)
        public = build_public_metadata({"review_required_regulations": [],
                                        "related_regulations": [regulation()]})
        self.assertEqual(public, {"review_required_regulations": []})

    def test_video_pending_references_remain_available_without_confirmed_law_leak(self):
        result = {
            "consolidated_hazards": [
                {"risk_type": "COLLAPSE", "final_decision": "REVIEW_REQUIRED"},
                {"risk_type": "NO_HELMET", "final_decision": "CONFIRMED"}],
            "hazards": [{"risk_type": "COLLAPSE", "regulations": [regulation()]},
                        {"risk_type": "NO_HELMET", "regulations": [regulation("제42조")]}],
        }
        detailed = build_rag_metadata(result)
        public = build_public_metadata(detailed)
        self.assertEqual(public["vlm_decision_state"], "CONFIRMED")
        self.assertEqual([item["metadata"]["article"] for item in
                          public["review_required_regulations"]], ["제44조"])
        self.assertIn("regulations", detailed["hazards"][0])
        self.assertNotIn("regulations", public["hazards"][0])

    def test_none_empty_and_repeated_serialization_are_safe(self):
        self.assertIsNone(build_public_metadata(None))
        self.assertEqual(build_public_metadata({}), {})
        public = build_public_metadata(detailed_metadata())
        self.assertEqual(build_public_metadata(public), public)

    def test_collapse_keeps_actual_clip_and_event_times_without_model_details(self):
        metadata = detailed_metadata()
        metadata["hazards"][1]["collapse_verification"] = {
            "status": "FALL_SUSPECTED", "method": "PRIVATE", "device": "PRIVATE",
            "elapsed_seconds": 12, "requested_windows": [[0, 6]],
            "clips": [{"start": 0, "end": 3.04, "requested_end": 6,
                       "status": "ANALYZED", "frames": 76, "four_joint_observations": 20},
                      {"start": 20, "end": 22, "status": "OUT_OF_RANGE", "frames": 0}],
            "events": [{"clip_index": 0, "track_id": 7,
                        "suspected_start_seconds": 2.4, "decision_seconds": 3.0}],
        }
        before = deepcopy(metadata)
        public = build_public_metadata(metadata)
        self.assertEqual(public["hazards"][1]["collapse_verification"], {
            "status": "FALL_SUSPECTED", "clips": [{"start": 0, "end": 3.04}],
            "events": [{"suspected_start_seconds": 2.4, "decision_seconds": 3.0}],
        })
        self.assertEqual(metadata, before)
        self.assertEqual(public["review_queue"], before["review_queue"])
        self.assertEqual(build_public_metadata(public), public)
        self.assertNotIn("PRIVATE", json.dumps(public))

    def test_collapse_failure_does_not_turn_requested_windows_into_analyzed_clips(self):
        for status in ("ERROR", "NO_VALID_WINDOW", "INCONCLUSIVE"):
            with self.subTest(status=status):
                metadata = detailed_metadata()
                metadata["hazards"][1]["collapse_verification"] = {
                    "status": status, "error": "PRIVATE", "requested_windows": [[0, 6]],
                    "events": [],
                }
                summary = build_public_metadata(metadata)["hazards"][1]["collapse_verification"]
                self.assertEqual(summary, {"status": status, "clips": [], "events": []})
        metadata["hazards"][1].pop("collapse_verification")
        self.assertNotIn("collapse_verification", build_public_metadata(metadata)["hazards"][1])

    def test_video_http_response_exposes_collapse_summary_and_keeps_review_queue(self):
        metadata = detailed_metadata()
        metadata["hazards"][1]["collapse_verification"] = {
            "status": "INCONCLUSIVE", "requested_windows": [[0, 6]], "events": [],
            "clips": [{"status": "ANALYZED", "start": 0, "end": 6, "frames": 150}],
            "method": "PRIVATE",
        }
        response = VLMResponse(is_danger=False, severity="WARNING", action_guide="확인 필요",
                               vlm_description="검토 후보", violated_regulation="", ragMetadata=metadata)
        with TestClient(app) as client, patch("app.api.analyze_video_for_api", return_value=response):
            received = client.post("/api/vlm/analyze/video", files={"video": ("test.mp4", b"test", "video/mp4")})
        self.assertEqual(received.status_code, 200, received.text)
        public = received.json()["ragMetadata"]
        self.assertEqual(public["hazards"][1]["collapse_verification"], {
            "status": "INCONCLUSIVE", "clips": [{"start": 0, "end": 6}], "events": [],
        })
        self.assertEqual(public["review_queue"], metadata["review_queue"])
        self.assertNotIn("PRIVATE", received.text)

    def test_actual_http_image_and_video_responses_exclude_internal_details(self):
        response = VLMResponse(
            is_danger=False, severity="WARNING", action_guide="현장 확인 필요",
            vlm_description="쓰러짐 검토 후보", violated_regulation="",
            ragMetadata=detailed_metadata(),
        )
        before = deepcopy(response.ragMetadata)
        with TestClient(app) as client:
            for route, field, mime, function in [
                ("/api/vlm/analyze", "image", "image/jpeg", "analyze_image_for_api"),
                ("/api/vlm/analyze/video", "video", "video/mp4", "analyze_video_for_api"),
            ]:
                with self.subTest(route=route), patch("app.api." + function, return_value=response):
                    received = client.post(route, files={field: ("test", b"test-input", mime)})
                    self.assertEqual(received.status_code, 200, received.text)
                    data = received.json()
                    self.assertFalse(data["is_danger"])
                    self.assertEqual(data["severity"], "WARNING")
                    self.assertEqual(data["action_guide"], response.action_guide)
                    self.assertEqual(data["vlm_description"], response.vlm_description)
                    self.assertEqual(data["violated_regulation"], "")
                    self.assertEqual(data["ragMetadata"], build_public_metadata(before))
                    self.assertNotIn("PRIVATE", received.text)
        self.assertEqual(response.ragMetadata, before)


if __name__ == "__main__":
    unittest.main()
