"""Bounded person-crop reviews; conflicting categorical observations stay pending."""
import hashlib
import os
import threading
import time
from functools import lru_cache
from pathlib import Path
from PIL import Image
from app.local import ollama_client as client
from app.rag.focused_observation import FIELDS, INSTRUCTIONS, observation_schema, interpret_observations, verify_risk

ROOT=Path(__file__).resolve().parents[2]
REVIEW_BATCH_SIZE=8
REVIEW_BUDGET_SECONDS=120.0
_MODEL=None
_MODEL_LOCK=threading.Lock()

def pending(result, reason):
    result=dict(result)
    result.update(detected=False, confirmation_eligible=False, conclusive=False, confidence='LOW',
                  evidence=reason, review_reason=reason)
    return result

@lru_cache(maxsize=128)
def _person_boxes(path, fingerprint):
    global _MODEL
    os.environ['YOLO_CONFIG_DIR']=str(ROOT/'pose_results/yolo_config')
    os.environ['YOLO_AUTOINSTALL']='false'
    os.environ['MPLCONFIGDIR']=str(ROOT/'pose_results/mpl_config')
    from ultralytics import YOLO
    with _MODEL_LOCK:
        if _MODEL is None:
            weights=ROOT/'models/yolo11s.pt'
            if not weights.is_file():raise FileNotFoundError('사람 검출 모델 파일 없음')
            _MODEL=YOLO(str(weights))
        with Image.open(path) as opened:
            picture=opened.convert('RGB')
        result=_MODEL.predict(picture,classes=[0],imgsz=640,conf=0.25,device='cpu',verbose=False)[0]
        boxes=tuple(sorted(tuple(int(v) for v in box) for box in result.boxes.xyxy.cpu().tolist()))
    return boxes

def box_area(box):
    return max(0,box[2]-box[0])*max(0,box[3]-box[1])


def near_duplicate(first, second):
    """A grouping hint, not proof of identity; distinct member views are retained."""
    intersection=max(0,min(first[2],second[2])-max(first[0],second[0]))*max(0,min(first[3],second[3])-max(first[1],second[1]))
    small=min(box_area(first),box_area(second))
    if not small:return False
    widths=[box[2]-box[0] for box in (first,second)]
    heights=[box[3]-box[1] for box in (first,second)]
    aligned=(abs(first[1]-second[1])<=0.1*min(heights)
        and abs((first[0]+first[2]-second[0]-second[2])/2)<=0.25*min(widths))
    return aligned and intersection/small>=0.9 and min(widths)/max(widths)>=0.65


def group_person_boxes(boxes):
    # Exact duplicate boxes have identical pixels. Near duplicates only share a group.
    unique={}
    for index,box in enumerate(boxes):unique.setdefault(tuple(box),[]).append(index)
    groups=[]
    for box in sorted(unique,key=lambda box:(-box_area(box),box)):
        group=next((group for group in groups if near_duplicate(group['representative'],box)),None)
        member={'box':box,'raw_indices':unique[box]}
        if group is None:groups.append({'representative':box,'members':[member]})
        else:group['members'].append(member)
    return sorted(groups,key=lambda group:group['representative'])


