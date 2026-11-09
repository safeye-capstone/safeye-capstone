"""Risk-specific observations; code derives evidence codes from explicit visual answers."""
from pathlib import Path
from app.local import ollama_client as client

YES_NO = ['YES', 'NO', 'UNKNOWN']
FIELDS = {
 'NO_HELMET': {'head_visible': YES_NO, 'helmet': ['WEARING','NOT_WEARING','UNKNOWN']},
 'UNFASTENED_SAFETY_HARNESS': {'elevated_support':YES_NO,'torso_visible':YES_NO,
     'harness':['CONNECTED','NOT_WEARING','DISCONNECTED','UNKNOWN'],'hook_visible':YES_NO},
 'FALL_HAZARD': {'edge_or_opening':YES_NO,'person_exposed':YES_NO,'protection_missing':YES_NO},
 'BLOCKED_PATH': {'passage_visible':YES_NO,'passage_blocked':YES_NO},
}
INSTRUCTIONS = {
 'NO_HELMET': 'Inspect every visible head separately. A protective hard hat is WEARING; hair or a fabric cap is NOT_WEARING. head_visible=YES only if the head is clear enough to assess. Occlusion, blur or tiny heads mean UNKNOWN. Do not copy equipment between people.',
 'UNFASTENED_SAFETY_HARNESS': 'CONNECTED requires a visibly attached hook and hook_visible=YES; a hidden attachment is UNKNOWN. elevated_support=YES only if the person actually works on a raised support, not ordinary ground or beside tall structures. torso_visible=YES only if equipment can be assessed. NOT_WEARING requires a clearly visible torso with no fall-arrest harness. DISCONNECTED requires a directly visible unattached hook: hook_visible=YES. A hidden attachment is UNKNOWN. Ordinary clothes or bags are not harnesses.',
 'FALL_HAZARD': 'Inspect each person and their actual fall point. edge_or_opening=YES only for a nearby real drop or opening, not background scaffolding or uneven ground. person_exposed=YES only if that same person is exposed to that drop. protection_missing=YES only if the relevant barrier/cover is visibly missing. If unsure use UNKNOWN.',
 'BLOCKED_PATH': 'Return route_box and obstacle_box in original-image coordinates normalized to 0..1000 as [left,top,right,bottom]; use [0,0,0,0] if not identifiable. obstacle_kind must describe a physical obstruction, not a warning sign or merely a restricted area. Boxes must mark the actual passage and obstructing object, never the entire image. Inspect identifiable pedestrian passages, not arbitrary storage areas. passage_visible=YES only for an identifiable passage. passage_blocked=YES only if objects actually obstruct that same passage. Materials beside a route do not count. If unsure use UNKNOWN.',
}

def observation_schema(risk):
    props={key:{'type':'string','enum':values} for key,values in FIELDS[risk].items()}
    if risk=='BLOCKED_PATH':
        props.update(route_box={'type':'array','items':{'type':'integer','minimum':0,'maximum':1000},'minItems':4,'maxItems':4},
                     obstacle_box={'type':'array','items':{'type':'integer','minimum':0,'maximum':1000},'minItems':4,'maxItems':4},
                     obstacle_kind={'type':'string','enum':['MATERIAL','EQUIPMENT','FENCE','PERSON','SIGN','OTHER','UNKNOWN']})
    return {'type':'object','properties':{
      'context':{'type':'string','enum':['INDUSTRIAL','NON_INDUSTRIAL','UNCERTAIN']},
      'observations':{'type':'array','maxItems':16,'items':{'type':'object','properties':props,
         'required':list(props),'additionalProperties':False}}},
      'required':['context','observations'],'additionalProperties':False}

