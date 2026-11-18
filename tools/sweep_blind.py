"""Blind-window sweep over all 34 test files. Prints per-config totals and per-file win counts vs the base."""
import sys,glob,os,json,warnings; warnings.filterwarnings('ignore'); sys.path.insert(0,'src'); sys.path.insert(0,'tools')
from multiprocessing import Pool
def files():
    return sorted(glob.glob('data/deg/*.csv'))+sorted(glob.glob('data/deg_hold/*.csv'))+sorted(glob.glob('data/deg_mh/*.csv'))
def job(a):
    i,P,f=a
    import main as M; from score import score
    b=os.path.basename(f)[:-4]; o='/tmp/sw_%d_%s.txt'%(i,b); M.run(f,o,dict(P)); r=score('data/raw/%s_gt.csv'%b.rsplit('_',1)[0],o,f); os.remove(o)
    return i,b,r['ate_rmse'],r['blind5_rmse']
if __name__=='__main__':
    cfg=[eval(c) for c in sys.argv[1].split(';')]
    with Pool(2) as p: res=p.map(job,[(i,P,f) for i,P in enumerate(cfg) for f in files()])
    out={}
    for i,b,a,bl in res: out.setdefault(i,{})[b]=(a,bl)
    json.dump({str(k):v for k,v in out.items()},open(sys.argv[2] if len(sys.argv)>2 else '/tmp/sweep.json','w'))
    base=out[0]
    for i,P in enumerate(cfg):
        d=out[i]; A=sum(v[0] for v in d.values()); B=sum(v[1] for v in d.values())
        wa=sum(d[k][0]<base[k][0]-1e-3 for k in d); la=sum(d[k][0]>base[k][0]+1e-3 for k in d)
        wb=sum(d[k][1]<base[k][1]-1e-3 for k in d); lb=sum(d[k][1]>base[k][1]+1e-3 for k in d)
        print('%-40s ATE %.2f (+%d/-%d)  blind %.2f (+%d/-%d)'%(P,A,wa,la,B,wb,lb),flush=True)
