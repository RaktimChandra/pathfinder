"""Ablation: final configuration vs one component removed (EuRoC: LOO drag calibration)."""
import sys,os,glob,json,numpy as np
from multiprocessing import Pool
sys.path.insert(0,'src'); sys.path.insert(0,'tools')
ABL={'final':{}, 'no rotor-drag velocity':{'rdrag':1e6}, 'no degradation-aware noise':{'qa_exc':0.0,'qb_sev':0.0,'qb_exc':0.0},
     'no rest-period bias / ZUPT':{'use_static_bias':False,'static_gyro_std':-1.0}, 'constant-velocity blind window':{'blind_tau':1e6}}
def job(a):
    name,P,f=a
    import main as M; from score import score; from fit_drag import fit
    seq=os.path.basename(f).rsplit('_',1)[0]; P=dict(P)
    if not seq.startswith('TUM'):
        others=sorted({os.path.basename(x)[:-8] for x in glob.glob('data/raw/*_imu.csv') if not os.path.basename(x).startswith('TUM')}-{seq})
        P['drag_k']=fit(others).tolist()
    o='/tmp/abl_%s_%s.txt'%(name.replace(' ','_').replace('/',''),os.path.basename(f)[:-4]); M.run(f,o,P)
    return name,seq,score('data/raw/%s_gt.csv'%seq,o,f)
if __name__=='__main__':
    files=sorted(glob.glob('data/deg/*.csv'))+sorted(glob.glob('data/deg_hold/*.csv'))
    with Pool(2) as p: res=p.map(job,[(n,P,f) for n,P in ABL.items() for f in files])
    out={}
    for n in ABL:
        for grp,pre in [('EuRoC',('V1','V2')),('TUM-VI',('TUM',))]:
            rs=[r for nn,s,r in res if nn==n and s.startswith(pre)]
            out.setdefault(n,{})[grp]={m:float(np.mean([r[m] for r in rs])) for m in ['ate_rmse','waypoint_rmse','blind5_rmse','dropout_rmse']}
        print('%-32s EuRoC ATE %.3f blind %.3f | TUM ATE %.3f blind %.3f'%(n,out[n]['EuRoC']['ate_rmse'],out[n]['EuRoC']['blind5_rmse'],out[n]['TUM-VI']['ate_rmse'],out[n]['TUM-VI']['blind5_rmse']),flush=True)
    json.dump(out,open('results/ablation.json','w'),indent=1)