def interpret_observations(risk, raw):
    if not isinstance(raw,dict) or set(raw)!={'context','observations'}:
        raise ValueError('관찰 응답 구조 오류')
    context=raw['context']; items=raw['observations']
    if context not in {'INDUSTRIAL','NON_INDUSTRIAL','UNCERTAIN'} or not isinstance(items,list) or len(items)>16:
        raise ValueError('관찰 맥락 또는 배열 오류')
    positives=[]; negatives=[]
    for index,item in enumerate(items,1):
        allowed=set(FIELDS[risk]) | ({'route_box','obstacle_box','obstacle_kind'} if risk=='BLOCKED_PATH' else set())
        if not isinstance(item,dict) or not set(FIELDS[risk]).issubset(item) or not set(item).issubset(allowed) or any(item[k] not in v for k,v in FIELDS[risk].items()):
            raise ValueError('관찰 필드 또는 값 오류')
        codes=[]; negative=False
        if risk=='NO_HELMET':
            if item['head_visible']=='YES' and item['helmet']=='NOT_WEARING':codes=['HEAD_VISIBLE','HELMET_ABSENT']
            negative=item['head_visible']=='YES' and item['helmet']=='WEARING'
        elif risk=='UNFASTENED_SAFETY_HARNESS':
            if item['elevated_support']=='YES' and item['torso_visible']=='YES':
                if item['harness']=='NOT_WEARING':codes=['ELEVATED_SUPPORT_VISIBLE','HARNESS_ABSENT']
                elif item['harness']=='DISCONNECTED' and item['hook_visible']=='YES':codes=['ELEVATED_SUPPORT_VISIBLE','ANCHOR_DISCONNECTED']
            negative=item['elevated_support']=='NO' or (item['harness']=='CONNECTED' and item['hook_visible']=='YES')
        elif risk=='FALL_HAZARD':
            if all(v=='YES' for v in item.values()):codes=['EDGE_OR_OPENING_VISIBLE','PERSON_EXPOSED','PROTECTION_MISSING']
            negative=any(v=='NO' for v in item.values())
        else:
            if all(item[k]=='YES' for k in FIELDS[risk]) and passage_geometry_valid(item):codes=['PASSAGE_VISIBLE','PASSAGE_BLOCKED']
            negative=any(item[k]=='NO' for k in FIELDS[risk])
        if codes:positives.append({'worker_id':index,'visual_evidence':codes,'observation':item})
        negatives.append(negative)
    eligible=context=='INDUSTRIAL' and bool(positives)
    conclusive=eligible or context=='NON_INDUSTRIAL' or (context=='INDUSTRIAL' and bool(items) and all(negatives))
    selected=positives[0] if eligible else {}
    messages={'NO_HELMET':'머리가 보이며 안전모 미착용이 관찰됨',
       'UNFASTENED_SAFETY_HARNESS':'높은 작업 위치에서 안전대 미착용 또는 보이는 고리의 미체결이 관찰됨',
       'FALL_HAZARD':'동일 사람의 가장자리·개구부 노출과 방호 부족이 관찰됨',
       'BLOCKED_PATH':'식별된 통행 경로의 차단이 관찰됨'}
    return {'detected':eligible,'confirmation_eligible':eligible,'conclusive':conclusive,
      'confidence':'MEDIUM' if eligible else 'LOW','candidate_source':'vlm',
      'worker_ids':[selected['worker_id']] if eligible and risk!='BLOCKED_PATH' else [],
      'visual_evidence':selected.get('visual_evidence',[]),
      'evidence':messages[risk] if eligible else '위험이 직접 확인되지 않음' if conclusive else '가림·맥락·관찰 항목의 불확실성으로 확인 보류',
      'observation_method':'focused_fields_v1','observation_response':raw,
      'positive_observations':positives if eligible else []}

def verify_risk(image_path: Path, risk: str):
    prompt=('Inspect only this image for '+risk+'. Return the requested JSON only. '
      'Classify INDUSTRIAL only for an actual construction, manufacturing, maintenance or logistics activity/environment; '
      'sports or ordinary daily activities are NON_INDUSTRIAL. Use UNCERTAIN when unclear. '
      'Each observation must concern one person or one passage. Do not combine facts from different people. '
      'Answer only visible facts, not hypothetical future risks. '+INSTRUCTIONS[risk])
    data=client.request_ollama(Path(image_path),client.prepare_image_base64(Path(image_path)),prompt,1,schema=observation_schema(risk))
    if not data.get('done') or data.get('done_reason')=='length' or not data.get('response'):
        raise ValueError('관찰 응답 미완료')
    return interpret_observations(risk,client.parse_json_response(data['response']))


