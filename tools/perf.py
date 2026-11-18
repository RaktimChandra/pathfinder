import sys,time,tracemalloc,os,gc
sys.path.insert(0,'src'); import main as M
import numpy as np
f=sys.argv[1]
dur=None
gc.collect(); tracemalloc.start()
t0=time.process_time(); w0=time.perf_counter()
M.run(f,'/tmp/perf_out.txt')
cpu=time.process_time()-t0; wall=time.perf_counter()-w0
cur,peak=tracemalloc.get_traced_memory(); tracemalloc.stop()
ts=np.loadtxt(f,delimiter=',',comments='#',usecols=0,dtype=np.int64); dur=(ts.max()-ts.min())*1e-9
print('%s dur %.1fs | peak heap %.2f MB | cpu %.3fs wall %.3fs | %.1f ms per 1s IMU (budget 20)'%(os.path.basename(f),dur,peak/1e6,cpu,wall,1000*cpu/dur))
