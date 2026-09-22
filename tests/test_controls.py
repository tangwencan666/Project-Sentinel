import ast
from pathlib import Path
import pytest
from sentinel.patching import validate, propose

@pytest.mark.parametrize('source',[
    'import os\ndef total(price,quantity,discount=0): return 1',
    'def total(price,quantity,discount=0): return open("/etc/passwd").read()',
    'def total(price,quantity,discount=0): return (1).__class__',
    'def total(price,quantity,discount=0):\n while True: pass',
    'def total(price,quantity,discount=0): return eval("1")',
    'def total(price,quantity,discount=0): return 1\nround(1)',
])
def test_reject_unsafe_patch(source):
    with pytest.raises(ValueError): validate(source)

def test_baseline_reproduces_and_candidate_passes():
    source=Path('/app/services/pricing.py').read_text()
    candidate=source.replace('(1 - discount)','(1 - (discount if discount is not None else 0))')
    result=propose(candidate,'test-controls')
    assert result['baseline_test']['exit_code']==1
    assert result['candidate_test']['exit_code']==0
    assert result['validated']
    assert '+    return' in result['diff']

def test_investigator_has_no_truth_capability():
    for name in ('agent.py','evidence.py'):
        source=Path('/app/sentinel',name).read_text()
        tree=ast.parse(source)
        assert not any(isinstance(n,ast.ImportFrom) and n.module and 'scenarios' in n.module for n in ast.walk(tree))
        assert 'ground_truth_root_cause' not in source
    source=Path('/app/sentinel/evidence.py').read_text()
    assert "redis.keys" not in source
    assert "redis.scan" not in source
    assert "Path('/app/services/pricing.py')" in source
