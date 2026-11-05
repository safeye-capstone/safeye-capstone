import unittest
from unittest.mock import patch
from app.rag.spatial_review import group_person_boxes,review_candidate
from app.rag.focused_observation import interpret_observations

def observed(helmet='WEARING',visible='YES'):
    return interpret_observations('NO_HELMET',{'context':'INDUSTRIAL','observations':[{'head_visible':visible,'helmet':helmet}]})
def regions(count):
    return {'crops':[{'target_id':f'p{i}','person_box':[i*20,0,i*20+10,100],'path':'unused'} for i in range(count)],
        'detected_people':count,'coverage_limited':False,'batch_size':8}

class CropBatchTests(unittest.TestCase):
    def test_exact_duplicates_share_one_member_with_all_source_indices(self):
        groups=group_person_boxes([(0,0,50,100)]*3)
        self.assertEqual(len(groups),1);self.assertEqual(groups[0]['members'][0]['raw_indices'],[0,1,2])
    def test_near_duplicate_views_are_preserved_and_distinct_neighbors_are_not_merged(self):
        boxes=[(0,0,50,100),(1,1,50,80),(30,0,80,100)]
        groups=group_person_boxes(boxes)
        self.assertEqual(len(groups),2)
        self.assertEqual({member['box'] for group in groups for member in group['members']},set(boxes))
    def test_ninth_target_is_checked_and_can_supply_positive_evidence(self):
        visited=[]
        def check(path,crop,risk):
            visited.append((crop['target_id'],crop['batch_index']))
            return observed('NOT_WEARING' if crop['target_id']=='p8' else 'WEARING')
        result=review_candidate('unused','NO_HELMET',{},whole_verifier=lambda *args:observed('UNKNOWN','UNKNOWN'),
            cropper=lambda *args:regions(10),crop_verifier=check,budget_seconds=None)
        self.assertTrue(result['confirmation_eligible'])
        self.assertEqual(len(visited),10);self.assertIn(('p8',2),visited)
        self.assertEqual(result['spatial_target'],'p8')
        self.assertEqual(result['spatial_review']['positive_target_ids'],['p8'])
        self.assertEqual(result['spatial_review']['pending_target_ids'],[])
    def test_budget_preserves_every_unreviewed_target_and_never_rejects(self):
        check=unittest.mock.Mock(return_value=observed())
        result=review_candidate('unused','NO_HELMET',{},whole_verifier=lambda *args:observed(),
            cropper=lambda *args:regions(10),crop_verifier=check,budget_seconds=0)
        check.assert_not_called()
        self.assertFalse(result['conclusive']);self.assertFalse(result['confirmation_eligible'])
        self.assertEqual(len(result['spatial_review']['pending_target_ids']),10)
        self.assertTrue(all(item['status']=='PENDING' for item in result['spatial_review']['checks']))
    def test_partial_budget_does_not_turn_checked_negatives_into_a_complete_negative(self):
        with patch('app.rag.spatial_review.time.monotonic',side_effect=range(20)):
            result=review_candidate('unused','NO_HELMET',{},whole_verifier=lambda *args:observed(),
                cropper=lambda *args:regions(3),crop_verifier=lambda *args:observed(),budget_seconds=2.5)
        self.assertFalse(result['conclusive'])
        self.assertEqual(result['spatial_review']['reviewed_targets'],2)
        self.assertEqual(result['spatial_review']['pending_target_ids'],['p2'])
    def test_all_batches_are_required_before_a_clear_negative(self):
        result=review_candidate('unused','NO_HELMET',{'review_context':{'context':'INDUSTRIAL','worker_count':10}},
            whole_verifier=lambda *args:observed(),cropper=lambda *args:regions(10),
            crop_verifier=lambda *args:observed(),budget_seconds=None)
        self.assertTrue(result['conclusive']);self.assertFalse(result['detected'])
        self.assertEqual(result['spatial_review']['reviewed_targets'],10)
    def test_ambiguous_grouping_cannot_prove_complete_person_coverage(self):
        crop_regions=regions(2);crop_regions['grouping_ambiguous']=True
        result=review_candidate('unused','NO_HELMET',{},whole_verifier=lambda *args:observed(),
            cropper=lambda *args:crop_regions,crop_verifier=lambda *args:observed())
        self.assertFalse(result['conclusive'])
if __name__=='__main__':unittest.main()
