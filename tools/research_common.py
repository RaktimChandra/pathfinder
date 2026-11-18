import numpy as np
def qmat(q):  # q = w,x,y,z -> R
    w,x,y,z=q[...,0],q[...,1],q[...,2],q[...,3]
    R=np.empty(q.shape[:-1]+(3,3))
    R[...,0,0]=1-2*(y*y+z*z); R[...,0,1]=2*(x*y-w*z); R[...,0,2]=2*(x*z+w*y)
    R[...,1,0]=2*(x*y+w*z); R[...,1,1]=1-2*(x*x+z*z); R[...,1,2]=2*(y*z-w*x)
    R[...,2,0]=2*(x*z-w*y); R[...,2,1]=2*(y*z+w*x); R[...,2,2]=1-2*(x*x+y*y)
    return R
def load_imu(p):
    ts=np.loadtxt(p,delimiter=',',comments='#',usecols=0,dtype=np.int64)
    d=np.loadtxt(p,delimiter=',',comments='#')[:,1:]
    return ts,d[:,0:3],d[:,3:6]
def load_gt(p):
    d=np.loadtxt(p,delimiter=',',comments='#')
    ts=np.loadtxt(p,delimiter=',',comments='#',usecols=0,dtype=np.int64)
    return ts,d[:,1:4],d[:,4:8],d[:,8:11],d[:,11:14],d[:,14:17]
def interp_gt(ts_q,gts,P,Q):
    t=(ts_q-gts[0])*1e-9; tg=(gts-gts[0])*1e-9
    p=np.stack([np.interp(t,tg,P[:,i]) for i in range(3)],1)
    i=np.clip(np.searchsorted(tg,t),0,len(tg)-1)
    return p,Q[i]
def write_tum(path,ts,p,qwxyz):
    with open(path,'w') as f:
        f.write('# timestamp tx ty tz qx qy qz qw\n')
        for t,a,q in zip(ts,p,qwxyz):
            f.write('%.9f %.6f %.6f %.6f %.7f %.7f %.7f %.7f\n'%(t*1e-9,a[0],a[1],a[2],q[1],q[2],q[3],q[0]))
