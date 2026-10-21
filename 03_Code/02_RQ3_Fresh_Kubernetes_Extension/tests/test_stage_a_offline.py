#!/usr/bin/env python3
"""Offline state-machine test. Synthetic outputs are not scientific evidence."""
import json, math, shutil, sys, tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import run_stage_a as M

def fake_cell(root,phase,cid,rates,rng,duty,extra):
    accepted=root/'cells'/phase/cid/'accepted.json'
    if accepted.exists(): return json.loads(accepted.read_text())
    accepted.parent.mkdir(parents=True,exist_ok=True)
    if phase=='solo':
        sta=extra['sta_index']; g=2050.0+20*sta
        off=sum(rates); D=g/off
        rec={'phase':phase,'cell_id':cid,'rng_run':rng,'duty_fraction':duty,'rates_mbps':rates,
             'aggregate_offered_mbps':off,'aggregate_achieved_mbps':g,'aggregate_delivered_fraction':D,
             'packets':[],'resource':{},'attempt':1,'elapsed_seconds':0.0,**extra}
    else:
        # recover planned U from rates using known fake solo capacities
        gs=[2050.0+20*i for i in range(6)]
        U=sum((r/g) for r,g in zip(rates,gs) if r>0)/duty
        m=sum(r>0 for r in rates)
        air=[r/g for r,g in zip(rates,gs) if r>0]; tot=sum(air); p=[a/tot for a in air]; ne=1/sum(x*x for x in p)
        # Deterministic synthetic mechanism: loss depends on U, N_eff and m, plus tiny RNG perturbation.
        loss=min(0.9,max(0.0,0.03*U*U+0.012*math.log(ne)+0.008*math.log(m)+0.00001*(rng%10)))
        D=1-loss; off=sum(rates); ach=off*D
        rec={'phase':phase,'cell_id':cid,'rng_run':rng,'duty_fraction':duty,'rates_mbps':rates,
             'aggregate_offered_mbps':off,'aggregate_achieved_mbps':ach,'aggregate_delivered_fraction':D,
             'packets':[],'resource':{},'attempt':1,'elapsed_seconds':0.0,**extra}
    M.dump(accepted,rec); return rec

tmp=Path(tempfile.mkdtemp(prefix='p2-stagea-offline-'))
old_results,old_current=M.RESULTS,M.CURRENT
M.RESULTS=tmp; M.CURRENT=tmp/'CURRENT_RUN.txt'
try:
    assert M.self_test(check_disk=False)['science_intents']==2700
    root=M.ensure_runroot()
    # Holdout must be locked initially.
    try:
        M.execute_split(root,'holdout',cell_fn=fake_cell,workers=8)
        raise AssertionError('holdout lock failed')
    except RuntimeError as e:
        assert 'LOCKED' in str(e)
    solo=M.solo_calibration(root,cell_fn=fake_cell)
    assert len(solo['solo_goodputs_mbps'])==6
    cal=M.execute_split(root,'calibration',cell_fn=fake_cell,workers=8)
    assert cal['accepted']==1350
    fits=M.fit_freeze(root)
    assert M.coefficient_freeze_valid(root)
    hold=M.execute_split(root,'holdout',cell_fn=fake_cell,workers=8)
    assert hold['accepted']==1350
    rep=M.analyze_holdout(root)
    assert rep['primary_RQ1']['n_shapes']==30
    assert (root/'holdout_shape_errors.csv').exists()
    # Resume must not create extra accepted cells.
    M.execute_split(root,'holdout',cell_fn=fake_cell,workers=8)
    assert len(list((root/'cells/holdout').glob('*/accepted.json')))==1350
    print(json.dumps({'offline_pipeline':'PASS','calibration_cells':1350,'holdout_cells':1350,
                      'coefficient_freeze_valid':True,'rq1_shapes':30,
                      'synthetic_primary':rep['primary_RQ1']},indent=2))
finally:
    M.RESULTS, M.CURRENT = old_results, old_current
    shutil.rmtree(tmp)
