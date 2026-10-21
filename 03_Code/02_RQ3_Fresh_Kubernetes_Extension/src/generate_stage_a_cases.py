from __future__ import annotations
import json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
CFG=json.loads((ROOT/"config"/"stage_a.json").read_text())
# Active physical-link identities are balanced across calibration and holdout.
# Each alpha stratum defines two subsets; reps 0/1 (calibration) and 2/3
# (holdout) use the same subset pair but independent Dirichlet seeds.
ACTIVE_SUBSET_PAIRS={
  2:[[[0,1],[2,3]], [[2,3],[4,5]], [[4,5],[0,1]]],
  3:[[[0,1,2],[3,4,5]], [[0,2,4],[1,3,5]], [[0,3,4],[1,2,5]]],
  4:[[[2,3,4,5],[0,1,4,5]], [[0,1,4,5],[0,1,2,3]], [[0,1,2,3],[2,3,4,5]]],
  5:[[[1,2,3,4,5],[0,2,3,4,5]], [[0,1,3,4,5],[0,1,2,4,5]], [[0,1,2,3,5],[0,1,2,3,4]]],
  6:[[[0,1,2,3,4,5],[0,1,2,3,4,5]]]*3,
}

def seed_for(m,ai,rep): return 170000+1000*m+100*ai+rep
def build():
    shapes=[]
    for m in CFG["active_stream_counts"]:
        for ai,alpha in enumerate(CFG["dirichlet_alpha"]):
            for rep in range(CFG["shape_replicates_per_cell"]):
                seed=seed_for(m,ai,rep)
                active=ACTIVE_SUBSET_PAIRS[m][ai][rep % 2]
                vals=np.random.default_rng(seed).dirichlet([float(alpha)]*m)
                w=[0.0]*CFG["num_streams"]
                for idx,val in zip(active,vals): w[idx]=float(val)
                hhi=sum(v*v for v in w if v>0)
                shapes.append({"shape_id":f"m{m}-a{alpha:g}-r{rep}","m":m,"alpha":float(alpha),
                    "rep":rep,"seed":seed,"split":"calibration" if rep in CFG["calibration_rep_indices"] else "holdout",
                    "active_sta_indices":active,"normalized_weights":w,"hhi":hhi,"n_eff":1.0/hhi})
    return shapes
if __name__=="__main__":
    shapes=build()
    assert len(shapes)==60
    (ROOT/"config"/"stage_a_shapes.json").write_text(json.dumps({"shapes":shapes},indent=2))
    print(ROOT/"config"/"stage_a_shapes.json")
