#!/usr/bin/env python3
"""Target only a specified AppearanceLab process for an X11 desktop UI check.

This is ordinary desktop GUI automation, not Codex's built-in browser. It never
discovers credentials, controls unrelated applications, or submits study data.
"""
import argparse
import ctypes as C
import ctypes.util
import json
import os
from pathlib import Path
import time

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pid',required=True,type=int)
parser.add_argument('--action',choices=('inspect','capture','click','key','type'),default='inspect')
parser.add_argument('--x',type=float)
parser.add_argument('--y',type=float)
parser.add_argument('--text')
parser.add_argument('--output',type=Path)
args=parser.parse_args()
cmdline=Path(f'/proc/{args.pid}/cmdline').read_bytes().split(b'\0')
if not cmdline or Path(os.fsdecode(cmdline[0])).name!='AppearanceLab.x86_64':
    parser.error('The requested process is not AppearanceLab.x86_64; no input sent.')

x=C.CDLL(ctypes.util.find_library('X11'))
xt=C.CDLL(ctypes.util.find_library('Xtst'))
D=C.c_void_p;W=C.c_ulong;I=C.c_int;U=C.c_uint
x.XOpenDisplay.argtypes=[C.c_char_p];x.XOpenDisplay.restype=D
x.XDefaultRootWindow.argtypes=[D];x.XDefaultRootWindow.restype=W
x.XInternAtom.argtypes=[D,C.c_char_p,I];x.XInternAtom.restype=W
x.XGetWindowProperty.argtypes=[D,W,W,C.c_long,C.c_long,I,W,C.POINTER(W),C.POINTER(I),C.POINTER(W),C.POINTER(W),C.POINTER(C.POINTER(C.c_ubyte))]
x.XFree.argtypes=[D]
x.XGetGeometry.argtypes=[D,W,C.POINTER(W),C.POINTER(I),C.POINTER(I),C.POINTER(U),C.POINTER(U),C.POINTER(U),C.POINTER(U)]
x.XQueryTree.argtypes=[D,W,C.POINTER(W),C.POINTER(W),C.POINTER(C.POINTER(W)),C.POINTER(U)]
x.XTranslateCoordinates.argtypes=[D,W,W,I,I,C.POINTER(I),C.POINTER(I),C.POINTER(W)]
x.XRaiseWindow.argtypes=[D,W];x.XSetInputFocus.argtypes=[D,W,I,W];x.XFlush.argtypes=[D]
x.XStringToKeysym.argtypes=[C.c_char_p];x.XStringToKeysym.restype=W
x.XKeysymToKeycode.argtypes=[D,W];x.XKeysymToKeycode.restype=C.c_ubyte
x.XCloseDisplay.argtypes=[D]
xt.XTestFakeMotionEvent.argtypes=[D,I,I,I,W]
xt.XTestFakeButtonEvent.argtypes=[D,U,I,W]
xt.XTestFakeKeyEvent.argtypes=[D,U,I,W]
display=x.XOpenDisplay(None)
if not display:parser.error('Cannot connect to the specified X11 display.')
root=x.XDefaultRootWindow(display)

def prop(window,name):
    atom=x.XInternAtom(display,name.encode(),True)
    if not atom:return []
    actual=W();fmt=I();count=W();remaining=W();data=C.POINTER(C.c_ubyte)()
    result=x.XGetWindowProperty(display,window,atom,0,4096,False,0,C.byref(actual),C.byref(fmt),C.byref(count),C.byref(remaining),C.byref(data))
    if result or not data:return []
    try:
        return list(C.cast(data,C.POINTER(W))[:count.value]) if fmt.value==32 else []
    finally:x.XFree(data)

clients=prop(root,'_NET_CLIENT_LIST')
if not clients:
    parent=W();returned_root=W();children=C.POINTER(W)();child_count=U()
    if x.XQueryTree(display,root,C.byref(returned_root),C.byref(parent),C.byref(children),C.byref(child_count)) and children:
        clients=list(children[:child_count.value]);x.XFree(children)
windows=[w for w in clients if prop(w,'_NET_WM_PID')==[args.pid]]
if len(windows)!=1:
    x.XCloseDisplay(display);parser.error(f'Expected one managed window for this Unity PID, found {len(windows)}; no input sent.')
window=windows[0]
r=W();wx=I();wy=I();width=U();height=U();border=U();depth=U()
if not x.XGetGeometry(display,window,C.byref(r),C.byref(wx),C.byref(wy),C.byref(width),C.byref(height),C.byref(border),C.byref(depth)):
    parser.error('Cannot read Unity window geometry.')
screen_x=I();screen_y=I();child=W()
x.XTranslateCoordinates(display,window,root,0,0,C.byref(screen_x),C.byref(screen_y),C.byref(child))
report={'pid':args.pid,'window':window,'client_geometry':[screen_x.value,screen_y.value,width.value,height.value],'action':args.action}

def key(name,down):
    sym=x.XStringToKeysym(name.encode('ascii'))
    code=x.XKeysymToKeycode(display,sym)
    if not code:raise ValueError('Unsupported keysym '+name)
    xt.XTestFakeKeyEvent(display,code,down,0);x.XFlush(display)

try:
    if args.action!='inspect':
        x.XRaiseWindow(display,window);x.XSetInputFocus(display,window,2,0);x.XFlush(display);time.sleep(.15)
    if args.action=='click':
        if args.x is None or args.y is None or not 0<=args.x<1440 or not 0<=args.y<900:
            parser.error('Provide x/y within the Unity 1440×900 design coordinates.')
        px=screen_x.value+round(args.x*width.value/1440)
        py=screen_y.value+round(args.y*height.value/900)
        xt.XTestFakeMotionEvent(display,-1,px,py,0)
        xt.XTestFakeButtonEvent(display,1,True,0);x.XFlush(display);time.sleep(.08)
        xt.XTestFakeButtonEvent(display,1,False,0);x.XFlush(display)
        report['design_point']=[args.x,args.y]
    elif args.action=='key':
        names=(args.text or '').split('+')
        if not names or not all(names):parser.error('Provide --text with an X keysym or a + separated chord.')
        for name in names:key(name,True)
        time.sleep(.06)
        for name in reversed(names):key(name,False)
        report['key']=args.text
    elif args.action=='type':
        text=args.text or ''
        if not text or len(text)>500 or any(ord(c)<32 or ord(c)>126 for c in text):
            parser.error('Typing accepts 1–500 printable ASCII characters only.')
        symbols={' ':'space','.':'period',',':'comma','-':'minus','_':'underscore',':':'colon',';':'semicolon','?':'question','!':'exclam','(':'parenleft',')':'parenright','/':'slash'}
        shifted=set('_:?!()')
        for char in text:
            shift=char.isupper() or char in shifted
            if shift:key('Shift_L',True)
            key(symbols.get(char,char),True);key(symbols.get(char,char),False)
            if shift:key('Shift_L',False)
            time.sleep(.01)
        report['typed_characters']=len(text)
    elif args.action=='capture':
        if args.output is None:parser.error('Provide --output for the Unity-window-only screenshot.')
        from PIL import ImageGrab
        time.sleep(.2)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        ImageGrab.grab(bbox=(screen_x.value,screen_y.value,screen_x.value+width.value,screen_y.value+height.value),xdisplay=os.environ.get('DISPLAY')).save(args.output)
        report['screenshot']=str(args.output)
    print(json.dumps(report))
finally:x.XCloseDisplay(display)
