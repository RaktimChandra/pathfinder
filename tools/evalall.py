"""Run main.py on all test inputs and score. usage: evalall.py [json params]"""
import sys,os,json,time,glob,tracemalloc,importlib
sys.path.insert(0,'src'); sys.path.insert(0,'tools')
import main as M; from score import score
P=json.loads(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1].startswith('{') else {}
pat=[x for x in sys.argv[1:] if not x.startswith('{')]
files=sorted(glob.glob('data/deg/*.csv')) if not pat else pat
rows=[]
for f in files:
    seq=os.path.basename(f).rsplit('_',1)[0] if '_H' in f else os.path.basename(f)[:-8]
    gt='data/raw/%s_gt.csv'%seq; out='results/%s.txt'%os.path.basename(f)[:-4]
    t0=time.perf_counter(); info=M.run(f,out,P); el=time.perf_counter()-t0
    r=score(gt,out,f)
    rows.append(r)
    print('%-26s ATE %6.3f (const %.2f) wp %6.3f blind %6.3f drop %6.3f RPE %.3f rot %5.1f | %.2fs %s'%(os.path.basename(f),r['ate_rmse'],r['const_baseline_rmse'],r['waypoint_rmse'],r['blind5_rmse'],r['dropout_rmse'] or -1,r['rpe_trans_1s'],r['ate_rot_deg'],el,info['platform']))
import numpy as np
print('MEAN ATE %.3f  wp %.3f blind %.3f'%(np.mean([r['ate_rmse'] for r in rows]),np.mean([r['waypoint_rmse'] for r in rows]),np.mean([r['blind5_rmse'] for r in rows])))
