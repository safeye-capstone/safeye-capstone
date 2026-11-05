import unittest
from pathlib import Path
from unittest.mock import patch
from app import pipeline
from app.local.ollama_client import VLM_SCHEMA
from app.rag.regulation_retriever import extract_risk_type, rerank_candidate
from app.rag import regulation_retriever as retriever
from app.rag.query_builder import build_search_query
from app.video_pipeline import collect_regulations


class CollapsePipelineTests(unittest.TestCase):
    def test_no_candidate_skips_vision_and_rag(self):
        with patch.object(pipeline, 'extract_frames', return_value=[Path('frame_0000.00.jpg')]), \
                patch.object(pipeline, 'analyze_image', return_value='{"workers":[],"hazards":[],"scene_description":"정상"}'), \
                patch('app.rag.collapse_verification.verify_windows') as vision, \
                patch.object(pipeline, 'search_regulations') as rag:
            result = pipeline.analyze_video('1_2collapse.mp4')
        vision.assert_not_called()
        rag.assert_not_called()
        self.assertEqual(result['decided_hazards'], [])

    def test_collapse_marker_uses_general_rag_without_fall_rules(self):
        risk, query = extract_risk_type('[RISK_TYPE=COLLAPSE] 구급용구 및 사고 대응')
        self.assertEqual(risk, 'COLLAPSE')
        self.assertNotIn('RISK_TYPE', query)
        result = rerank_candidate({'distance':0.2, 'collection':'osh_safety_rule', 'metadata':{}}, risk, query)
        self.assertIn('rerank_score', result)
        self.assertIn('COLLAPSE', VLM_SCHEMA['properties']['hazards']['items']['properties']['risk_type']['enum'])

    def test_collapse_retrieval_ignores_posture_and_does_not_fill_with_unrelated_work(self):
        query_a = build_search_query({'risk_type':'COLLAPSE','evidence':['바닥에 누워 있음']})
        query_b = build_search_query({'risk_type':'COLLAPSE','evidence':['직립 뒤 몸이 기울고 내려감']})
        self.assertEqual(query_a, query_b)
        first_aid = {'id':'first_aid','collection':'osh_safety_rule','distance':0.6,
                     'metadata':{'article':'제82조','article_title':'구급용구'},
                     'document':'부상자의 응급처치에 필요한 구급용구와 들것을 갖추어 둔다.'}
        unrelated = {'id':'demolition','collection':'osh_safety_rule','distance':0.01,
                     'metadata':{'article':'제384조','article_title':'해체작업 시 준수사항'},
                     'document':'해체작업 중 사고 시 응급처치 및 들것 사용'}
        specific = {'id':'confined','collection':'osh_safety_rule','distance':0.02,
                    'metadata':{'article':'제640조','article_title':'긴급 구조훈련'},
                    'document':'밀폐공간 구조훈련에서 응급처치 및 구급용구 사용'}
        with patch.object(retriever, 'embed_query', return_value=[0.0]), \
                patch.object(retriever, 'get_available_collections', return_value=['osh_safety_rule']), \
                patch.object(retriever, 'search_collection', return_value=[unrelated,specific]), \
                patch.object(retriever, 'fetch_priority_candidates', return_value=[first_aid]) as priority, \
                patch.object(retriever, 'fetch_serious_accident_priority_candidates', return_value=[]), \
                patch.object(retriever, 'fetch_annex_candidates', return_value=[]):
            results = retriever.search_regulations(query_a)
            self.assertEqual([r['id'] for r in results], ['first_aid'])
            priority.assert_called_once_with('COLLAPSE', [0.0])
            with patch.object(retriever, 'fetch_priority_candidates', return_value=[]):
                self.assertEqual(retriever.search_regulations(query_a), [])

    def test_collapse_references_are_not_reported_as_legal_violations(self):
        # A fall observation alone does not establish a specific legal violation.
        result = {'consolidated_hazards':[{'risk_type':'COLLAPSE','detected':True,'final_decision':'CONFIRMED'}],
                  'hazards':[{'risk_type':'COLLAPSE','regulations':[{'id':'reference'}]}]}
        self.assertEqual(collect_regulations(result), [])


if __name__ == '__main__':
    unittest.main()
