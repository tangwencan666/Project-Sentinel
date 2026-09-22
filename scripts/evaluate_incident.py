"""Human evaluation export, deliberately outside the investigator tool surface.
No fabricated automatic root-cause score. Judge evidence and diagnosis manually.
"""
import argparse
import json
from pathlib import Path
import sys
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sentinel.scenarios import REGISTRY

parser=argparse.ArgumentParser()
parser.add_argument('incident_id')
parser.add_argument('scenario_id',choices=REGISTRY)
parser.add_argument('--output',default='docs/evaluation.json')
args=parser.parse_args()
with urllib.request.urlopen('http://localhost:18082/api/incidents/'+args.incident_id) as response:
    incident=json.load(response)
scenario=REGISTRY[args.scenario_id]
result={'incident_id':args.incident_id,'ground_truth':scenario,'actual_report':incident.get('report'),'tool_audit':incident['steps'],'runtime_verification':incident.get('verification'),'human_score':None,'rubric':{'root_cause': '0=wrong / 1=partially correct / 2=mechanism and affected service correct','evidence':'0=unsupported / 1=single source / 2=independent cross-check','repair':'0=not tested / 1=tests pass / 2=live reproducer passes after patch'},'note':'Evaluation output must never be supplied to the investigating model.'}
Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(args.output)
