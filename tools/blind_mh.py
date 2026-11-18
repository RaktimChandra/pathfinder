"""Blind test on EuRoC Machine Hall: the shipped main.py, untouched defaults (drag K fitted on Vicon rooms only)."""
import sys,os,glob,json
sys.path.insert(0,'src'); sys.path.insert(0,'tools'); import main as M; from score import score
from baselines import naive,const
files=sys.argv[1:] or sorted(glob.glob('data/deg_mh/*.csv'))
res={}
for f in files:
    b=os.path.basename(f)[:-4]; seq=b.rsplit('_',1)[0]; gt='data/raw/%s_gt.csv'%seq; r={}
    for name,fn in [('naive',naive),('const',const)]:
        o='results/base_%s_%s.txt'%(name,b); fn(f,o); r[name]=score(gt,o,f)
    o='results/%s.txt'%b; M.run(f,o); r['ours']=score(gt,o,f)
    res[b]={k:{m:v.get(m) for m in ['ate_rmse','waypoint_rmse','blind5_rmse','dropout_rmse','rpe_trans_1s']} for k,v in r.items()}
    print('%-22s naive %9.1f | const %5.2f | ours %5.2f | blind ours %5.2f const %5.2f'%(b,r['naive']['ate_rmse'],r['const']['ate_rmse'],r['ours']['ate_rmse'],r['ours']['blind5_rmse'],r['const']['blind5_rmse']),flush=True)
json.dump(res,open('results/blind_mh.json','w'),indent=1)