def collect_ppe_candidates(image_path):
    fields = {'head_visible':YES_NO,'helmet':['WEARING','NOT_WEARING','UNKNOWN'],
        'elevated_support':YES_NO,'harness':['CONNECTED','NOT_WEARING','DISCONNECTED','UNKNOWN','NOT_APPLICABLE']}
    schema={'type':'object','properties':{
        'context':{'type':'string','enum':['INDUSTRIAL','NON_INDUSTRIAL','UNCERTAIN']},
        'people':{'type':'array','maxItems':16,'items':{'type':'object','properties':{
            key:{'type':'string','enum':values} for key,values in fields.items()},
            'required':list(fields),'additionalProperties':False}}},
        'required':['context','people'],'additionalProperties':False}
    prompt=('Inspect actual visible people for protective equipment, one person per item. '
        'Classify actual industrial work/environment versus non-industrial daily/sports activity; use UNCERTAIN when unclear. '
        'Do not copy one person to others. head_visible=YES only if head is assessable. '
        'helmet WEARING requires an actual protective hard hat; bare hair or an ordinary cap is NOT_WEARING. '
        'Occluded or tiny heads are UNKNOWN. elevated_support=YES requires this person actually on a raised work support, '
        'not merely a background structure. Harness DISCONNECTED requires a directly visible unattached hook; '
        'hidden connection means UNKNOWN. NOT_WEARING requires a sufficiently visible torso with no harness. '
        'Return only JSON; report uncertainty instead of guessing.')
    path=Path(image_path)
    response=client.request_ollama(path,client.prepare_image_base64(path),prompt,1,schema=schema)
    if not response.get('done') or response.get('done_reason')=='length':raise ValueError('추가 관찰 미완료')
    raw=client.parse_json_response(response['response'])
    if set(raw)!={'context','people'} or raw['context'] not in {'INDUSTRIAL','NON_INDUSTRIAL','UNCERTAIN'} or not isinstance(raw['people'],list) or len(raw['people'])>16:
        raise ValueError('추가 관찰 구조 오류')
    for person in raw['people']:
        if not isinstance(person,dict) or set(person)!=set(fields) or any(person[k] not in v for k,v in fields.items()):
            raise ValueError('추가 관찰 필드 오류')
    return raw


def prepare_frame_candidates(image_path, raw_analysis, *, observer=None):
    from app.rag.query_builder import normalize_vlm_analysis
    from copy import deepcopy
    analysis=normalize_vlm_analysis(deepcopy(raw_analysis))
    # A visible lying/losing-balance posture is a candidate, never a final fall verdict.
    unstable=[w.get('worker_id') for w in analysis.get('workers',[])
              if w.get('posture') in {'LYING_OR_ROLLING','LOSING_BALANCE'}]
    if unstable and not any(h['risk_type']=='COLLAPSE' and h.get('detected') for h in analysis['hazards']):
        analysis['hazards'].append({'risk_type':'COLLAPSE','detected':True,'confidence':'LOW',
            'candidate_source':'posture_supplement','worker_ids':unstable,'visual_evidence':[],
            'evidence':'누움 또는 실제 균형 상실 자세가 관찰되어 연속 영상 확인 필요',
            'proximity':'UNCERTAIN','confirmation_eligible':False,
            'confirmation_missing':['연속 영상의 자세·하강·유지시간 검증 필요']})
    if analysis.get('scene_context',{}).get('category')=='NON_INDUSTRIAL':
        analysis['ppe_candidate_observation']={'status':'NOT_APPLICABLE','reason':'NON_INDUSTRIAL'}
        return attach_review_contexts(analysis)
    try:
        observed=(observer or collect_ppe_candidates)(image_path)
        analysis['ppe_candidate_observation']=observed
        if observed['context']=='NON_INDUSTRIAL':
            return attach_review_contexts(analysis)
        risks=set()
        elevated=any(w.get('work_level')=='ELEVATED' for w in analysis.get('workers',[]))
        for person in observed['people']:
            # Candidate preservation is intentionally weaker than confirmation.
            if person['helmet']=='NOT_WEARING':risks.add('NO_HELMET')
            if person['harness'] in {'NOT_WEARING','DISCONNECTED'} and (
                    person['elevated_support']=='YES' or (person['elevated_support']=='UNKNOWN' and elevated)):
                risks.add('UNFASTENED_SAFETY_HARNESS')
        workers=analysis.get('workers',[])
        if workers and observed['people'] and len(workers)!=len(observed['people']):
            risks.add('NO_HELMET')  # Different person coverage needs checking, not a violation verdict.
        for risk in sorted(risks):
            if any(h['risk_type']==risk and h.get('detected') for h in analysis['hazards']):continue
            analysis['hazards'].append({'risk_type':risk,'detected':True,'confidence':'LOW',
                'candidate_source':'focused_candidate','worker_ids':[],'visual_evidence':[],
                'evidence':'불완전·상충 보호구 관찰 또는 사람 관찰 범위 차이로 추가 확인 필요','proximity':'UNCERTAIN',
                'confirmation_eligible':False,'confirmation_missing':['위험별 직접 관찰 재검증 필요']})
    except Exception as error:
        analysis['ppe_candidate_observation']={'status':'ERROR','error':str(error)}
    return attach_review_contexts(analysis)


