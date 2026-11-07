"""Deterministic per-analysis review order; never changes a hazard decision."""
from copy import deepcopy

REVIEW_ORDER_POLICY = 'risk_proximity_v1'
RISK_GROUP = {'COLLAPSE':1,'FALL_HAZARD':2,'UNFASTENED_SAFETY_HARNESS':2,
              'NO_HELMET':3,'BLOCKED_PATH':3}
PROXIMITY_ORDER = {'IMMEDIATE':0,'NEAR':1,'UNCERTAIN':1,'NOT_NEAR':2}
GROUP_REASON = {1:'쓰러짐 후보의 추가 확인 우선',2:'추락·안전대 관련 위험의 추가 확인 우선',
                3:'보호구·통행 경로 위험 확인'}
PROXIMITY_REASON = {'IMMEDIATE':'즉시 노출 관찰', 'NEAR':'근접 노출 관찰',
                    'UNCERTAIN':'근접도 불명확을 낮은 위험으로 취급하지 않음', 'NOT_NEAR':'멀리 떨어진 관계로 관찰됨'}
ORDER_FIELDS = ('review_order','review_order_reason','review_group','review_proximity')

def review_proximity(hazard, frames):
    values=[]
    if hazard.get('proximity') in PROXIMITY_ORDER:values.append(hazard['proximity'])
    evidence=set(hazard.get('evidence_frames') or [])
    for frame in frames:
        if evidence and frame.get('frame') not in evidence:continue
        for item in frame.get('hazards',[]):
            if item.get('risk_type')==hazard.get('risk_type') and item.get('detected'):
                values.append(item.get('proximity') if item.get('proximity') in PROXIMITY_ORDER else 'UNCERTAIN')
    # NEAR and UNCERTAIN have equal queue priority; prefer an explicit NEAR label for explanation.
    return min(values,key=lambda value:(PROXIMITY_ORDER[value],value=='UNCERTAIN')) if values else 'UNCERTAIN'

def attach_review_order(hazards, frames=None):
    """Return annotated records and an ordered index queue, preserving every original record."""
    records=deepcopy(hazards)
    pending=[]
    for index,record in enumerate(records):
        for key in ORDER_FIELDS:record.pop(key,None)
        if record.get('final_decision')!='REVIEW_REQUIRED':continue
        group=RISK_GROUP.get(record.get('risk_type'),2)
        proximity=review_proximity(record,frames or [])
        pending.append((group,PROXIMITY_ORDER[proximity],index,proximity))
    pending.sort(key=lambda item:item[:3])
    queue=[]
    for order,(group,_,index,proximity) in enumerate(pending,1):
        record=records[index]
        reason=(GROUP_REASON[group] if record.get('risk_type') in RISK_GROUP else '위험 종류가 불명확하여 추가 확인 필요')+'; '+PROXIMITY_REASON[proximity]
        record.update(review_order=order,review_order_reason=reason,review_group=group,review_proximity=proximity)
        queue.append({'review_order':order,'hazard_index':index,'risk_type':record.get('risk_type'),
                      'review_group':group,'review_proximity':proximity,'review_order_reason':reason})
    return records,queue
