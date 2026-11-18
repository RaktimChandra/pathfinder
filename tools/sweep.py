"""Evaluate parameter sets on all degraded test files (multiprocessing)."""
import sys,os,glob,json,itertools
import numpy as np
from multiprocessing import Pool
sys.path.insert(0,'src'); sys.path.insert(0,'tools')
def job(args):
    f,P,tag=args
    import main as M; from score import score
    seq=os.path.basename(f).rsplit('_',1)[0]
    out='/tmp/sw_%s_%s.txt'%(tag,os.path.basename(f)[:-4])
    try:
        M.run(f,out,P); r=score('data/raw/%s_gt.csv'%seq,out,f)
    except Exception as e:
        return (tag,f,None,str(e))
    return (tag,f,r,None)
def evaluate(plist,files=None,procs=2):
    files=files or sorted(glob.glob('data/deg/*.csv'))
    jobs=[(f,P,str(i)) for i,P in enumerate(plist) for f in files]
    with Pool(procs) as p: res=p.map(job,jobs)
    out=[]
    for i,P in enumerate(plist):
        rs=[r for tag,f,r,e in res if tag==str(i) and r]
        errs=[e for tag,f,r,e in res if tag==str(i) and e]
        if errs: out.append((P,None,errs)); continue
        m={k:float(np.mean([r[k] for r in rs])) for k in ['ate_rmse','waypoint_rmse','blind5_rmse','dropout_rmse','rpe_trans_1s','ate_rot_deg']}
        out.append((P,m,None))
    return out
if __name__=='__main__':
    grid=json.loads(sys.argv[1]); keys=list(grid)
    plist=[dict(zip(keys,v)) for v in itertools.product(*[grid[k] for k in keys])]
    for P,m,e in sorted(evaluate(plist),key=lambda x:(x[1] or {'ate_rmse':9e9})['ate_rmse']):
        print(json.dumps(P), ' -> ', e if e else ' '.join('%s %.3f'%(k.split('_')[0],v) for k,v in m.items()))
