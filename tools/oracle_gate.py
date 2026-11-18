"""Research: upper bound of (a) ZUPT anywhere and (b) gating the drag model off when not flying, using GT oracle masks."""
import sys,numpy as np,warnings; warnings.filterwarnings('ignore'); sys.path.insert(0,'src'); sys.path.insert(0,'tools')
import main as M; from score import score; from research_common import load_gt
src=open('src/main.py').read()
def run_masks(f,gtf,mode):
    S=M.run(f,None,return_state=True); nb=len(S['ub']); dtb=S['dtb']
    gts,Pg,Qg,V,_,_=load_gt(gtf); t0=S['tsu'][0]; tg=(gts-t0)*1e-9
    tk=(np.arange(nb)+0.5)*dtb; sp=np.interp(tk,tg,np.linalg.norm(V,axis=1)); z=np.interp(tk,tg,Pg[:,2])
    zmin=np.percentile(Pg[:,2],1)
    static=(np.arange(nb)+1)*dtb<=S['t_static']
    if 'zupt' in mode: static=static|(sp<0.02)
    K=S['K']; P=dict(S['P'])
    fly=z>zmin+0.25   # oracle: airborne
    has=S['has'].copy()
    if 'gate' in mode:
        # drag obs only while airborne: emulate by giving non-flying blocks no drag via huge noise -> implement by zeroing Bp contribution
        pass
    # patched translation with drag mask
    ns={}
    code=src.split('def translation')[1].split('\n# ====')[0]
    code='def translation'+code.replace('if multi and meas[i] and P["rdrag"] < 1e5:','if multi and meas[i] and dragok[i] and P["rdrag"] < 1e5:').replace('qb_k=None):','qb_k=None, dragok=None):\n    dragok = np.ones(len(ub), bool) if dragok is None else dragok',1)
    exec(code,M.__dict__,ns)
    qa,qb=S['qa_k'],S['qb_k']
    dk=fly if 'gate' in mode else None
    tk,pk,vk=ns['translation'](S['ub'],S['fp'],has,S['blind'],S['qmid'],dtb,S['Bp'],K,P,static=static,qa_k=qa,qb_k=qb,dragok=dk)
    M.write_output('/tmp/or.txt',M.parse_imu(f)[0],t0,tk,pk,vk,S['td'],S['Qd'])
    return score(gtf,'/tmp/or.txt',f)['ate_rmse']
for s in sys.argv[1:]:
    f=('data/deg_mh/%s.csv' if s.startswith('MH') else 'data/deg/%s.csv')%s; gtf='data/raw/%s_gt.csv'%s.rsplit('_',1)[0]
    print(s,' '.join('%s %.2f'%(m,run_masks(f,gtf,m)) for m in ['base','zupt','gate','zupt+gate']),flush=True)
