import sys,os,copy,numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
sys.path.insert(0,'tools'); from evo.tools import file_interface; from evo.core import sync
from score import load_est
f=sys.argv[1]; seq=os.path.basename(f).rsplit('_',1)[0]; est='results/%s.txt'%os.path.basename(f)[:-4]
gt=file_interface.read_euroc_csv_trajectory('data/raw/%s_gt.csv'%seq); e=load_est(est)
g,e=sync.associate_trajectories(gt,e,max_diff=0.003); ea=copy.deepcopy(e); ea.align(g,correct_scale=False)
t=g.timestamps-g.timestamps[0]; err=np.linalg.norm(ea.positions_xyz-g.positions_xyz,axis=1)
fig,ax=plt.subplots(4,1,figsize=(11,9),sharex=True)
for i,l in enumerate('xyz'):
    ax[i].plot(t,g.positions_xyz[:,i],'k',lw=1,label='GT'); ax[i].plot(t,ea.positions_xyz[:,i],'C1',lw=1,label='est'); ax[i].set_ylabel(l)
ax[3].plot(t,err,'C3'); ax[3].set_ylabel('err m'); ax[0].legend(); ax[3].axvspan(t[-1]-5,t[-1],color='0.85')
plt.tight_layout(); plt.savefig('results/plot_%s.png'%os.path.basename(f)[:-4],dpi=70)
