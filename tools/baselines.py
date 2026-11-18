"""Reference baselines on the same inputs/scorer:
  naive  - textbook strapdown: biases from first 2 s, gyro integration, gravity removal, double integration
  const  - constant position (identity attitude), tiny jitter only to keep Umeyama well-posed
"""
import sys,os,glob,json,numpy as np
sys.path.insert(0,'src'); sys.path.insert(0,'tools'); import main as M; from score import score
def naive(f,out):
    ts,w,a=M.parse_imu(f); t,tsu,valid,dead,W,A=M.triage(ts,w,a)
    W=W.astype(np.float64); A=A.astype(np.float64)
    m=t<2.0; bg=W[m].mean(0); g0=A[m].mean(0)
    q=np.array(M._q_from_up(g0/np.linalg.norm(g0))); R=M.quat_to_R(q[None])[0]
    n=len(t); p=np.zeros((n,3)); v=np.zeros(3); pos=np.zeros(3); Q=np.zeros((n,4))
    ba=R.T@np.array([0,0,M.G])-g0   # accel bias so that initial specific force == gravity
    for i in range(n):
        Q[i]=q; p[i]=pos
        if i==n-1: break
        d=t[i+1]-t[i]
        acc=M.quat_to_R(q[None])[0]@(A[i]+ba)-np.array([0,0,M.G])
        pos=pos+v*d+0.5*acc*d*d; v=v+acc*d
        q=M._qexp_v(((W[i]-bg)*d)[None])[0]; q=M._qmul_v(Q[i],q); q/=np.linalg.norm(q)
    trow=(ts-tsu[0])*1e-9
    j=np.clip(np.searchsorted(tsu,ts),0,n-1)
    with open(out,'w') as fo:
        for r,jj in zip(ts,j):
            fo.write('%d.%09d %.6f %.6f %.6f %.8f %.8f %.8f %.8f\n'%(r//10**9,r%10**9,*p[jj],Q[jj,1],Q[jj,2],Q[jj,3],Q[jj,0]))
def const(f,out):
    ts,w,a=M.parse_imu(f)
    rng=np.random.default_rng(0)
    with open(out,'w') as fo:
        for r in ts:
            e=rng.normal(0,1e-4,3); fo.write('%d.%09d %.6f %.6f %.6f 0 0 0 1\n'%(r//10**9,r%10**9,*e))
if __name__=='__main__':
    files=sys.argv[1:] or sorted(glob.glob('data/deg/*.csv'))+sorted(glob.glob('data/deg_hold/*.csv'))+sorted(glob.glob('data/deg_mh/*.csv'))
    res={}
    for f in files:
        seq=os.path.basename(f).rsplit('_',1)[0]; gt='data/raw/%s_gt.csv'%seq; b=os.path.basename(f)[:-4]
        r={}
        for name,fn in [('naive',naive),('const',const)]:
            o='results/base_%s_%s.txt'%(name,b); fn(f,o); r[name]=score(gt,o,f)
        o='results/%s.txt'%b
        P={}
        if not seq.startswith('TUM'):
            # leave-one-sequence-out drag calibration: fit on the other EuRoC sequences only
            from fit_drag import fit
            others=sorted({os.path.basename(x)[:-8] for x in glob.glob('data/raw/*_imu.csv') if not os.path.basename(x).startswith('TUM')}-{seq})
            if others: P['drag_k']=fit(others).tolist()
        M.run(f,o,P); r['ours']=score(gt,o,f); r['ours']['drag_k_loo']=P.get('drag_k')
        res[b]={k:{m:v.get(m) for m in ['ate_rmse','waypoint_rmse','blind5_rmse','dropout_rmse','rpe_trans_1s','const_baseline_rmse','drag_k_loo']} for k,v in r.items()}
        print('%-20s naive %10.1f m | const %.2f | ours %.2f'%(b,r['naive']['ate_rmse'],r['const']['ate_rmse'],r['ours']['ate_rmse']),flush=True)
    json.dump(res,open('results/baselines.json','w'),indent=1)
