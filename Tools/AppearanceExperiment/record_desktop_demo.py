#!/usr/bin/env python3
"""Record one real, already-running Unity desktop debug window for 60 seconds."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import uuid


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--window-id',required=True,type=lambda x:int(x,0))
    p.add_argument('--size',default='1920x1043')
    p.add_argument('--runtime-dir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--scenario',choices=('appearance-v1','avatar-v2'),default='appearance-v1')
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    evidence=[];start=time.monotonic()
    def status():
        # Unity publishes by replacement; tolerate the brief file replacement interval.
        for _ in range(10):
            try:return json.loads((args.runtime_dir/'appearance-status.json').read_text())
            except (FileNotFoundError,json.JSONDecodeError):time.sleep(.03)
        raise RuntimeError('Runtime status unavailable.')
    initial=status()
    if initial.get('phase')!='debug' or initial.get('condition')!='S' or not initial.get('initialized') or initial.get('decision')!='READY':
        raise RuntimeError('Require a fresh initialized S debug session; no command sent.')
    if args.scenario=='avatar-v2' and initial.get('capability_profile')!='avatar-demo-v1':
        raise RuntimeError('The avatar-v2 scenario requires the isolated avatar demo profile.')
    session=initial['study_session_id']
    def at(seconds):
        while True:
            remaining=seconds-(time.monotonic()-start)
            if remaining<=0:return
            time.sleep(min(.2,remaining))
    def action(kind,value=None,text=None):
        command={'id':uuid.uuid4().hex,'study_session_id':session,'action':kind,'value':value,'text':text}
        temp=args.runtime_dir/'appearance-command.json.recording.tmp'
        temp.write_text(json.dumps(command,ensure_ascii=False)+'\n');temp.replace(args.runtime_dir/'appearance-command.json')
        deadline=time.monotonic()+25
        while time.monotonic()<deadline:
            s=status()
            if s.get('study_session_id')!=session or s.get('faulted'):raise RuntimeError('Demo runtime changed or faulted.')
            if s.get('command_id')==command['id']:
                if not s.get('command_accepted'):raise RuntimeError('Demo command rejected: '+s.get('command_error',''))
                if not s.get('busy') and not s.get('validating'):
                    event={'seconds':round(time.monotonic()-start,3),'action':kind,'value':value,'text':text,'status':s}
                    evidence.append(event);print(kind,s['decision'],s['observed'],flush=True);return s
            time.sleep(.1)
        raise RuntimeError('Demo action timed out; keep partial recording as failed evidence.')
    raw=args.output/'desktop-debug-raw.mp4'
    if raw.exists():raise RuntimeError('Use a new output directory; existing raw recording is preserved.')
    log=(args.output/'capture.log').open('w')
    recorder=subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','warning','-y','-f','x11grab','-window_id',str(args.window_id),
        '-video_size',args.size,'-framerate','30','-draw_mouse','0','-i',os.environ.get('DISPLAY',':1'),
        '-t','60','-vf','crop=iw:trunc(ih/2)*2','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(raw)],stderr=log)
    start=time.monotonic();passed=False
    try:
        if args.scenario=='avatar-v2':
            at(5);s=action('submit',text='把西装换成橙色运动装，保持当前人物、眼镜和大小。')
            if s['decision']!='ACT' or s['observed']['outfit']!='sport' or s['observed']['jacket_color']!='orange':
                raise RuntimeError('The requested sportswear was not actually applied.')
            at(16);s=action('submit',text='把大小比例设成 1.10，其余全部保持不变。')
            if abs(s['observed']['scale']-1.1)>.001:raise RuntimeError('Scale not applied.')
            at(25);s=action('submit',text='把衣服改成冷色，人物、运动装款式、眼镜和大小保持不变。')
            if s['decision']!='ASK':raise RuntimeError('The live model did not ask; do not label it as clarification.')
            option=next(o['id'] for o in s['question']['options'] if '蓝色' in o['label'])
            at(32);s=action('answer',value=option)
            if s['observed']['jacket_color']!='blue':raise RuntimeError('Blue selection was not applied.')
            before={k:v for k,v in s['observed'].items() if k!='revision'}
            at(40);s=action('submit',text='把整个形象全部替换为奶龙，使用奶龙的默认外观。')
            if s['decision']!='ACT' or s['observed']['avatar_id']!='nailong' or s['observed']['jacket_color']!='yellow':
                raise RuntimeError('The full mascot replacement was not applied.')
            at(49);s=action('undo',value='all')
            if {k:v for k,v in s['observed'].items() if k!='revision'}!=before:
                raise RuntimeError('Atomic replacement undo did not restore all five fields.')
            at(54);s=action('finish')
        else:
            at(5);s=action('submit',text='把衣服改成暖色，戴上眼镜，大小保持不变。')
            if s['decision']!='ASK':raise RuntimeError('This live model response did not ask; do not label it as a clarification demo.')
            option=next(o['id'] for o in s['question']['options'] if '橙色' in o['label'] and '眼镜' in o['label'])
            at(18);s=action('answer',value=option)
            if s['observed']['jacket_color']!='orange' or s['observed']['accessory']!='glasses':raise RuntimeError('Unexpected actual renderer state.')
            at(29);s=action('submit',text='把大小比例设成 1.10，颜色和眼镜保持不变。')
            if abs(s['observed']['scale']-1.1)>.001:raise RuntimeError('Scale not applied.')
            at(40);s=action('undo',value='jacket_color')
            if s['observed']['jacket_color']!='blue' or s['observed']['accessory']!='glasses' or abs(s['observed']['scale']-1.1)>.001:raise RuntimeError('Partial undo did not preserve other fields.')
            at(48);s=action('finish')
        if not s['finished'] or len(s['captures'])!=4:raise RuntimeError('Missing completion or renderer probes.')
        recorder.wait(timeout=70)
        if recorder.returncode:raise RuntimeError('Window recorder failed.')
        passed=True
    finally:
        if recorder.poll() is None:
            recorder.terminate();recorder.wait(timeout=10)
        log.close()
        manifest={'passed':passed,'phase':'debug','scenario':args.scenario,'capture_source':'Ubuntu Unity desktop window, fixed camera; not a headset recording',
            'session':session,'initial':initial,'events':evidence,'raw_video':raw.name}
        (args.output/'demo-events.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    print('Desktop debug recording completed.',flush=True)


if __name__=='__main__':main()
