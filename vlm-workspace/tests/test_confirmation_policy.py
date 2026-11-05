import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from app.local.config import local_settings
from app.local.ollama_client import OllamaClient, normalize_worker_ids
from app.rag.query_builder import normalize_vlm_analysis
from app.rag.aggregator import aggregate_frame_results
from app.rag.final_decision import apply_final_decisions
from app.rag.reverification import run_prompt_ensemble, select_distinct_reverification_frames, update_confirmation_observations
from app.rag.confidence_calibrator import apply_confidence_recalibration
from app.image_pipeline import classify_image_hazards


def worker(worker_id=1, helmet='NOT_WEARING', work_level='GROUND', harness='NOT_APPLICABLE'):
    return {'worker_id':worker_id,'helmet':helmet,'vest':'UNCERTAIN','harness':harness,
            'work_level':work_level,'posture':'UPRIGHT','position':'관찰 위치','observations':['관찰 근거']}


def hazard(risk='NO_HELMET', codes=None, ids=None, confidence='HIGH'):
    return {'risk_type':risk,'detected':True,'confidence':confidence,'proximity':'NEAR',
            'worker_ids':[1] if ids is None else ids,
            'visual_evidence':['HEAD_VISIBLE','HELMET_ABSENT'] if codes is None else codes,
            'evidence':'작업자 머리의 안전모 미착용이 확인됨' if risk=='NO_HELMET' else '개구부 가장자리의 관찰 근거'}


def scene(hazards, workers=None):
    return {'scene_context':{'category':'INDUSTRIAL','evidence':'산업 작업 관찰'},
            'workers':workers or [worker()], 'hazards':hazards,'scene_description':'관찰 장면'}


def decide(raw, frames=3):
    normalized=normalize_vlm_analysis(deepcopy(raw))
    records=aggregate_frame_results([dict(deepcopy(normalized),frame=f'frame_{i:04d}.00.jpg') for i in range(frames)])
    for h in records:
        h.update(final_reliability_label='HIGH',reverification_applied=True,
                 reverification_successful_votes=2,reverification_positive_votes=2,reverification_unique_frames=2)
    return normalized,apply_final_decisions(records)