def analyze_candidates(image_path, analyzer):
    """Keep valid structured observations as pending candidates after language-only failure."""
    from copy import deepcopy
    import json
    try:
        return json.loads(analyzer(image_path))
    except client.AnalysisLanguageError as error:
        raw=deepcopy(error.analysis)
        raw['language_status']='FAILED'
        raw['language_error']=str(error)
        raw['scene_description']='설명 번역이 완료되지 않아 구조화된 관찰을 후보로만 보존했습니다.'
        for worker in raw.get('workers',[]):
            worker['position']='위치 설명 확인 필요'
            worker['observations']=['구조화된 보호구·자세 관찰은 별도 검증 필요']
        for hazard in raw.get('hazards',[]):
            hazard['evidence']='구조화된 관찰에서 생성된 검토 후보'
            if hazard.get('risk_type')!='COLLAPSE':hazard['confidence']='LOW'
        return raw


def build_review_context(analysis, risk, candidate=None):
    """Frame observations are not identity matches across independent VLM responses."""
    workers=analysis.get('workers',[])
    extra=analysis.get('ppe_candidate_observation',{})
    people=extra.get('people',[])
    conflicts=[]
    prior_all_wearing=False
    if risk=='NO_HELMET':
        primary_wearing=bool(workers) and all(w.get('helmet')=='WEARING' for w in workers)
        extra_wearing=bool(people) and all(w.get('head_visible')=='YES' and w.get('helmet')=='WEARING' for w in people)
        prior_all_wearing=primary_wearing and extra_wearing and len(workers)==len(people)
        if prior_all_wearing and candidate and candidate.get('candidate_source')=='vlm':
            conflicts.append('사람 관찰은 모두 착용이나 위험 후보는 미착용으로 서로 모순됨')
    elif risk=='UNFASTENED_SAFETY_HARNESS':
        if any(w.get('work_level')=='ELEVATED' and w.get('harness')=='CONNECTED' for w in workers) and any(
                w.get('harness') in {'DISCONNECTED','NOT_WEARING'} for w in people):
            conflicts.append('높이·안전대 관찰이 서로 다르며 동일 인물 대응이 확인되지 않음')
        if workers and all(w.get('work_level')=='GROUND' for w in workers) and any(w.get('elevated_support')=='YES' for w in people):
            conflicts.append('지상 작업 관찰과 높은 작업 지지면 관찰이 서로 모순됨')
    category=analysis.get('scene_context',{}).get('category','UNCERTAIN')
    if {category,extra.get('context')}=={'INDUSTRIAL','NON_INDUSTRIAL'}:
        conflicts.append('산업 작업 적용 맥락이 서로 모순됨')
    return {'context':category,'conflicts':conflicts,'prior_all_wearing':prior_all_wearing,
        'worker_count':len(workers),'extra_person_count':len(people)}


def passage_geometry_valid(item):
    def valid(box):
        return (isinstance(box,list) and len(box)==4 and all(type(v) is int and 0<=v<=1000 for v in box)
            and box[0]<box[2] and box[1]<box[3] and box!=[0,0,1000,1000])
    route=item.get('route_box');obstacle=item.get('obstacle_box')
    if not valid(route) or not valid(obstacle) or item.get('obstacle_kind') not in {'MATERIAL','EQUIPMENT','FENCE','PERSON','OTHER'}:
        return False
    return max(route[0],obstacle[0])<min(route[2],obstacle[2]) and max(route[1],obstacle[1])<min(route[3],obstacle[3])


def attach_review_contexts(analysis):
    for hazard in analysis.get('hazards',[]):
        if not hazard.get('detected') or hazard.get('risk_type') not in FIELDS:continue
        context=build_review_context(analysis,hazard['risk_type'],hazard)
        hazard['review_context']=context
        if context['conflicts']:
            hazard['observation_conflict_required']=True
            hazard['confirmation_eligible']=False
            hazard['confirmation_missing']=list(hazard.get('confirmation_missing',[]))+context['conflicts']
    return analysis
