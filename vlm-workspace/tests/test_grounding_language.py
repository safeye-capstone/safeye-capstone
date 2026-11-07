import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from app.local import ollama_client as client
from app.rag.query_builder import normalize_vlm_analysis
from app.rag.aggregator import aggregate_frame_results
from app.rag.final_decision import apply_final_decisions


def observation(category='INDUSTRIAL'):
    return {'scene_context':{'category':category,'evidence':'관찰된 활동 맥락'},
            'workers':[{'worker_id':1,'posture':'UPRIGHT','helmet':'NOT_WEARING','vest':'UNCERTAIN','harness':'NOT_APPLICABLE',
                        'work_level':'GROUND','position':'지상에 서 있음','observations':['머리가 보이고 안전모가 없음']}],
            'hazards':[{'risk_type':'NO_HELMET','worker_ids':[1],'visual_evidence':['HEAD_VISIBLE','HELMET_ABSENT'],'detected':True,'confidence':'HIGH','proximity':'NEAR','evidence':'안전모 미착용'}],
            'scene_description':'사람이 서 있음'}


def response(obj):
    return {'model':'test','done':True,'done_reason':'stop','response':json.dumps(obj,ensure_ascii=False)}


class GroundingAndLanguageTests(unittest.TestCase):
    def test_non_industrial_attributes_are_not_industrial_warnings_but_collapse_survives(self):
        raw=observation('NON_INDUSTRIAL')
        raw['workers'][0]['posture']='LYING_OR_ROLLING'
        raw['hazards'].append({'risk_type':'COLLAPSE','detected':True,'confidence':'LOW','proximity':'NEAR','evidence':'바닥에 누워 있음'})
        result=normalize_vlm_analysis(raw)
        self.assertTrue(all(not h['detected'] for h in result['hazards'] if h['risk_type']=='NO_HELMET'))
        self.assertTrue(next(h['detected'] for h in result['hazards'] if h['risk_type']=='COLLAPSE'))
        self.assertEqual(result['workers'][0]['helmet'],'NOT_WEARING')

    def test_uncertain_context_cannot_be_promoted_by_high_temporal_score(self):
        normalized=normalize_vlm_analysis(observation('UNCERTAIN'))
        frames=[dict(deepcopy(normalized),frame=f'frame_{i:04d}.00.jpg') for i in range(3)]
        aggregate=aggregate_frame_results(frames)
        aggregate[0].update(final_reliability_label='HIGH',reverification_applied=True,
                            reverification_successful_votes=2,reverification_positive_votes=2)
        self.assertEqual(apply_final_decisions(aggregate)[0]['final_decision'],'REVIEW_REQUIRED')

    def test_industrial_helmet_risk_remains_detectable(self):
        normalized=normalize_vlm_analysis(observation('INDUSTRIAL'))
        self.assertTrue(any(h['risk_type']=='NO_HELMET' and h['detected'] for h in normalized['hazards']))
        aggregate=aggregate_frame_results([dict(deepcopy(normalized),frame=f'frame_{i:04d}.00.jpg') for i in range(3)])
        aggregate[0]['final_reliability_label']='HIGH'
        self.assertEqual(apply_final_decisions(aggregate)[0]['final_decision'],'CONFIRMED')

    def test_multi_risk_harness_guard_does_not_erase_other_risk(self):
        raw=observation()
        raw['hazards']=[{'risk_type':'UNFASTENED_SAFETY_HARNESS|FALL_HAZARD','detected':True,
                         'confidence':'MEDIUM','proximity':'NEAR','evidence':'높은 개구부 가장자리'}]
        result=normalize_vlm_analysis(raw)
        self.assertTrue(next(h['detected'] for h in result['hazards'] if h['risk_type']=='FALL_HAZARD'))

    def test_generic_unstable_footing_cannot_become_confirmed_fall_hazard(self):
        raw=observation('INDUSTRIAL')
        raw['hazards']=[{'risk_type':'FALL_HAZARD','detected':True,'confidence':'MEDIUM',
                         'proximity':'NEAR','evidence':'새로 깔린 아스팔트에서 발걸음이 불안정해 추락할 수 있음'}]
        normalized=normalize_vlm_analysis(raw)
        frames=[dict(deepcopy(normalized),frame=f'frame_{i:04d}.00.jpg') for i in range(3)]
        aggregate=aggregate_frame_results(frames)
        fall=next(h for h in aggregate if h['risk_type']=='FALL_HAZARD')
        fall.update(final_reliability_label='HIGH',reverification_applied=True,
                    reverification_successful_votes=2,reverification_positive_votes=2)
        self.assertEqual(apply_final_decisions([fall])[0]['final_decision'],'REVIEW_REQUIRED')

    def test_specific_opening_risk_remains_eligible_for_confirmation(self):
        raw=observation('INDUSTRIAL')
        raw['hazards']=[{'risk_type':'FALL_HAZARD','detected':True,'confidence':'HIGH',
                         'worker_ids':[1],'visual_evidence':['EDGE_OR_OPENING_VISIBLE','PERSON_EXPOSED','PROTECTION_MISSING'],
                         'proximity':'IMMEDIATE','evidence':'작업자가 덮개 없는 개구부 가장자리 바로 옆에 서 있음'}]
        normalized=normalize_vlm_analysis(raw)
        frames=[dict(deepcopy(normalized),frame=f'frame_{i:04d}.00.jpg') for i in range(3)]
        aggregate=aggregate_frame_results(frames)
        fall=next(h for h in aggregate if h['risk_type']=='FALL_HAZARD')
        fall['final_reliability_label']='HIGH'
        self.assertEqual(apply_final_decisions([fall])[0]['final_decision'],'CONFIRMED')

    def test_language_repair_uses_text_only_and_preserves_decisions(self):
        raw=observation()
        raw['workers'][0]['position']='Standing on the ground'
        raw['hazards'][0]['evidence']='No helmet is worn'
        before=deepcopy(raw)
        with patch.object(client,'request_ollama',return_value=response({'field_0':'지상에 서 있음','field_1':'안전모를 착용하지 않음'})) as request:
            result=client.repair_analysis_language(raw)
        self.assertIsNone(request.call_args.args[1])
        self.assertEqual(raw,before)
        self.assertEqual(result['hazards'][0]['detected'],before['hazards'][0]['detected'])
        self.assertEqual(result['hazards'][0]['risk_type'],before['hazards'][0]['risk_type'])
        self.assertEqual(result['hazards'][0]['confidence'],before['hazards'][0]['confidence'])
        client.validate_korean_output(result)

    def test_enum_mentions_are_localized_in_text_without_changing_enum_fields(self):
        raw=observation()
        raw['hazards'][0]['evidence']='위험 자세 (LYING_OR_ROLLING)'
        with patch.object(client,'request_ollama',return_value=response({'field_0':'위험 자세 (LYING_OR_ROLLING)'})):
            result=client.repair_analysis_language(raw)
        self.assertEqual(result['hazards'][0]['evidence'],'위험 자세 (바닥에 누움 또는 구름)')
        self.assertEqual(result['hazards'][0]['risk_type'],'NO_HELMET')

    def test_partial_translation_retries_only_missing_or_invalid_original_fields(self):
        raw=observation()
        raw['workers'][0]['position']='Standing on the ground'
        raw['hazards'][0]['evidence']='No helmet is worn'
        with patch.object(client,'request_ollama',side_effect=[response({'field_0':'지상에 서 있음','field_1':'Helmet'}),
                                                              response({'field_1':'안전모를 착용하지 않음'})]) as request:
            result=client.repair_analysis_language(raw)
        retry_prompt=request.call_args_list[1].args[2]
        self.assertNotIn('Standing on the ground',retry_prompt)
        self.assertIn('No helmet is worn',retry_prompt)
        self.assertEqual(result['workers'][0]['position'],'지상에 서 있음')
        self.assertEqual(result['hazards'][0]['detected'],raw['hazards'][0]['detected'])

    def test_failed_language_repair_does_not_reinfer_image(self):
        raw=observation()
        raw['scene_description']='A person is standing'
        with patch.object(client,'validate_image',return_value=Path('unused.jpg')), \
                patch.object(client,'prepare_image_base64',return_value='encoded-image'), \
                patch.object(client,'request_ollama',side_effect=[response(raw),response({'field_0':'Still English'}),response({'field_0':'Still English'})]) as request:
            with self.assertRaisesRegex(RuntimeError,'원래 판단은 재생성하지 않음'):
                client.analyze_image('unused.jpg',prompt='검사')
        self.assertEqual(request.call_count,3)
        self.assertEqual(request.call_args_list[0].args[1],'encoded-image')
        self.assertTrue(all(call.args[1] is None for call in request.call_args_list[1:]))

    def test_stable_squat_contradiction_is_not_a_collapse_but_unknown_is_preserved(self):
        for posture, expected in [('SQUATTING',False),('LYING_OR_ROLLING',True),('UNCERTAIN',True)]:
            raw=observation('NON_INDUSTRIAL')
            raw['workers'][0]['posture']=posture
            raw['hazards']=[{'risk_type':'COLLAPSE','detected':True,'confidence':'LOW','proximity':'NEAR','evidence':'넘어질 수 있음'}]
            result=normalize_vlm_analysis(raw)
            self.assertEqual(result['hazards'][0]['detected'],expected)
        raw=observation('NON_INDUSTRIAL')
        raw['workers'][0]['posture']='SQUATTING'
        raw['hazards']=[{'risk_type':'COLLAPSE','detected':True,'confidence':'HIGH','proximity':'NEAR','evidence':'비정상 자세 근거'}]
        self.assertTrue(normalize_vlm_analysis(raw)['hazards'][0]['detected'])

    def test_scene_context_requires_a_reason(self):
        raw=observation()
        raw['scene_context']['evidence']=''
        with self.assertRaises(client.OllamaBadJSON):
            client.validate_analysis_schema(raw)

    def test_context_exclusions_remain_in_api_audit_metadata(self):
        from app.video_pipeline import build_rag_metadata
        normalized=normalize_vlm_analysis(observation('NON_INDUSTRIAL'))
        result={'consolidated_hazards':[], 'frames':[dict(normalized,frame='frame_0000.00.jpg')]}
        metadata=build_rag_metadata(result)
        self.assertEqual(metadata['scene_contexts'][0]['context']['category'],'NON_INDUSTRIAL')
        self.assertTrue(metadata['context_exclusions'])
        self.assertTrue(metadata['context_exclusions'][0]['hazard']['observed_detected'])

    def test_single_english_word_is_not_accepted_as_korean(self):
        self.assertTrue(client.is_invalid_natural_language('Standing'))
        self.assertTrue(client.is_invalid_natural_language('ころぶ'))
        self.assertTrue(client.is_invalid_natural_language('서 있음 a'))
        self.assertFalse(client.is_invalid_natural_language('지상에 서 있음'))


if __name__=='__main__':
    unittest.main()