class ConfirmationPolicyTests(unittest.TestCase):
    def test_supplement_only_stays_low_and_cannot_be_promoted_by_repeated_agreement(self):
        normalized, decisions=decide(scene([]))
        self.assertEqual(len(normalized['hazards']),1)
        self.assertEqual(normalized['hazards'][0]['confidence'],'LOW')
        self.assertFalse(normalized['hazards'][0]['confirmation_eligible'])
        self.assertEqual(decisions[0]['confirmation_detection_count'],0)
        self.assertEqual(decisions[0]['final_decision'],'REVIEW_REQUIRED')

    def test_each_risk_requires_its_own_complete_evidence(self):
        cases=[('NO_HELMET',['HEAD_VISIBLE','HELMET_ABSENT'],[worker()]),
               ('UNFASTENED_SAFETY_HARNESS',['ELEVATED_SUPPORT_VISIBLE','ANCHOR_DISCONNECTED'],
                [worker(work_level='ELEVATED',harness='WORN_NOT_CONNECTED')]),
               ('FALL_HAZARD',['EDGE_OR_OPENING_VISIBLE','PERSON_EXPOSED','PROTECTION_MISSING'],[worker()]),
               ('BLOCKED_PATH',['PASSAGE_VISIBLE','PASSAGE_BLOCKED'],[worker()])]
        for risk,codes,workers in cases:
            with self.subTest(risk=risk):
                _,good=decide(scene([hazard(risk,codes)],workers))
                target=next(h for h in good if h['risk_type']==risk)
                self.assertEqual(target['final_decision'],'CONFIRMED')
                _,bad=decide(scene([hazard(risk,codes[:-1])],workers))
                self.assertEqual(next(h for h in bad if h['risk_type']==risk)['final_decision'],'REVIEW_REQUIRED')

    def test_duplicate_candidates_merge_without_high_boost_or_double_count(self):
        source=hazard(confidence='MEDIUM')
        normalized, decisions=decide(scene([source,deepcopy(source)]))
        self.assertEqual(len(normalized['hazards']),1)
        self.assertEqual(normalized['hazards'][0]['confidence'],'MEDIUM')
        self.assertEqual(decisions[0]['detection_count'],3)
        self.assertEqual(decisions[0]['confirmation_detection_count'],3)

    def test_partial_evidence_from_different_people_is_not_combined(self):
        normalized, decisions=decide(scene([hazard(codes=['HEAD_VISIBLE'],ids=[1]),
                                            hazard(codes=['HELMET_ABSENT'],ids=[2])],
                                           [worker(1),worker(2)]))
        self.assertFalse(normalized['hazards'][0]['confirmation_eligible'])
        self.assertEqual(decisions[0]['final_decision'],'REVIEW_REQUIRED')

    def test_uncertain_anchor_connection_is_not_confirmed(self):
        normalized, decisions=decide(scene([hazard('UNFASTENED_SAFETY_HARNESS',
                       ['ELEVATED_SUPPORT_VISIBLE','ANCHOR_DISCONNECTED'])],
                       [worker(work_level='ELEVATED',harness='UNCERTAIN')]))
        target=next(h for h in decisions if h['risk_type']=='UNFASTENED_SAFETY_HARNESS')
        self.assertTrue(target['detected'])
        self.assertEqual(target['final_decision'],'REVIEW_REQUIRED')

    def test_low_direct_observation_does_not_become_high_by_supplement(self):
        normalized, decisions=decide(scene([hazard(confidence='LOW')]))
        self.assertEqual(normalized['hazards'][0]['confidence'],'LOW')
        self.assertEqual(decisions[0]['final_decision'],'REVIEW_REQUIRED')

    def test_image_api_applies_the_same_confirmation_gate(self):
        raw=scene([hazard(codes=[])])
        normalized=normalize_vlm_analysis(deepcopy(raw))
        self.assertEqual(classify_image_hazards(raw,normalized)[0]['final_decision'],'REVIEW_REQUIRED')

    def test_worker_renumbering_remaps_references_and_rejects_ambiguous_ids(self):
        raw=scene([hazard(ids=[9])],[worker(7,helmet='WEARING'),worker(9)])
        normalized=normalize_worker_ids(raw)
        self.assertEqual(normalized['hazards'][0]['worker_ids'],[2])
        self.assertTrue(normalize_vlm_analysis(normalized)['hazards'][0]['confirmation_eligible'])
        raw=scene([hazard(ids=[7])],[worker(7),worker(7)])
        normalized=normalize_vlm_analysis(normalize_worker_ids(raw))
        self.assertTrue(all(not h['confirmation_eligible'] for h in normalized['hazards']))

    def test_temporally_scattered_complete_evidence_does_not_confirm(self):
        good=normalize_vlm_analysis(scene([hazard()]))
        frames=[dict(deepcopy(good),frame='frame_0000.00.jpg')]
        frames += [{'frame':f'frame_{i:04d}.00.jpg','hazards':[]} for i in range(1,6)]
        frames += [dict(deepcopy(good),frame='frame_0006.00.jpg')]
        aggregate=aggregate_frame_results(frames)
        aggregate[0]['final_reliability_label']='HIGH'
        self.assertFalse(aggregate[0]['confirmation_ready'])
        self.assertEqual(apply_final_decisions(aggregate)[0]['final_decision'],'REVIEW_REQUIRED')

    def test_reverification_uses_distinct_frames_and_not_duplicate_bytes(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'pose_results') as folder:
            root=Path(folder); a=root/'frame_0000.00.jpg'; b=root/'frame_0002.00.jpg'; c=root/'frame_0004.00.jpg'
            a.write_bytes(b'one'); b.write_bytes(b'one'); c.write_bytes(b'two')
            selected=select_distinct_reverification_frames(a,[{'frame':p.name} for p in [a,b,c]],root)
            self.assertEqual(selected,[a,c])
            with patch('app.rag.reverification.run_single_reverification',return_value={'detected':True,'confidence':'HIGH','evidence':'근거'}) as verify:
                result=run_prompt_ensemble(a,'NO_HELMET',additional_image_paths=[b,c])
                self.assertEqual(verify.call_count,2)
                self.assertEqual([call.kwargs['image_path'] for call in verify.call_args_list],[a,c])
                self.assertEqual(result['successful_votes'],2)
            with patch('app.rag.reverification.run_single_reverification',return_value={'detected':True,'confidence':'HIGH','evidence':'근거'}) as verify:
                self.assertEqual(run_prompt_ensemble(a,'NO_HELMET')['successful_votes'],1)
                self.assertEqual(verify.call_count,1)

    def test_high_score_without_required_evidence_still_requests_verification(self):
        normalized=normalize_vlm_analysis(scene([]))
        aggregate=aggregate_frame_results([dict(deepcopy(normalized),frame=f'frame_{i:04d}.00.jpg') for i in range(3)])
        calibrated=apply_confidence_recalibration(aggregate)[0]
        self.assertTrue(calibrated['needs_reverification'])
        self.assertEqual(calibrated['reverification_reason'],'REQUIRED_VISUAL_EVIDENCE_NOT_MET')

    def test_verified_facts_can_complete_gate_but_votes_alone_cannot(self):
        timeline=[{'frame':f'frame_{i:04d}.00.jpg'} for i in range(3)]
        base={'required_count':2,'confirmation_observations':[]}
        votes=[{'frame':f['frame'],'status':'SUCCESS','detected':True,'confidence':'HIGH'} for f in timeline[:2]]
        self.assertFalse(update_confirmation_observations(base,votes,timeline)['confirmation_ready'])
        for detail in votes:
            detail.update(confirmation_eligible=True,candidate_source='vlm',worker_ids=[1],
                          visual_evidence=['HEAD_VISIBLE','HELMET_ABSENT'],evidence='머리 미착용 관찰')
        update=update_confirmation_observations(base,votes,timeline)
        self.assertTrue(update['confirmation_ready'])
        self.assertEqual(update['confirmation_detection_count'],2)
        self.assertEqual(update_confirmation_observations(base,[votes[0],votes[0]],timeline)['confirmation_detection_count'],1)

    def test_reverification_does_not_compress_failed_timeline_positions(self):
        timeline=[{'frame':f'frame_{i:04d}.00.jpg','error':'failed'} for i in range(5)]
        details=[{'frame':timeline[i]['frame'],'status':'SUCCESS','detected':True,'confidence':'HIGH',
                  'confirmation_eligible':True,'candidate_source':'vlm'} for i in [0,4]]
        self.assertFalse(update_confirmation_observations({'required_count':2},details,timeline)['confirmation_ready'])

    def test_temperature_zero_defaults(self):
        self.assertEqual(local_settings.temperature,0.0)
        self.assertEqual(OllamaClient('http://example.test','model')._options()['temperature'],0.0)


if __name__=='__main__':
    unittest.main()
