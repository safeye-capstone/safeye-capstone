import unittest
from copy import deepcopy
from unittest.mock import patch
from app.review_order import attach_review_order
from app.video_pipeline import build_rag_metadata

def hazard(risk,state='REVIEW_REQUIRED',proximity='UNCERTAIN',confidence='LOW'):
    return {'risk_type':risk,'final_decision':state,'detected':True,
            'confidence':confidence,'proximity':proximity,'evidence':'관찰 근거'}

class ReviewOrderTests(unittest.TestCase):
    def test_risk_group_and_exposure_order_ignore_low_confidence(self):
        items=[hazard('NO_HELMET',proximity='IMMEDIATE',confidence='HIGH'),
            hazard('FALL_HAZARD',proximity='NEAR',confidence='HIGH'),
            hazard('UNFASTENED_SAFETY_HARNESS',proximity='IMMEDIATE'),hazard('COLLAPSE')]
        records,queue=attach_review_order(items)
        self.assertEqual([x['risk_type'] for x in queue],['COLLAPSE','UNFASTENED_SAFETY_HARNESS','FALL_HAZARD','NO_HELMET'])
        self.assertEqual(records[3]['review_order'],1)
    def test_unknown_proximity_is_not_treated_as_distant_or_low_confidence(self):
        items=[hazard('NO_HELMET',proximity='NOT_NEAR',confidence='HIGH'),
            hazard('NO_HELMET',confidence='LOW'),hazard('BLOCKED_PATH',proximity='NEAR',confidence='HIGH')]
        _,queue=attach_review_order(items)
        self.assertEqual([x['hazard_index'] for x in queue],[1,2,0])
    def test_records_decisions_and_input_are_preserved_and_queue_indexes_match(self):
        items=[hazard('NO_HELMET','CONFIRMED'),hazard('FALL_HAZARD','REJECTED'),
            hazard('BLOCKED_PATH'),hazard('COLLAPSE')];before=deepcopy(items)
        records,queue=attach_review_order(items)
        self.assertEqual(items,before);self.assertEqual(len(records),len(items))
        for old,new in zip(items,records):
            for key,value in old.items():self.assertEqual(new[key],value)
        self.assertEqual(len(queue),2)
        for item in queue:
            record=records[item['hazard_index']]
            self.assertEqual(record['final_decision'],'REVIEW_REQUIRED')
            self.assertEqual(record['review_order'],item['review_order'])
    def test_video_uses_only_detected_matching_evidence_frame_proximity(self):
        items=[hazard('FALL_HAZARD'),hazard('UNFASTENED_SAFETY_HARNESS')]
        items[1]['evidence_frames']=['frame_2.jpg']
        frames=[{'frame':'frame_1.jpg','hazards':[hazard('UNFASTENED_SAFETY_HARNESS',proximity='IMMEDIATE')]},
          {'frame':'frame_2.jpg','hazards':[dict(hazard('FALL_HAZARD',proximity='IMMEDIATE'),detected=False),
                                        hazard('UNFASTENED_SAFETY_HARNESS',proximity='NEAR')]}]
        _,queue=attach_review_order(items,frames)
        self.assertEqual([x['hazard_index'] for x in queue],[0,1])
        self.assertEqual(queue[1]['review_proximity'],'NEAR')
        items[1]['evidence_frames']=[]
        _,queue=attach_review_order(items,frames)
        self.assertEqual(queue[0]['hazard_index'],1)
    def test_completed_candidates_have_no_stale_order_and_empty_queue_is_valid(self):
        old=hazard('COLLAPSE','CONFIRMED');old['review_order']=1
        records,queue=attach_review_order([old])
        self.assertEqual(queue,[]);self.assertNotIn('review_order',records[0]);self.assertEqual(old['review_order'],1)
        self.assertEqual(attach_review_order([]),([],[]))
    def test_video_metadata_queue_includes_related_review_records(self):
        items=[hazard('NO_HELMET'),hazard('FALL_HAZARD')]
        items[1]['is_primary_hazard']=False
        data={'consolidated_hazards':items,'hazards':[],'frames':[]}
        metadata=build_rag_metadata(data)
        self.assertEqual(len(metadata['hazards']),2);self.assertEqual(len(metadata['review_queue']),2)
        self.assertEqual(metadata['review_queue'][0]['risk_type'],'FALL_HAZARD')
        self.assertEqual(metadata['vlm_decision_state'],'REVIEW_REQUIRED')
    def test_image_api_metadata_adds_queue_without_changing_pending_state(self):
        from app.image_pipeline import analyze_image_for_api
        items=[hazard('NO_HELMET'),hazard('COLLAPSE')]
        analysis={'scene_context':{'category':'INDUSTRIAL'},'scene_description':'작업 현장','hazards':items,'workers':[]}
        with patch('app.rag.focused_observation.analyze_candidates',return_value=deepcopy(analysis)), \
             patch('app.rag.focused_observation.prepare_frame_candidates',return_value=deepcopy(analysis)), \
             patch('app.image_pipeline.classify_image_hazards',return_value=deepcopy(items)), \
             patch('app.image_pipeline.verify_image_candidates',return_value=deepcopy(items)), \
             patch('app.image_pipeline.search_related_regulations',return_value=[]):
            result=analyze_image_for_api('unused.jpg')
        data=result.model_dump(mode='json')
        self.assertFalse(data['is_danger']);self.assertEqual(data['severity'],'WARNING')
        self.assertEqual(data['ragMetadata']['review_queue'][0]['risk_type'],'COLLAPSE')
        self.assertEqual(data['ragMetadata']['hazards'][0]['risk_type'],'NO_HELMET')
        self.assertEqual(result.ragMetadata['hazards'][0]['evidence'],'관찰 근거')
        self.assertNotIn('evidence',data['ragMetadata']['hazards'][0])
if __name__=='__main__':unittest.main()
