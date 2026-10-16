import json
from pathlib import Path
import numpy as np
import pytest
from lag_audit.data import parse_trajectory,normalize,safe_destination,sha256
from lag_audit.prediction import features,Predictor
from lag_audit.empirical import partition,run_experiments
from lag_audit.statistics import paired_block_interval


def fixture_rows(n=40):
    # SYNTHETIC TEST FIXTURE, not SWE-bench measurements.
    return [{'id':f'fixture:{i}', 'instance_id':f'fake__repo-{i}', 'submission':'fixture',
             'repo':f'fixture/repo-{i%2}', 'problem_statement':'x'*(10+i*5),
             'created_at':f'2024-01-{1+i//4:02d}T00:00:00Z',
             'actual_cost':.25+(i%3)*.2, 'resolved':i%2,'api_calls':i+1} for i in range(n)]


def test_parser_not_cumulative_cost():
    record=parse_trajectory({'info':{'model_stats':{'instance_cost':2.3,'total_cost':1000,'api_calls':20}}})
    assert record['actual_cost']==2.3 and record['api_calls']==20
    with pytest.raises(ValueError): parse_trajectory({'info':{'model_stats':{'total_cost':1000}}})
    assert parse_trajectory({'info':{'model_stats':{'instance_cost':0}}})['actual_cost']==0


def test_ingestion_missingness_and_feature_firewall(tmp_path):
    rows=fixture_rows(4)
    trajs=tmp_path/'trajs'; trajs.mkdir()
    for r in rows[:3]:
        (trajs/(r['instance_id']+'.traj')).write_text(json.dumps({'info':{'model_stats':{'instance_cost':.5,'api_calls':3}}}))
    for r in rows: r['difficulty']='GOLD PATCH LEAK'
    out=tmp_path/'normalized.jsonl'
    audit=normalize(rows,trajs,{'resolved':[rows[0]['instance_id']], 'no_logs':[rows[1]['instance_id']]},'fixture',out)
    assert audit['retained']==2 and not audit['complete']
    assert len(audit['exclusions'])==2
    assert 'difficulty' not in out.read_text()
    assert 'GOLD PATCH' not in out.read_text()


def test_duplicate_trajectory_is_not_silently_another_attempt(tmp_path):
    r=fixture_rows(1)[0]
    (tmp_path/(r['instance_id']+'.traj')).write_text('{}')
    (tmp_path/(r['instance_id']+'.json')).write_text('{}')
    with pytest.raises(ValueError,match='Duplicate'):
        normalize([r],tmp_path,{'resolved':[]},'fixture',tmp_path/'out.jsonl')


@pytest.mark.parametrize('relative',['../bad','/tmp/bad','a/../../bad','a\\bad'])
def test_download_paths_cannot_escape(tmp_path,relative):
    with pytest.raises(ValueError): safe_destination(tmp_path,relative)


def test_both_predictors_ignore_all_forbidden_fields():
    rows=fixture_rows(15)
    changed=[{**r,'difficulty':'<15 min','patch':'secret','resolved':1-r['resolved'],
              'hints_text':'reference fix','other_agent_outcome':1,'actual_cost':5} for r in rows]
    assert [features(r) for r in rows]==[features(r) for r in changed]
    model=Predictor(6).fit(rows[:10])
    p,c=model.predict(rows[10:])
    pp,cc=model.predict(changed[10:])
    np.testing.assert_array_equal(p,pp); np.testing.assert_array_equal(c,cc)
    with pytest.raises(ValueError,match='overlap'): model.predict(rows[:1])


def test_blocks_disjoint_and_no_modulo_rotations():
    blocks=partition(fixture_rows(),10)
    assert len(blocks)==10
    assert len({r['id'] for b in blocks for r in b})==40
    assert max(r['created_at'] for r in blocks[0])<=min(r['created_at'] for r in blocks[1])


def small_config():
    config=json.loads(Path('configs/pilot.json').read_text())
    config.update(budgets=[3.0],reservation=2.0,workers=[2],queue_modes=['strict'],
                  density_modes=['reservation'],feedback_modes=['admitted_only','full_archive'],
                  policies=['hard_cap','zcl_settled','lag_structural'],bootstrap_resamples=100)
    return config


def save_fixture(tmp_path,rows,name):
    path=tmp_path/f'{name}.jsonl'
    path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    path.with_suffix('.audit.json').write_text(json.dumps({'complete':True,'normalized_sha256':sha256(path)}))
    return path


def test_replay_end_to_end_on_synthetic_fixture(tmp_path):
    data=save_fixture(tmp_path,fixture_rows(),'fixture')
    config=small_config()
    result=run_experiments(data,config,tmp_path/'run')
    assert result['episodes']==48
    provenance=json.loads((tmp_path/'run'/'training_provenance.json').read_text())
    for row in provenance:
        assert not set(row['training_ids']) & set(row['test_ids'])
    selective=[r for r in provenance if r['feedback']=='admitted_only' and r['policy']=='hard_cap']
    full=[r for r in provenance if r['feedback']=='full_archive' and r['policy']=='hard_cap']
    assert len(selective[-1]['training_ids'])<len(full[-1]['training_ids'])
    assert (tmp_path/'run'/'ledger.jsonl').stat().st_size>0
    with pytest.raises(FileExistsError): run_experiments(data,config,tmp_path/'run')


def test_mutating_future_labels_cannot_change_past_results(tmp_path):
    rows=fixture_rows()
    config=small_config();config.update(feedback_modes=['admitted_only'],policies=['zcl_settled','lag_structural'])
    first=save_fixture(tmp_path,rows,'first')
    run_experiments(first,config,tmp_path/'first_run')
    mutated=[dict(r) for r in rows]
    for r in mutated[-4:]: r['resolved']=1-r['resolved'];r['actual_cost']=1.5
    second=save_fixture(tmp_path,mutated,'second')
    run_experiments(second,config,tmp_path/'second_run')
    a=[json.loads(x) for x in (tmp_path/'first_run'/'episodes.jsonl').read_text().splitlines()]
    b=[json.loads(x) for x in (tmp_path/'second_run'/'episodes.jsonl').read_text().splitlines()]
    assert [r for r in a if r['block']<9]==[r for r in b if r['block']<9]


def test_paired_interval_reproducible_and_constant():
    a=paired_block_interval([2]*8,resamples=100)
    assert a['mean_difference']==a['ci95_low']==a['ci95_high']==2
    assert paired_block_interval([-1,2,0,4],resamples=100)==paired_block_interval([-1,2,0,4],resamples=100)
