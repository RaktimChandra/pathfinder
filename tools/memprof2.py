import sys,tracemalloc,gc; sys.path.insert(0,'src'); import main as M, numpy as np
f=sys.argv[1]
orig={n:getattr(M,n) for n in ['parse_imu','triage','identify_platform','detect_static_start','attitude_vec','noise_schedule','translation','write_output']}
def wrap(n,fn):
    def g(*a,**k):
        tracemalloc.reset_peak(); c0=tracemalloc.get_traced_memory()[0]
        r=fn(*a,**k); c,p=tracemalloc.get_traced_memory(); print('%-20s start %.2f  peak %.2f  end %.2f MB'%(n,c0/1e6,p/1e6,c/1e6)); return r
    return g
for n,fn in orig.items(): setattr(M,n,wrap(n,fn))
gc.collect(); tracemalloc.start(); M.run(f,'/tmp/o.txt'); print('overall peak %.2f'%(tracemalloc.get_traced_memory()[1]/1e6))
