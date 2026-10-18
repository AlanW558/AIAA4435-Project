"""Deterministic, seamless material sources. Run with Python + numpy + Pillow.
Grain runs along image V; floor maps 2 m / repeat, tabletop 1.8 m / repeat.
No external texture licenses or downloaded content.
"""
from pathlib import Path
import numpy as np
from PIL import Image
OUT = Path(__file__).resolve().parents[1] / 'Assets/Project/Textures/Room'
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(4435)

def save(name, a):
    Image.fromarray(np.uint8(np.clip(a, 0, 1)*255)).save(OUT / (name+'.png'))

def normal(name, h, strength):
    dx=(np.roll(h,-1,axis=1)-np.roll(h,1,axis=1))*strength
    dy=(np.roll(h,-1,axis=0)-np.roll(h,1,axis=0))*strength
    n=np.stack([-dx,-dy,np.ones_like(h)],axis=2)
    n/=np.linalg.norm(n,axis=2,keepdims=True)
    save(name,n*.5+.5)

# 2048 across grain × 4096 along grain, periodic frequencies avoid tile edges.
w,h=2048,4096
x=np.arange(w,dtype=np.float32)[None,:]/w
y=np.arange(h,dtype=np.float32)[:,None]/h
tau=2*np.pi
warp=.014*np.sin(tau*y)+.006*np.sin(tau*(3*y+x))+.003*np.sin(tau*(7*y-2*x))
q=x+warp
broad=np.sin(tau*(7*q+0.4*np.sin(tau*y)))
grain=np.sin(tau*(61*q+.25*np.sin(tau*2*y)))
fine=np.sin(tau*(173*q+.2*np.sin(tau*5*y)))
fibres=(.5+.5*np.sin(tau*391*q))**18
height=.45+.13*broad+.04*grain+.018*fine-.045*fibres
# Low-contrast oak; material tint supplies the final floor/table colour.
value=.86+.055*broad+.023*grain+.009*fine-.032*fibres
rgb=np.stack([value*1.025,value*.99,value*.935],axis=2)
save('Oak_Albedo_4K',rgb)
normal('Oak_Normal_4K',height,1.6)
# URP metallic map alpha = smoothness; wood stays dielectric.
mask=np.zeros((h,w,4),dtype=np.float32)
mask[:,:,3]=.26+.035*broad+.02*grain
save('Oak_Mask_4K',mask)
del rgb,mask,grain,broad,fine,fibres,height,value,q,warp
# Fine woven upholstery; a repeat represents 12 cm, not a whole chair.
n=1024
x=np.arange(n,dtype=np.float32)[None,:]/n
y=np.arange(n,dtype=np.float32)[:,None]/n
warp=(.5+.5*np.cos(tau*64*x))**2
weft=(.5+.5*np.cos(tau*64*y))**2
cross=np.sin(tau*32*x)*np.sin(tau*32*y)
height=.32*warp+.32*weft+.07*cross
noise=rng.normal(0,.008,(n,n)).astype(np.float32)
v=.89+.035*(warp+weft-1)+.014*cross+noise
save('Linen_Albedo_1K',np.stack([v,v*.984,v*.955],axis=2))
normal('Linen_Normal_1K',height,.6)
print('Generated',len(list(OUT.glob('*.png'))),'textures in',OUT)
