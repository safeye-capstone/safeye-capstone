import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import Mock
from app.rag.aggregator import aggregate_frame_results
from app.rag.collapse_verification import apply_collapse_verification, candidate_windows
from app.rag.final_decision import apply_final_decisions
from app.rag.query_builder import build_search_query, normalize_vlm_analysis


def candidate():
    return {'risk_type': 'COLLAPSE', 'detected': True, 'final_decision': 'REVIEW_REQUIRED',
            'evidence_frames': ['frame_0002.00.jpg'], 'evidence': ['쓰러짐 의심']}


class CollapseVerificationTests(unittest.TestCase):
    def test_only_collapse_review_candidates_run_vision(self):
        other = dict(candidate(), risk_type='FALL_HAZARD')
        rejected = dict(candidate(), final_decision='REJECTED')
        missing = dict(candidate(), detected=False)
        verifier = Mock(side_effect=AssertionError('should not run'))
        records = [other, rejected, missing]
        self.assertEqual(apply_collapse_verification(records, Path('unused'), verifier=verifier), records)
        verifier.assert_not_called()

    def test_empty_candidates_do_not_load_vision(self):
        verifier = Mock()
        self.assertEqual(apply_collapse_verification([], Path('unused'), verifier=verifier), [])
        verifier.assert_not_called()

    def test_windows_merge_and_budget(self):
        windows, limited = candidate_windows(['frame_0000.00.jpg', 'frame_0002.00.jpg', 'frame_0004.00.jpg',
                                             'frame_0020.00.jpg', 'frame_0040.00.jpg'])
        self.assertEqual(windows, [(0., 6.), (16., 22.)])
        self.assertTrue(limited)
        self.assertEqual(candidate_windows(['unknown', '../frame_0002.00.jpg']), ([], False))

    def test_candidate_window_includes_pre_transition_upright_context(self):
        self.assertEqual(candidate_windows(['frame_0004.00.jpg']), ([(0., 6.)], False))

    def test_event_confirms_and_preserves_original(self):
        hazard = candidate()
        verifier = Mock(return_value={'status': 'FALL_SUSPECTED', 'events': [{'decision_seconds': 3.0}]})
        result = apply_collapse_verification([hazard], Path('unused'), verifier=verifier)[0]
        self.assertEqual(result['final_decision'], 'CONFIRMED')
        self.assertEqual(hazard['final_decision'], 'REVIEW_REQUIRED')
        self.assertIn('[RISK_TYPE=COLLAPSE]', build_search_query(result))
        self.assertNotIn('작업발판', build_search_query(result))

    def test_negative_missing_window_and_error_stay_pending(self):
        for verifier in [Mock(return_value={'status': 'INCONCLUSIVE', 'events': []}),
                         Mock(side_effect=RuntimeError('missing model'))]:
            with self.assertLogs('app.rag.collapse_verification', level='ERROR') if verifier.side_effect else nullcontext():
                result = apply_collapse_verification([candidate()], Path('unused'), verifier=verifier)[0]
            self.assertEqual(result['final_decision'], 'REVIEW_REQUIRED')
            self.assertTrue(result['detected'])
        bad = dict(candidate(), evidence_frames=['bad'])
        verifier = Mock()
        self.assertEqual(apply_collapse_verification([bad], Path('unused'), verifier=verifier)[0]['collapse_verification']['status'], 'NO_VALID_WINDOW')
        verifier.assert_not_called()

    def test_vlm_candidate_survives_and_cannot_confirm_from_stills(self):
        raw = {'workers': [], 'hazards': [{'risk_type': 'COLLAPSE', 'detected': True,
               'confidence': 'HIGH', 'proximity': 'IMMEDIATE', 'evidence': '바닥에 사람이 누워 있음'}]}
        analysis = normalize_vlm_analysis(raw)
        frames = [dict(analysis, frame='frame_0002.00.jpg'), dict(analysis, frame='frame_0004.00.jpg')]
        aggregate = aggregate_frame_results(frames)
        self.assertEqual(aggregate[0]['risk_type'], 'COLLAPSE')
        aggregate[0].update(reliability_label='HIGH', final_reliability_label='HIGH')
        self.assertEqual(apply_final_decisions(aggregate)[0]['final_decision'], 'REVIEW_REQUIRED')


if __name__ == '__main__':
    unittest.main()
