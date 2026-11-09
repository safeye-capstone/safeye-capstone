import unittest
from app.rag.focused_observation import prepare_frame_candidates, interpret_observations
from app.rag.spatial_review import review_candidate
from app.rag.final_decision import determine_final_decision
from app.image_pipeline import verify_image_candidates

def raw(workers=None,hazards=None):
    return {'scene_context':{'category':'INDUSTRIAL','evidence':'작업 현장'},
        'workers':workers or [],'hazards':hazards or [],'scene_description':'작업 현장'}
def person(**kw):
    return dict({'head_visible':'YES','helmet':'WEARING','elevated_support':'NO','harness':'NOT_APPLICABLE'},**kw)
def worker(**kw):
    return dict({'worker_id':1,'helmet':'WEARING','work_level':'GROUND','harness':'NOT_APPLICABLE'},**kw)
def observe(items):return {'context':'INDUSTRIAL','people':items}
def head(visible='YES',helmet='NOT_WEARING'):
    return interpret_observations('NO_HELMET',{'context':'INDUSTRIAL','observations':[{'head_visible':visible,'helmet':helmet}]})
def crops(limited=False,expected=1):
    return {'crops':[{'target_id':'p1','person_box':[1,1,100,200],'path':'unused'}],
        'detected_people':expected,'coverage_limited':limited}

