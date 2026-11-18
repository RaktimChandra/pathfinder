"""Fit rotor-drag coefficients K (thrust-perpendicular body axes) from clean GT sequences.
f_perp = K * v_perp + offset (offset per sequence: accelerometer bias)."""
import sys,numpy as np
sys.path.insert(0,'tools'); sys.path.insert(0,'src'); from research_common import *; import main as M
def seq_data(seq):
    gts,P,Q,V,BW,BA=load_gt('data/raw/%s_gt.csv'%seq)
    ts,w,a=load_imu('data/raw/%s_imu.csv'%seq)
    k=(ts>=gts[0])&(ts<=gts[-1]); ts,w,a=ts[k],w[k],a[k]
    t=(ts-gts[0])*1e-9; tg=(gts-gts[0])*1e-9
    vw=np.stack([np.interp(t,tg,V[:,i]) for i in range(3)],1)
    i=np.clip(np.searchsorted(tg,t),0,len(tg)-1); R=qmat(Q[i]); vb=np.einsum('nji,nj->ni',R,vw)
    up=a[t<2].mean(0); up/=np.linalg.norm(up); Bp=M.drag_basis(up)
    n=20  # 0.1 s blocks
    m=len(t)//n*n
    fb=(a[:m]@Bp.T).reshape(-1,n,2).mean(1); vbb=(vb[:m]@Bp.T).reshape(-1,n,2).mean(1)
    return fb,vbb,up
def fit(seqs):
    rows=[];ys=[]
    for j,s in enumerate(seqs):
        fb,vb,_=seq_data(s)
        for ax in range(2):
            pass
        rows.append((fb,vb))
    K=[]
    for ax in range(2):
        # per-sequence offsets: demean within sequence
        x=np.concatenate([vb[:,ax]-vb[:,ax].mean() for fb,vb in rows]); y=np.concatenate([fb[:,ax]-fb[:,ax].mean() for fb,vb in rows])
        K.append(float((x@y)/(x@x)))
    return np.array(K)
if __name__=='__main__':
    seqs=sys.argv[1:]
    print('all:',np.round(fit(seqs),4))
    for s in seqs:
        print('without %s:'%s,np.round(fit([x for x in seqs if x!=s]),4))
