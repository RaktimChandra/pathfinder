import sys,numpy as np
src,dst=sys.argv[1:3]
d=np.loadtxt(src,comments='#'); t=d[:,0]
ts=np.round(t*1e9).astype(np.int64)
# exact ns from text to avoid float rounding
with open(src) as f: tt=[l.split()[0] for l in f if l.strip() and not l.startswith('#')]
ts=np.array([int(x.split('.')[0])*1000000000+int((x.split('.')[1]+'000000000')[:9]) for x in tt],dtype=np.int64)
p=d[:,1:4]; q=d[:,[7,4,5,6]]
v=np.gradient(p,t,axis=0)
# light smoothing of finite-difference velocity (5-sample)
k=np.ones(5)/5; v=np.stack([np.convolve(v[:,j],k,'same') for j in range(3)],1)
with open(dst,'w') as f:
    f.write('#timestamp, p_RS_R_x [m], p_RS_R_y [m], p_RS_R_z [m], q_RS_w [], q_RS_x [], q_RS_y [], q_RS_z [], v_RS_R_x [m s^-1], v_RS_R_y [m s^-1], v_RS_R_z [m s^-1], b_w_RS_S_x [rad s^-1], b_w_RS_S_y [rad s^-1], b_w_RS_S_z [rad s^-1], b_a_RS_S_x [m s^-2], b_a_RS_S_y [m s^-2], b_a_RS_S_z [m s^-2]\n')
    for i in range(len(ts)):
        f.write('%d,%.6f,%.6f,%.6f,%.7f,%.7f,%.7f,%.7f,%.5f,%.5f,%.5f,0,0,0,0,0,0\n'%(ts[i],*p[i],*q[i],*v[i]))
print(dst,len(ts),'dur %.1f'%(t[-1]-t[0]),'dt med %.4f'%np.median(np.diff(t)))