class PriorityReviewTests(unittest.TestCase):
    def test_invisible_but_suspected_head_is_pending_candidate(self):
        result=prepare_frame_candidates('unused',raw([worker()]),
            observer=lambda p:observe([person(head_visible='NO',helmet='NOT_WEARING')]))
        hazard=next(h for h in result['hazards'] if h['risk_type']=='NO_HELMET')
        self.assertTrue(hazard['detected']);self.assertFalse(hazard['confirmation_eligible'])
    def test_uncertain_height_and_conflicting_harness_are_pending(self):
        result=prepare_frame_candidates('unused',raw([worker(work_level='ELEVATED',harness='CONNECTED')]),
            observer=lambda p:observe([person(elevated_support='UNKNOWN',harness='DISCONNECTED')]))
        hazard=next(h for h in result['hazards'] if h['risk_type']=='UNFASTENED_SAFETY_HARNESS')
        self.assertEqual(hazard['confidence'],'LOW');self.assertTrue(hazard['review_context']['conflicts'])
    def test_different_person_coverage_is_a_candidate_not_a_verdict(self):
        result=prepare_frame_candidates('unused',raw([worker()]),observer=lambda p:observe([person(),person()]))
        self.assertTrue(any(h['risk_type']=='NO_HELMET' and not h['confirmation_eligible'] for h in result['hazards']))
    def test_conflict_blocks_even_a_positive_injected_image_verifier(self):
        h={'risk_type':'NO_HELMET','detected':True,'review_context':{'conflicts':['관찰 모순']}}
        checked=verify_image_candidates('unused',[h],verifier=lambda *args:head())[0]
        self.assertEqual(checked['final_decision'],'REVIEW_REQUIRED')
    def test_partial_whole_view_can_be_resolved_by_spatial_target(self):
        result=review_candidate('unused','NO_HELMET',{},whole_verifier=lambda *args:head('UNKNOWN','UNKNOWN'),
            cropper=lambda *args:crops(),crop_verifier=lambda *args:head())
        self.assertTrue(result['confirmation_eligible']);self.assertEqual(result['spatial_target'],'p1')
        self.assertEqual(result['worker_ids'],[])
    def test_opposing_whole_and_crop_results_are_never_votes_for_confirmation(self):
        for whole,zoom in [(head(),head(helmet='WEARING')),(head(helmet='WEARING'),head())]:
            checked=review_candidate('unused','NO_HELMET',{},whole_verifier=lambda *args:whole,
                cropper=lambda *args:crops(),crop_verifier=lambda *args:zoom)
            self.assertFalse(checked['confirmation_eligible']);self.assertFalse(checked['conclusive'])
            self.assertTrue(checked['verification_conflicts'])
    def test_spatial_error_and_limited_coverage_do_not_reject(self):
        def fail(*args):raise RuntimeError('model unavailable')
        checked=review_candidate('unused','NO_HELMET',{},whole_verifier=lambda *args:head(),cropper=fail)
        self.assertFalse(checked['confirmation_eligible']);self.assertFalse(checked['conclusive'])
        checked=review_candidate('unused','NO_HELMET',{},whole_verifier=lambda *args:head(helmet='WEARING'),
            cropper=lambda *args:crops(limited=True),crop_verifier=lambda *args:head(helmet='WEARING'))
        self.assertFalse(checked['conclusive'])
    def test_missing_or_sign_or_disjoint_passage_geometry_stays_pending(self):
        base={'passage_visible':'YES','passage_blocked':'YES'}
        for item in [base,dict(base,route_box=[10,10,500,900],obstacle_box=[600,200,900,400],obstacle_kind='FENCE'),
                dict(base,route_box=[10,10,500,900],obstacle_box=[100,200,300,400],obstacle_kind='SIGN'),
                dict(base,route_box=[0,0,1000,1000],obstacle_box=[100,200,300,400],obstacle_kind='MATERIAL')]:
            checked=interpret_observations('BLOCKED_PATH',{'context':'INDUSTRIAL','observations':[item]})
            self.assertFalse(checked['confirmation_eligible']);self.assertFalse(checked['conclusive'])
    def test_video_conflict_cannot_be_overridden_by_high_score_or_quorum(self):
        checked={'detected':True,'risk_type':'NO_HELMET','observation_conflict_required':True,
            'confirmation_ready':True,'focused_confirmation_ready':True,'final_reliability_label':'HIGH'}
        self.assertEqual(determine_final_decision(checked)[0],'REVIEW_REQUIRED')
    def test_complete_spatial_negatives_resolve_a_candidate_without_confirmation(self):
        result=review_candidate('unused','NO_HELMET',{'review_context':{'context':'INDUSTRIAL','conflicts':['착용 관찰 모순'],'worker_count':1}},
            whole_verifier=lambda *args:head(helmet='WEARING'),cropper=lambda *args:crops(),
            crop_verifier=lambda *args:head(helmet='WEARING'))
        self.assertTrue(result['conclusive']);self.assertFalse(result['detected'])
        self.assertFalse(result['verification_conflicts']);self.assertTrue(result['conflicts_resolved'])
    def test_connected_harness_without_visible_hook_is_not_a_clear_negative(self):
        result=interpret_observations('UNFASTENED_SAFETY_HARNESS',{'context':'INDUSTRIAL','observations':[
            {'elevated_support':'YES','torso_visible':'YES','harness':'CONNECTED','hook_visible':'UNKNOWN'}]})
        self.assertFalse(result['conclusive'])
    def test_crop_bounds_limit_and_pixels_match_original_preprocessing(self):
        import tempfile
        from pathlib import Path
        from PIL import Image
        from unittest.mock import patch
        from app.rag import spatial_review
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'pose_results') as tmp:
            root=Path(tmp);source=root/'original.jpg'
            image=Image.new('RGB',(40,20),'white');exif=Image.Exif();exif[274]=6;image.save(source,exif=exif)
            boxes=tuple((0,0,40,20) for i in range(9))
            with patch.object(spatial_review,'ROOT',root),patch.object(spatial_review,'_person_boxes',return_value=boxes):
                result=spatial_review.person_crops(source)
            self.assertEqual(result['raw_detection_count'],9);self.assertEqual(result['detected_people'],1)
            self.assertEqual(result['exact_duplicates_removed'],8);self.assertFalse(result['coverage_limited'])
            self.assertEqual(len(result['crops']),1)
            with Image.open(result['crops'][0]['path']) as crop:self.assertEqual(crop.size,(40,20))
    def test_unmatched_height_harness_conflict_is_not_erased_by_negative_crops(self):
        negative=interpret_observations('UNFASTENED_SAFETY_HARNESS',{'context':'INDUSTRIAL','observations':[
            {'elevated_support':'NO','torso_visible':'YES','harness':'UNKNOWN','hook_visible':'UNKNOWN'}]})
        result=review_candidate('unused','UNFASTENED_SAFETY_HARNESS',{'review_context':{
            'context':'INDUSTRIAL','conflicts':['높이·안전대 관찰과 사람 대응 불명확'],'worker_count':1}},
            whole_verifier=lambda *args:negative,cropper=lambda *args:crops(),crop_verifier=lambda *args:negative)
        self.assertFalse(result['conclusive']);self.assertTrue(result['verification_conflicts'])
    def test_initial_conflict_propagates_through_video_aggregation(self):
        from app.rag.aggregator import aggregate_frame_results
        base=raw([worker()],[{'risk_type':'NO_HELMET','detected':True,'confidence':'HIGH',
            'evidence':'미착용 판단','proximity':'NEAR'}])
        frame=prepare_frame_candidates('unused',base,observer=lambda p:observe([person()]))
        h=next(h for h in frame['hazards'] if h['risk_type']=='NO_HELMET')
        self.assertTrue(h['observation_conflict_required']);self.assertFalse(h['confirmation_eligible'])
        aggregated=aggregate_frame_results([dict(frame,frame=f'frame_{i}.jpg') for i in range(3)])[0]
        self.assertTrue(aggregated['observation_conflict_required'])
    def test_nonindustrial_scenes_do_not_spawn_industrial_review_candidates(self):
        from unittest.mock import Mock
        base=raw([worker(helmet='NOT_WEARING',posture='LYING_OR_ROLLING')])
        base['scene_context']={'category':'NON_INDUSTRIAL','evidence':'운동 장면'}
        observer=Mock(return_value=observe([person(helmet='NOT_WEARING')]))
        result=prepare_frame_candidates('unused',base,observer=observer)
        observer.assert_not_called()
        detected=[h['risk_type'] for h in result['hazards'] if h.get('detected')]
        self.assertEqual(detected,['COLLAPSE'])
if __name__=='__main__':unittest.main()
