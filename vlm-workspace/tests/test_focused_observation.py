import unittest
from pathlib import Path
from unittest.mock import patch
from app.rag.focused_observation import interpret_observations, verify_risk
from app.rag.reverification import update_confirmation_observations, run_prompt_ensemble
from app.rag.final_decision import determine_final_decision
from app.image_pipeline import verify_image_candidates

def observed(risk, items, context='INDUSTRIAL'):
    return interpret_observations(risk,{'context':context,'observations':items})
class FocusedObservationTests(unittest.TestCase):
    def test_head_visibility_and_context(self):
        item={'head_visible':'YES','helmet':'NOT_WEARING'}
        good=observed('NO_HELMET',[item])
        self.assertTrue(good['confirmation_eligible'])
        self.assertEqual(good['visual_evidence'],['HEAD_VISIBLE','HELMET_ABSENT'])
        for context in ['UNCERTAIN','NON_INDUSTRIAL']:
            self.assertFalse(observed('NO_HELMET',[item],context)['confirmation_eligible'])
        self.assertFalse(observed('NO_HELMET',[dict(item,head_visible='UNKNOWN')])['conclusive'])
    def test_no_cross_person_partial_evidence(self):
        result=observed('NO_HELMET',[{'head_visible':'YES','helmet':'WEARING'},
            {'head_visible':'UNKNOWN','helmet':'NOT_WEARING'}])
        self.assertFalse(result['confirmation_eligible'])
        self.assertFalse(result['conclusive'])
    def test_harness_hidden_hook_never_confirms(self):
        item={'elevated_support':'YES','torso_visible':'YES','harness':'DISCONNECTED','hook_visible':'UNKNOWN'}
        self.assertFalse(observed('UNFASTENED_SAFETY_HARNESS',[item])['confirmation_eligible'])
        self.assertTrue(observed('UNFASTENED_SAFETY_HARNESS',[dict(item,hook_visible='YES')])['confirmation_eligible'])
        self.assertFalse(observed('UNFASTENED_SAFETY_HARNESS',[dict(item,elevated_support='NO',hook_visible='YES')])['confirmation_eligible'])
    def test_edge_and_passage_require_complete_same_observation(self):
        self.assertFalse(observed('FALL_HAZARD',[{'edge_or_opening':'YES','person_exposed':'YES','protection_missing':'UNKNOWN'}])['confirmation_eligible'])
        self.assertFalse(observed('BLOCKED_PATH',[{'passage_visible':'UNKNOWN','passage_blocked':'YES'}])['conclusive'])
        self.assertTrue(observed('BLOCKED_PATH',[{'passage_visible':'YES','passage_blocked':'YES',
            'route_box':[100,100,500,900],'obstacle_box':[150,300,450,600],'obstacle_kind':'MATERIAL'}])['confirmation_eligible'])
    def test_empty_malformed_and_nonindustrial(self):
        self.assertFalse(observed('NO_HELMET',[])['conclusive'])
        for items in [[{'head_visible':True,'helmet':'WEARING'}],[{'helmet':'WEARING'}]]:
            with self.assertRaises(ValueError):observed('NO_HELMET',items)
    def test_low_candidate_can_be_resolved_by_distinct_focused_frames(self):
        result=observed('NO_HELMET',[{'head_visible':'YES','helmet':'NOT_WEARING'}])
        timeline=[{'frame':f'frame_{i}.jpg'} for i in range(3)]
        details=[dict(result,frame=frame['frame'],status='SUCCESS') for frame in timeline[:2]]
        h={'detected':True,'risk_type':'NO_HELMET','required_count':2,'confirmation_observations':[],
            'final_reliability_label':'LOW','meets_min_detection_count':False}
        h.update(update_confirmation_observations(h,details,timeline))
        self.assertEqual(determine_final_decision(h)[0],'CONFIRMED')
        details[1]=dict(details[1],detected=False,confirmation_eligible=False,conclusive=False)
        h.update(update_confirmation_observations(h,details,timeline))
        self.assertEqual(determine_final_decision(h)[0],'REVIEW_REQUIRED')
    def test_image_recheck_resolves_without_old_tags_and_does_not_confirm_uncertainty(self):
        candidate={'risk_type':'NO_HELMET','detected':True,'confidence':'LOW','worker_ids':[9],
            'final_decision':'REVIEW_REQUIRED'}
        positive=observed('NO_HELMET',[{'head_visible':'YES','helmet':'NOT_WEARING'}])
        checked=verify_image_candidates('unused.jpg',[candidate],verifier=lambda *args:positive)[0]
        self.assertEqual(checked['final_decision'],'CONFIRMED')
        self.assertEqual(checked['worker_ids'],[])
        self.assertEqual(checked['initial_worker_ids'],[9])
        uncertain=observed('NO_HELMET',[{'head_visible':'UNKNOWN','helmet':'UNKNOWN'}])
        self.assertEqual(verify_image_candidates('unused.jpg',[candidate],verifier=lambda *args:uncertain)[0]['final_decision'],'REVIEW_REQUIRED')
        def fail(*args):raise RuntimeError('offline')
        self.assertEqual(verify_image_candidates('unused.jpg',[candidate],verifier=fail)[0]['final_decision'],'REVIEW_REQUIRED')
    def test_incomplete_model_response_rejected(self):
        with patch('app.rag.focused_observation.client.prepare_image_base64',return_value='data'),patch('app.rag.focused_observation.client.request_ollama',return_value={'done':False,'response':'{}'}):
            with self.assertRaises(ValueError):verify_risk(Path('unused.jpg'),'NO_HELMET')
    def test_new_candidate_is_not_automatic_confirmation(self):
        from app.rag.focused_observation import prepare_frame_candidates
        raw={'scene_context':{'category':'INDUSTRIAL','evidence':'공사 현장'},'workers':[],
            'hazards':[],'scene_description':'현장'}
        response={'context':'INDUSTRIAL','people':[{'head_visible':'YES','helmet':'NOT_WEARING',
            'elevated_support':'NO','harness':'NOT_APPLICABLE'}]}
        result=prepare_frame_candidates('unused.jpg',raw,observer=lambda path:response)
        self.assertEqual(result['hazards'][0]['risk_type'],'NO_HELMET')
        self.assertFalse(result['hazards'][0]['confirmation_eligible'])
        self.assertEqual(result['hazards'][0]['confidence'],'LOW')
    def test_language_failure_retains_only_pending_structured_data(self):
        from app.rag.focused_observation import analyze_candidates
        from app.local.ollama_client import AnalysisLanguageError
        raw={'scene_context':{'category':'INDUSTRIAL','evidence':'작업 현장'},
            'workers':[{'position':'English text','observations':['English text']}],
            'hazards':[{'risk_type':'NO_HELMET','confidence':'HIGH','detected':True,'evidence':'English text'}],
            'scene_description':'English text'}
        with patch('app.rag.focused_observation.client.AnalysisLanguageError',AnalysisLanguageError):
            analyzer=unittest.mock.Mock(side_effect=AnalysisLanguageError('translation failed',raw))
            result=analyze_candidates('unused.jpg',analyzer)
        self.assertEqual(analyzer.call_count,1)
        self.assertEqual(result['language_status'],'FAILED')
        self.assertEqual(result['hazards'][0]['confidence'],'LOW')
        self.assertEqual(raw['hazards'][0]['confidence'],'HIGH')
    def test_unknown_recheck_is_not_negative_vote(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'pose_results') as tmp:
            image=Path(tmp)/'one.jpg';image.write_bytes(b'image')
            with patch('app.rag.reverification.run_single_reverification',return_value={
                    'detected':False,'confidence':'LOW','conclusive':False,'confirmation_eligible':False}):
                result=run_prompt_ensemble(image,'NO_HELMET')
        self.assertEqual(result['negative_votes'],0)
        self.assertIsNone(result['prompt_agreement'])
    def test_scattered_focused_checks_cannot_bypass_low_score(self):
        timeline=[{'frame':f'frame_{i}.jpg'} for i in range(5)]
        old=[{'frame':timeline[i]['frame'],'evidence':'직접 근거'} for i in [1,2]]
        positive=observed('NO_HELMET',[{'head_visible':'YES','helmet':'NOT_WEARING'}])
        details=[dict(positive,status='SUCCESS',frame=timeline[i]['frame']) for i in [0,4]]
        h={'detected':True,'risk_type':'NO_HELMET','required_count':2,'confirmation_observations':old,
            'final_reliability_label':'LOW','meets_min_detection_count':True}
        h.update(update_confirmation_observations(h,details,timeline))
        self.assertTrue(h['confirmation_ready'])
        self.assertFalse(h['focused_confirmation_ready'])
        self.assertEqual(determine_final_decision(h)[0],'REVIEW_REQUIRED')
    def test_observed_lying_posture_restores_missing_collapse_candidate_only(self):
        from app.rag.focused_observation import prepare_frame_candidates
        for posture,expected in [('LYING_OR_ROLLING',True),('LOSING_BALANCE',True),('SQUATTING',False)]:
            raw={'scene_context':{'category':'NON_INDUSTRIAL','evidence':'운동 장면'},
                'workers':[{'worker_id':1,'posture':posture,'work_level':'GROUND','helmet':'UNCERTAIN'}],
                'hazards':[],'scene_description':'운동 장면'}
            result=prepare_frame_candidates('unused.jpg',raw,
                observer=lambda path:{'context':'NON_INDUSTRIAL','people':[]})
            candidates=[h for h in result['hazards'] if h['risk_type']=='COLLAPSE' and h['detected']]
            self.assertEqual(bool(candidates),expected)
            if candidates:
                self.assertEqual(candidates[0]['confidence'],'LOW')
                self.assertFalse(candidates[0]['confirmation_eligible'])
if __name__=='__main__':unittest.main()
