"""Materialize the already executed official VNS initialization failure.

Reads only the persisted manifest/error/result artifacts. It does not read /tmp,
call any optimizer, or alter the existing completed run files.
"""
import json
from pathlib import Path
import shutil
import sys

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
sys.path.insert(0,str(ROOT/'src'))
from problem import atomic_json
from run_final import (CHECKPOINT,FROZEN,ROOT as REPO_ROOT,configuration,digest,
                       initialization_failure_outcome,outcome_path,persist_outcome,plan,
                       utc)


def main():
    manifest_path=OUT/'manifest.json';manifest=json.loads(manifest_path.read_text())
    if manifest.get('status')!='blocked_error':raise ValueError('Expected original recorded execution failure')
    failure=manifest.get('error')
    if not failure or failure.get('message')!='Inicialização aleatória não encontrou schedule completo':
        raise ValueError('Original failure does not match the independently classified initializer limitation')
    target=next(s for s in plan(manifest['inventory']) if s['file']==failure['run']['file'])
    expected=dict(experiment='B',instance='data/input/set2/750_10_1439_5_S_1-9.dat',algorithm='vns_vnd',
                  seed=101,budget=2000,block=135,order_in_block=['vns_vnd','spea2','moead'])
    if any(target[k]!=v for k,v in expected.items()) or target!=failure['run']:
        raise ValueError('Stored failed cell does not match the officially attempted design cell')
    if target['file'] in manifest['completed_runs'] or (OUT/target['file']).exists():
        raise ValueError('Failed cell unexpectedly has a successful run artifact')
    if manifest['completed_count']!=405 or manifest['completed_attempts']!=3150000:
        raise ValueError('Unexpected campaign checkpoint counts')
    if len(manifest['completed_runs'])!=405 or manifest['baseline_reads']:
        raise ValueError('Unexpected preserved search/baseline state')
    source=manifest['source_sha256']
    if source.get('src/metaheuristics/vns_vnd.py')!=digest(ROOT/'src/metaheuristics/vns_vnd.py'):
        raise ValueError('Algorithm source provenance mismatch')
    legacy_path=OUT/'execution_failure.json'
    legacy=json.loads(legacy_path.read_text())
    if (legacy.get('status')!='failed_initialization' or legacy.get('run')!=target
            or legacy.get('construction_attempts')!=200 or legacy.get('search_evaluator_attempts')!=0
            or legacy.get('source_sha256')!=source):
        raise ValueError('Post-run preserved diagnostic does not corroborate the official manifest failure')
    expected_outcome=outcome_path(target)
    if expected_outcome.exists():raise FileExistsError(expected_outcome)
    history=OUT/'history'/'before_protocol_amendment_2'
    if history.exists():raise FileExistsError(history)
    history.mkdir(parents=True)
    for name in ['manifest.json','relatorio.md','execution_failure.json','metrics.csv',
                 'normalized_metrics.csv','validation.json','final_checks.json']:
        path=OUT/name
        if path.exists():shutil.copyfile(path,history/name)
    if legacy_path.exists():
        amendment_source_hash=digest(legacy_path)
    outcome=initialization_failure_outcome(target,initialization_attempts=legacy['construction_attempts'],
        elapsed_seconds=None,failure_reason=failure['message'],source_sha256=source,
        occurred_utc=failure['detected_utc'],provenance='materialized after the fact from the official persisted manifest failure and preserved post-run diagnostic; no /tmp data or optimizer rerun used')
    outcome['elapsed_seconds_provenance']='unavailable: the original official runner did not persist a per-cell start timer; left null rather than infer from another run or nonofficial logs'
    outcome['official_attempt']=True
    outcome['diagnostic_artifact_sha256']=amendment_source_hash
    outcome['initialization_attempts_source']='original runner bound max(20, initial_solutions*50)=200 plus preserved diagnostic construction_attempts'
    outcomes_dir=OUT/'outcomes';outcomes_dir.mkdir(exist_ok=True)
    # Preserve the first campaign artifact as an auditable baseline for amendment 2.
    old_manifest_sha=digest(manifest_path)
    amendment=dict(id=2,defined_utc=utc(),decision='treat frozen VNS/VND initialization failure as explicit scalability outcome',
        independent_root_cause_confirmed_by_user=True,algorithm_checkpoint=CHECKPOINT,
        algorithms_modified=False,planned_cells_preserved=60,failed_cell=target,
        prior_attempt_not_repeated=True,materialized_posthoc=True,provenance='manifest.error + official planned cell + source/input hashes + preserved execution_failure.json; /tmp not used',
        initialization_attempts=200,search_attempts=0,feasible_evaluations=0,rejected_evaluations=0,
        cause='frozen randomized constructor returned None for all 200 attempts, as independently confirmed',
        elapsed_seconds=None,elapsed_seconds_limitation=outcome['elapsed_seconds_provenance'],
        original_failure_detected_utc=failure['detected_utc'],legacy_diagnostic_sha256=amendment_source_hash,
        prior_manifest_sha256=old_manifest_sha,order_and_seeds_unchanged=True,
        continue_after_same_class_initialization_failures=True,unexpected_errors='record execution_failed and stop for investigation')
    manifest.setdefault('protocol_amendments',[]).append(amendment)
    manifest['historical_execution_error']=failure
    manifest.pop('error',None)
    manifest['status']='running'
    manifest['resumable_after_protocol_amendment']=True
    manifest['outcome_schema']={'version':1,'statuses':['completed','initialization_failed','execution_failed'],
        'quality_metrics_on_failure':'null; no synthetic front or penalty values'}
    persist_outcome(target,outcome,manifest,manifest_path)
    manifest['protocol_amendments'][-1]['initial_failure_outcome_sha256']=manifest['cell_outcomes'][target['file']]['outcome_file_sha256']
    manifest['script_sha256']={name:digest(OUT/name) for name in ['run_final.py','analyze_final.py','normalization.py','validate_normalization.py','summarize_blocked.py','record_initialization_failure.py']}
    atomic_json(manifest_path,manifest)
    with (OUT/'relatorio.md').open('a',encoding='utf-8') as stream:
        stream.write('\n## Protocol amendment 2 — initialization failures as outcomes\n\n'+
            'Following independent root cause confirmation, the VNS/VND algorithm remains frozen at checkpoint 40bf609. '+
            'Initialization failures under the existing initializer/protocol are recorded as outcomes. '+
            'The already attempted B cell VNS/VND, seed 101, 750_10_1439_5_S_1-9, was materialized post hoc '+
            'from the persisted original manifest failure and the preserved official diagnostic. It was not rerun. '+
            'There were 200 constructor attempts, zero evaluator calls, zero search attempts, zero feasible/rejected evaluations. '+
            'The original invocation did not record a per-cell timer, so elapsed_seconds is null rather than reconstructed '+
            'from other cell timings or /tmp logs. The rest of B keeps its 60 frozen cells, seeds, budgets, and order; '+
            'the recorded initialization failure counts as that cell and later runs continue once each. '+
            'Unexpected technical failures get status execution_failed and stop the campaign.\n')
    print(f"Materialized the prior official failure once: {manifest['cell_outcomes'][target['file']]}")


if __name__=='__main__':main()
