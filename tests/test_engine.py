from dataclasses import replace
import pytest
from lag_audit.engine import Job,Proposal,Policy,replay
from lag_audit.thresholds import Threshold


def jobs(n=5,reservation=.6,actual=.05,value=1,duration=1):
    return [Job(Proposal(str(i),reservation,value,min(actual,reservation)),actual,value,duration) for i in range(n)]


def test_budget_and_refund_ledger():
    result=replay(jobs(),1,4,Policy(Threshold(1,10,'cap')),'defer')
    assert result.spend==pytest.approx(.25)
    assert result.value==5
    for event in result.events:
        assert -1e-10<=event['committed']<=1+1e-10
        assert event['reserved']>=-1e-10
    assert result.delta==pytest.approx(.6)


def test_strict_vs_waiting_room_semantics():
    policy=Policy(Threshold(1,10,'cap'))
    assert replay(jobs(),1,4,policy,'strict').value==1
    assert replay(jobs(),1,4,policy,'paper').value==5
    assert replay(jobs(),1,4,policy,'defer').value==5


def test_price_recheck_is_independent_queue_ablation():
    stream=jobs(n=3,reservation=.4,actual=.05,value=.5)
    policy=Policy(Threshold(1,10),'committed')
    paper=replay(stream,1,3,policy,'paper')
    defer=replay(stream,1,3,policy,'defer')
    assert len(paper.admitted)==1
    assert len(defer.admitted)==3


def test_completed_outcomes_not_available_to_policy():
    stream=jobs(n=6,reservation=.2,actual=.1,value=.3)
    changed=[replace(j,value=123) for j in stream]
    policy=Policy(Threshold(1,10),'settled')
    a=replay(stream,1,2,policy,'paper')
    b=replay(changed,1,2,policy,'paper')
    assert a.admitted==b.admitted
    assert a.rejected==b.rejected
    assert not hasattr(stream[0].proposal,'actual_cost')
    assert not hasattr(stream[0].proposal,'resolved')


def test_deadline_charges_late_work():
    result=replay(jobs(n=5),1,2,Policy(Threshold(1,10,'cap')),'defer',deadline=1.5)
    assert result.value_before_deadline==1
    assert result.value==2
    assert result.spend==pytest.approx(.1)


def test_completion_before_equal_timestamp_arrival():
    a=Job(Proposal('a',.6,1,.1),.1,1,1,0)
    b=Job(Proposal('b',.6,1,.1),.1,1,1,1)
    assert replay([a,b],1,2,Policy(Threshold(1,10,'cap')),'strict').admitted==['a','b']


def test_settled_delta_includes_own_reservation():
    result=replay(jobs(n=4,reservation=.2,actual=.1,value=1),1,4,
                  Policy(Threshold(1,10,'cap'),'settled'),'strict')
    assert result.delta==pytest.approx(.8)


def test_duplicate_job_and_reservation_violation_fail_closed():
    with pytest.raises(ValueError):
        Job(Proposal('x',.1,1,.1),.2,1,1)
    j=jobs(1)[0]
    with pytest.raises(ValueError):
        replay([j,j],1,2,Policy(Threshold(1,10)))


def test_full_budget_job():
    p=Proposal('x',1,1,1)
    result=replay([Job(p,1,1,1)],1,1,Policy(Threshold(1,10,'cap')))
    assert result.spend==1 and result.delta==1
