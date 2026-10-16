"""Synthetic fixtures only: no downloaded patches, model calls or data ingestion."""
import math
from dataclasses import replace
import numpy as np
import pytest
from lag_audit.campaign import Runner,PRIMARY
from lag_audit.engine import Proposal,Job,Policy,replay
from lag_audit.theory import audit_instance
from lag_audit.thresholds import Threshold
from test_data_and_empirical import fixture_rows

def fixture():
    rows=fixture_rows();split={r['instance_id']:i//4 for i,r in enumerate(rows)}
    return rows,split

def test_missing_records_do_not_shift_common_split():
    rows,split=fixture();runner=Runner(rows[:4]+rows[5:],split)
    assert len(runner.blocks[1])==3
    assert {r['id'] for r in runner.blocks[2]}=={r['id'] for r in rows[8:12]}

def test_admitted_only_history_contains_no_rejected_labels():
    rows,split=fixture();runner=Runner(rows,split)
    s={**PRIMARY,'reservation':2.,'budget':3.,'workers':2,'feedback':'admitted_only','queue_mode':'strict'}
    available=set(r['id'] for r in runner.warmup)
    for row,record in runner.episodes(s,['zcl_committed']):
        assert set(record['training_ids'])==available
        assert not available.intersection(record['test_ids'])
        available.update(record['admitted'])

def test_future_mutation_does_not_change_earlier_campaign():
    rows,split=fixture();s={**PRIMARY,'reservation':2.,'budget':3.,'feedback':'admitted_only'}
    a=list(Runner(rows,split).episodes(s,['zcl_committed','fixed_history']))
    changed=[{**r,'resolved':1-r['resolved'],'actual_cost':1.5} if split[r['instance_id']]==9 else dict(r) for r in rows]
    b=list(Runner(changed,split).episodes(s,['zcl_committed','fixed_history']))
    assert [r for r in a if r[0]['block']<9]==[r for r in b if r[0]['block']<9]

def test_tuning_uses_deadline_endpoint(monkeypatch):
    import lag_audit.empirical as module
    from types import SimpleNamespace
    calls=[]
    def stub(*args,**kwargs):
        calls.append(kwargs['deadline'])
        price=args[3].threshold.forecast
        return SimpleNamespace(value=100+price,value_before_deadline=10-price,spend=1)
    monkeypatch.setattr(module,'replay',stub)
    cfg={'seed':1,'duration_mode':'fixed','seconds_per_call':8,'fixed_duration':60,'deadline':30}
    _,_,price=module.tune_warmup(fixture_rows()[:20],24,2,'expected',2,'paper',cfg)
    assert calls and set(calls)=={30} and price==0

def test_zero_cost_and_empty_certificates_are_explicit():
    zero=Job(Proposal('zero',.2,1,.2),0,1,1)
    a=audit_instance([zero],Policy(Threshold(1,10)),1,10)
    assert a['gamma'] is None and a['actual_cost_certificate'] is None
    assert a['actual_cost_certificate_status']=='zero_actual_cost_unbounded_gamma'
    assert a['failures']==[]
    empty=audit_instance([],Policy(Threshold(1,10)),1,10)
    assert empty['J']==0 and empty['reservation_certificate'] is None
    low=Job(Proposal('low',.2,.2,.2),.2,.2,1)
    rejected=audit_instance([low],Policy(Threshold(1,10,'fixed',forecast=10)),1,10)
    assert rejected['alg']==0 and rejected['failures']==[]

def test_occupancy_and_late_charges():
    jobs=[Job(Proposal(str(i),.2,1,.1),.1,1,2) for i in range(5)]
    r=replay(jobs,1,3,Policy(Threshold(1,10,'cap')),'paper',deadline=1)
    assert r.peak_running==3 and r.completed_after_deadline==3
    assert r.value_before_deadline==0 and r.spend==pytest.approx(.3)

def test_partitioned_replay_matches_one_account_and_respects_worker_cap():
    from lag_audit.partitioned import replay_partitioned
    jobs=[Job(Proposal(str(i),.4,.5,.1),.1,.5,2) for i in range(8)]
    policy=Policy(Threshold(1,10),'committed')
    for mode in ['strict','paper','defer']:
        expected=replay(jobs,1,3,policy,mode,5)
        actual=replay_partitioned(jobs,{'a':1},3,{'a':policy},{j.proposal.id:'a' for j in jobs},mode,5)
        assert actual.admitted==expected.admitted
        assert actual.rejected==expected.rejected
        assert actual.spend==pytest.approx(expected.spend)
    accounts={j.proposal.id:str(i%2) for i,j in enumerate(jobs)}
    actual=replay_partitioned(jobs,{'0':.5,'1':.5},1,{'0':policy,'1':policy},accounts,'defer',20)
    assert actual.peak_running<=1
    assert all(e['account_committed']<=e['account_budget']+1e-10 for e in actual.events)

def test_model_identity_is_known_and_cold_start_coefficient_is_zero():
    from lag_audit.prediction import Predictor
    rows=fixture_rows();history=[{**r,'model_identity':'A'} for r in rows[:20]]
    model=Predictor(2,include_model_identity=True).fit(history)
    a=[{**r,'model_identity':'A'} for r in rows[20:]]
    b=[{**r,'model_identity':'B'} for r in rows[20:]]
    pa,ca=model.predict(a);pb,cb=model.predict(b)
    np.testing.assert_allclose(pa,pb,atol=1e-12)
    np.testing.assert_allclose(ca,cb,atol=1e-12)

def test_public_issue_length_reproduces_raw_text_features():
    from lag_audit.prediction import features,Predictor
    rows=fixture_rows();numeric=[{k:v for k,v in r.items() if k!='problem_statement'}|{'issue_length':len(r['problem_statement'])} for r in rows]
    assert [features(r) for r in rows]==[features(r) for r in numeric]
    a=Predictor(2).fit(rows[:20]).predict(rows[20:])
    b=Predictor(2).fit(numeric[:20]).predict(numeric[20:])
    np.testing.assert_array_equal(a[0],b[0]);np.testing.assert_array_equal(a[1],b[1])

def test_suffix_parser_requires_complete_structural_metadata():
    import json
    from lag_audit.data import parse_suffix_info
    obj={'trajectory':['arbitrary text mentioning info and instance_cost'], 'info':{'model_stats':{'instance_cost':1.25,'api_calls':8}},'replay_config':{},'environment':{}}
    raw=json.dumps(obj,indent=2).encode();suffix=raw[raw.index(b'  "info":'):]
    assert parse_suffix_info(suffix)['model_stats']['instance_cost']==1.25
    with pytest.raises(ValueError):parse_suffix_info(b'"instance_cost": 1.25')
    with pytest.raises(ValueError):parse_suffix_info(suffix[:-2])