def person_crops(image_path):
    path=Path(image_path).resolve()
    fingerprint=hashlib.sha256(path.read_bytes()).hexdigest()
    raw_boxes=_person_boxes(str(path),fingerprint)
    directory=ROOT/'pose_results/review_crops'/fingerprint/'all_targets_v2'
    directory.mkdir(parents=True,exist_ok=True)
    with Image.open(path) as opened:picture=opened.convert('RGB')
    boxes=[];invalid=[];valid_raw_indices=[]
    for raw_index,raw in enumerate(raw_boxes):
        left,top,right,bottom=raw
        box=(max(0,min(picture.width,left)),max(0,min(picture.height,top)),
             max(0,min(picture.width,right)),max(0,min(picture.height,bottom)))
        if box_area(box):
            boxes.append(box);valid_raw_indices.append(raw_index)
        else:invalid.append(list(raw))
    groups=group_person_boxes(boxes)
    tasks=[]
    for index,group in enumerate(groups,1):
        for view,member in enumerate(group['members'],1):
            tasks.append({'target_id':f'person_{index}' if view==1 else f'person_{index}_view_{view}',
                'detection_group_id':f'person_{index}','person_box':list(member['box']),
                'is_representative':view==1,'source_detection_indices':[valid_raw_indices[i] for i in member['raw_indices']],
                'group_boxes':[list(item['box']) for item in group['members']]})
    # Inspect representatives across the whole image before alternate near-duplicate views.
    # Size is a visibility scheduling hint, never a danger score or a total-count limit.
    tasks.sort(key=lambda item:(not item['is_representative'],-box_area(item['person_box']),tuple(item['person_box'])))
    crops=[]
    for task in tasks:
        left,top,right,bottom=task['person_box']
        pad_x=max(2,int((right-left)*0.05));pad_y=max(2,int((bottom-top)*0.05))
        box=(max(0,left-pad_x),max(0,top-pad_y),min(picture.width,right+pad_x),min(picture.height,bottom+pad_y))
        crop=directory/(task['target_id']+f'_{left}_{top}_{right}_{bottom}.jpg')
        if not crop.is_file():picture.crop(box).save(crop,quality=95)
        crops.append({**task,'crop_box':list(box),
            'normalized_person_box':[round(left*1000/picture.width),round(top*1000/picture.height),round(right*1000/picture.width),round(bottom*1000/picture.height)],
            'path':str(crop)})
    return {'crops':crops,'detected_people':len(groups),'raw_detection_count':len(raw_boxes),
        'exact_duplicates_removed':len(boxes)-len({tuple(box) for box in boxes}),
        'detection_group_count':len(groups),'grouping_ambiguous':any(len(group['members'])>1 for group in groups),
        'invalid_detection_boxes':invalid,'total_crop_targets':len(crops),'batch_size':REVIEW_BATCH_SIZE,
        'coverage_limited':bool(invalid),'image_sha256':fingerprint}


def inspect_crop(image_path, crop, risk):
    full_schema=observation_schema(risk)
    observations=full_schema['properties']['observations']
    observations.update(minItems=1,maxItems=1)
    schema={'type':'object','properties':{'observations':observations},
        'required':['observations'],'additionalProperties':False}
    if risk=='NO_HELMET':
        prompt=('This image is a crop of one detected person. Assess ONLY the person whose body is centered; '
            'ignore other people at the edges. Return exactly one observation. '
            'Use UNKNOWN when that target cannot be assessed. '+INSTRUCTIONS[risk])
        pictures=client.prepare_image_base64(Path(crop['path']))
    else:
        prompt=('Two images are provided. The FIRST is the original scene for actual support height. '
            'The SECOND is a crop of one detected person. Assess ONLY the person centered in the SECOND image. '
            'The target box in the original scene normalized to 0..1000 is '+str(crop.get('normalized_person_box',crop['person_box']))+'. '
            'Return exactly one observation for that same target. Use UNKNOWN if attachment or support cannot be seen. '+INSTRUCTIONS[risk])
        pictures=[client.prepare_image_base64(Path(image_path)),client.prepare_image_base64(Path(crop['path']))]
    response=client.request_ollama(Path(image_path),pictures,prompt,1,schema=schema)
    if not response.get('done') or response.get('done_reason')=='length':raise ValueError('확대 관찰 미완료')
    raw=client.parse_json_response(response['response'])
    if set(raw)!={'observations'} or len(raw['observations'])!=1:raise ValueError('확대 대상 인물 대응 불명확')
    # Scene applicability comes from the full scene, not a face crop or a test label.
    return interpret_observations(risk,{'context':crop.get('scene_context','UNCERTAIN'), 'observations':raw['observations']})


