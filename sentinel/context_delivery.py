"""Account for actual model input; detail pages contain complete raw span objects."""
import json

def provider_messages(system,context,limit=90000):
    """Measure the exact nested JSON envelope used by provider.complete's guard."""
    # Copy only evictable collections; pinned structures are never edited or sliced.
    context={**context,'P2':list(context.get('P2',[])),'P3':list(context.get('P3',[]))}
    def build():
        return [{'role':'system','content':system},
                {'role':'user','content':json.dumps(context,ensure_ascii=False)}]
    messages=build()
    while len(json.dumps(messages,ensure_ascii=False))>limit and (context['P3'] or context['P2']):
        (context['P3'] or context['P2']).pop(0)
        messages=build()
    if len(json.dumps(messages,ensure_ascii=False))>limit:
        raise ValueError('PINNED_CONTEXT_OVERFLOW: exact provider message envelope exceeds ceiling')
    return messages,context

def detail_page(traces,offset=0,limit=8,max_chars=12000):
    result=[]
    for trace in traces:
        spans=trace.get('spans',[]);selected=[];size=0
        for span in spans[offset:offset+limit]:
            cost=len(json.dumps(span,ensure_ascii=False))
            if selected and size+cost>max_chars: break
            if cost>max_chars: raise ValueError('DETAIL_OBJECT_TOO_LARGE: request a different span; no partial JSON was returned')
            selected.append(span);size+=cost
        end=offset+len(selected)
        result.append({**{k:v for k,v in trace.items() if k!='spans'},'spans':selected,
            'pagination':{'offset':offset,'returned_spans':len(selected),'total_spans':len(spans),
                          'next_offset':end if end<len(spans) else None},'representation':'raw_span_page'})
    return result

def visible_reads(context,provider_call_id):
    reads={}
    def add(eid,kind,content,representation):
        if not eid: return
        entry={'kind':kind,'read':True,'representation':representation,'provider_call_id':provider_call_id}
        if isinstance(content,dict) and all(k in content for k in ('path','start_line','end_line','source')):
            entry.update({k:content[k] for k in ('path','start_line','end_line')})
        if isinstance(content,dict) and all(k in content for k in ('file','line_range','snippet')):
            entry.update(path=content['file'],start_line=content['line_range'][0],end_line=content['line_range'][1])
        if isinstance(content,list) and kind=='get_trace_detail':
            entry['trace_pages']=[{'trace_id':t.get('traceID'),'span_ids':[s['spanID'] for s in t.get('spans',[])]} for t in content]
        reads[eid]={**reads.get(eid,{}),**entry}
    for item in context.get('evidence',{}).get('items',[]):
        add(item['id'],item['kind'],None if item.get('truncated') else item.get('observations'),'summary')
    for signal in (context.get('triage') or {}).get('signals',[]):
        if signal.get('observations'):
            for eid in signal.get('evidence_ids',[]): add(eid,'triage_observation',None,'triage_summary')
    for eid,item in context.get('P1',{}).get('critical_evidence',{}).items():
        add(eid,item['kind'],item.get('observations'),'pinned_summary')
    for recent in context.get('P2',[]):
        output=recent['output'];kind=recent['tool']
        if output.get('error'): continue
        if output.get('compressed'):
            for item in output.get('result',[]):
                add(item['id'],item['kind'],None if item.get('truncated') else item.get('observations'),'summary')
        else:
            for eid in output.get('evidence_ids',[]): add(eid,kind,output.get('result'),'detail')
        if kind=='read_evidence' and isinstance(output.get('result'),dict):
            page=output['result'];add(page.get('evidence_id'),kind,None,page.get('representation','character_page'))
    return reads


def raw_evidence_page(payload,offset=0,length=4,max_chars=12000):
    """Whole JSON records with paths: reversible paging, no summary and no string cuts."""
    objects=[]
    def split(value,path):
        if len(json.dumps(value,ensure_ascii=False,default=str))<=8000:
            objects.append({'path':path,'value':value});return
        if isinstance(value,dict):
            for key,child in value.items(): split(child,path+[key])
        elif isinstance(value,list):
            for index,child in enumerate(value): split(child,path+[index])
        else:
            raise ValueError('DETAIL_OBJECT_TOO_LARGE: atomic value exceeds 8000 characters; nothing truncated')
    split(payload,[]);selected=[]
    for item in objects[offset:offset+length]:
        if selected and len(json.dumps(selected+[item],ensure_ascii=False,default=str))>max_chars: break
        selected.append(item)
    end=offset+len(selected)
    return {'records':selected,'offset':offset,'next_offset':end if end<len(objects) else None,
            'total_records':len(objects),'representation':'raw_json_objects','pagination_unit':'objects',
            'reassembly':'Each record.value belongs at record.path in the original payload; paths are keys or array indexes.'}
