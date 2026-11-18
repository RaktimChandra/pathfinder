"""Blind test of the shipped estimator on newly downloaded sequences (data/deg_new)."""
import sys,warnings;warnings.filterwarnings('ignore');sys.path.insert(0,'src');sys.path.insert(0,'tools')
import main as M; from score import score; from baselines import const
for seq in sys.argv[1:]:
    for h in ['H1','H2']:
        f='data/deg_new/%s_%s.csv'%(seq,h); g='data/raw/%s_gt.csv'%seq
        M.run(f,'/tmp/bn.txt'); r=score(g,'/tmp/bn.txt',f); const(f,'/tmp/bc.txt'); c=score(g,'/tmp/bc.txt',f)
        print('%s_%s ours %.2f const %.2f | blind ours %.2f const %.2f'%(seq,h,r['ate_rmse'],c['ate_rmse'],r['blind5_rmse'],c['blind5_rmse']),flush=True)