def review_candidate(image_path, risk, candidate=None, *, whole_verifier=None, cropper=None, crop_verifier=None, budget_seconds=REVIEW_BUDGET_SECONDS):
    started=time.monotonic()
    candidate=candidate or {}
    context=candidate.get('review_context',{})
    conflicts=list(context.get('conflicts',[]))
    whole=(whole_verifier or verify_risk)(image_path,risk)
    result=dict(whole)
    result['whole_frame_observation']=dict(whole)
    result['verification_conflicts']=conflicts
    if risk not in {'NO_HELMET','UNFASTENED_SAFETY_HARNESS'}:
        return pending(result,'관찰 충돌이 남아 검토 필요') if conflicts else result
    try:
        regions=(cropper or person_crops)(image_path)
        result['spatial_review']={key:value for key,value in regions.items() if key!='crops'}
        checks=[]
        batch_size=regions.get('batch_size',REVIEW_BATCH_SIZE)
        if type(batch_size) is not int or batch_size<1:raise ValueError('확대 검토 묶음 크기 오류')
        for offset in range(0,len(regions['crops']),batch_size):
            for crop in regions['crops'][offset:offset+batch_size]:
                crop={**crop,'batch_index':offset//batch_size+1,
                    'scene_context':whole.get('observation_response',{}).get('context',context.get('context','UNCERTAIN'))}
                if budget_seconds is not None and time.monotonic()-started>=budget_seconds:
                    checks.append({**crop,'status':'PENDING','reason':'REVIEW_TIME_BUDGET'})
                    continue
                try:
                    checked=(crop_verifier or inspect_crop)(image_path,crop,risk)
                    checks.append({**crop,'status':'SUCCESS','result':checked})
                except Exception as error:
                    checks.append({**crop,'status':'ERROR','error':str(error)})
        result['spatial_review'].update(checks=checks,
            reviewed_targets=sum(check['status']=='SUCCESS' for check in checks),
            pending_target_ids=[check['target_id'] for check in checks if check['status']!='SUCCESS'],
            unresolved_target_ids=[check['target_id'] for check in checks if check.get('status')=='SUCCESS' and not check['result'].get('conclusive')],
            batch_count=(len(regions['crops'])+batch_size-1)//batch_size,
            budget_seconds=budget_seconds,elapsed_seconds=round(time.monotonic()-started,3))
        if any(check['status']!='SUCCESS' for check in checks):
            result['spatial_review']['coverage_limited']=True
        positives=[check for check in checks if check.get('result',{}).get('confirmation_eligible')]
        result['spatial_review']['positive_target_ids']=[check['target_id'] for check in positives]
        all_negative=bool(checks) and all(check.get('status')=='SUCCESS' and
            check['result'].get('conclusive') and not check['result'].get('detected') for check in checks)
        expected=max(context.get('worker_count',0),context.get('extra_person_count',0))
        coverage=(not result['spatial_review'].get('coverage_limited')
            and not regions.get('grouping_ambiguous') and regions['detected_people']>=expected)
        result['spatial_review']['coverage_sufficient']=coverage
        if whole.get('confirmation_eligible') and all_negative:
            conflicts.append('전체 이미지와 확대 관찰의 보호구 판단이 서로 모순됨')
        if context.get('prior_all_wearing') and (positives or whole.get('confirmation_eligible')):
            conflicts.append('앞선 두 관찰의 착용 판단과 현재 양성 판단이 충돌함')
        if positives and whole.get('conclusive') and not whole.get('detected'):
            conflicts.append('전체 이미지의 부정 판단과 확대 관찰의 양성 판단이 충돌함')
        if (all_negative and coverage and whole.get('conclusive') and not whole.get('detected')
                and context.get('context')=='INDUSTRIAL'
                and whole.get('observation_response',{}).get('context')=='INDUSTRIAL'
                and (not conflicts or risk=='NO_HELMET')):
            result['initial_verification_conflicts']=conflicts
            result['verification_conflicts']=[]
            result['conflicts_resolved']='NEGATIVE_SPATIAL_COVERAGE'
            return result
        if conflicts:
            result['verification_conflicts']=conflicts
            return pending(result,'상충하는 관찰 또는 동일 인물 대응 확인이 남아 검토 필요')
        if positives:
            checked=positives[0]['result']
            result.update({key:checked[key] for key in ['detected','confirmation_eligible','conclusive',
                'confidence','visual_evidence','evidence','positive_observations','observation_response']})
            result['worker_ids']=[]  # Spatial target ID is not an initial VLM worker ID.
            result['spatial_target']=positives[0]['target_id']
            result['spatial_target_box']=positives[0]['person_box']
            return result
        if all_negative and coverage and whole.get('conclusive') and not whole.get('detected'):
            return result
        return pending(result,'가시성·인물 검출 범위·확대 관찰에 불확실성이 남아 검토 필요')
    except Exception as error:
        result['spatial_review']={'status':'ERROR','error':str(error)}
        return pending(result,'대상 인물 확대 검증 실패로 검토 유지')
