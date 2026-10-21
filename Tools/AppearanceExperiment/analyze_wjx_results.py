#!/usr/bin/env python3
"""Audit the 32-question WJX export and emit anonymous aggregate statistics.

The actual condition order must be supplied explicitly. This does not rewrite
frozen experimental schedules. Source answers and identifiers are never copied
to the public output. Optional row-level audit data must stay under StudyData.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.metadata
import itertools
import json
import math
from pathlib import Path
import re
import sys

import numpy as np
from openpyxl import load_workbook
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
METRICS = ('interruption', 'control', 'effort', 'satisfaction')
LABELS = {'interruption': '打断感', 'control': '控制感', 'effort': '投入努力', 'satisfaction': '满意度'}
LOWER_BETTER = {'interruption', 'effort'}
OPEN_QUESTIONS = (12, 17, 22, 27, 29, 30, 31, 32)
EMPTY = {'', '(空)', '（空）'}
SEED = 20261021
BOOTSTRAPS = 20000
PERMUTATIONS = 99999


def clean(value):
    if value is None:
        return ''
    return str(value).strip()


def missing(value):
    return clean(value) in EMPTY


def code(value, maximum):
    text = clean(value)
    if text in EMPTY:
        return None
    if not re.fullmatch(r'\d+(?:\.0+)?', text):
        raise ValueError('Expected numeric WJX option code; export must use 按序号.')
    answer = int(float(text))
    if not 1 <= answer <= maximum:
        raise ValueError(f'Option code outside 1..{maximum}: {answer}')
    return answer


def rating(value):
    answer = code(value, 8)
    return np.nan if answer in (None, 8) else float(answer)


def holm(p_values):
    values = np.asarray(p_values, dtype=float)
    order = np.argsort(values, kind='stable')
    adjusted = np.empty(len(values))
    adjusted[order] = np.minimum(1, np.maximum.accumulate(values[order] * np.arange(len(values), 0, -1)))
    return adjusted.tolist()


def wilson(k, n):
    if not n:
        return [None, None]
    z = float(stats.norm.ppf(.975)); p = k / n; den = 1 + z*z/n
    center = (p + z*z/(2*n))/den
    half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
    return [max(0., center-half), min(1., center+half)]


def describe(values):
    values = np.asarray(values, dtype=float); valid = values[np.isfinite(values)]
    counts = [int(np.sum(valid == score)) for score in range(1, 8)]
    return dict(n=int(len(valid)), missing=int(len(values)-len(valid)), counts=counts,
                mean=float(np.mean(valid)) if len(valid) else None,
                sd=float(np.std(valid, ddof=1)) if len(valid)>1 else None,
                median=float(np.median(valid)) if len(valid) else None,
                q1=float(np.quantile(valid,.25)) if len(valid) else None,
                q3=float(np.quantile(valid,.75)) if len(valid) else None,
                low=sum(counts[:3]), neutral=counts[3], high=sum(counts[4:]),
                zero_variance=bool(len(valid)>0 and np.ptp(valid)==0))


def friedman_permutation(values, seed):
    values = np.asarray(values); values = values[np.isfinite(values).all(axis=1)]
    n, k = values.shape
    if n < 2:
        return dict(n=int(n), statistic=None, kendall_w=None, permutation_p=1., reason='Insufficient complete cases')
    ranks = stats.rankdata(values, axis=1)
    tie_sum = sum(sum(c**3-c for c in Counter(row).values()) for row in values)
    correction = 1-tie_sum/(n*(k**3-k))
    if correction == 0:
        return dict(n=int(n), statistic=0., kendall_w=0., permutation_p=1., reason='Every participant tied all conditions')
    def statistic(rank_sums):
        return (12/(n*k*(k+1))*np.sum(rank_sums**2,axis=-1)-3*n*(k+1))/correction
    observed = float(statistic(ranks.sum(axis=0)))
    scipy_stat = float(stats.friedmanchisquare(*values.T).statistic)
    if not np.isclose(observed, scipy_stat, atol=1e-10):
        raise AssertionError('Independent Friedman statistic does not match SciPy.')
    permutations = np.array(list(itertools.permutations(range(k))))
    rng = np.random.default_rng(seed); extreme = 0
    for start in range(0, PERMUTATIONS, 10000):
        batch = min(10000,PERMUTATIONS-start)
        indices = permutations[rng.integers(len(permutations),size=(batch,n))]
        permuted = np.take_along_axis(ranks[None,:,:],indices,axis=2)
        extreme += int(np.sum(statistic(permuted.sum(axis=1)) >= observed-1e-10))
    return dict(n=int(n), statistic=observed, df=k-1, kendall_w=observed/(n*(k-1)),
                permutation_p=(extreme+1)/(PERMUTATIONS+1), extreme_permutations=extreme,
                permutations=PERMUTATIONS, seed=seed, tie_correction=float(correction),
                scipy_statistic_matches=True)


def read_export(path):
    book = load_workbook(path,read_only=True,data_only=False)
    if len(book.worksheets) != 1:
        raise ValueError('Review additional workbook sheets before combining them.')
    sheet = book.worksheets[0]
    formula_count = sum(cell.data_type == 'f' for row in sheet for cell in row)
    if formula_count:
        raise ValueError('Formula-bearing export requires separate formula/cached-value review.')
    rows = list(sheet.values); headers = [clean(v) for v in rows[0]]
    questions = {}
    for index, header in enumerate(headers):
        match = re.match(r'^(\d+)[.、．]\s*(.+)',header)
        if match:
            number=int(match.group(1))
            if number in questions: raise ValueError('Duplicate question column')
            questions[number]=index
    if set(questions)!=set(range(1,33)):
        raise ValueError('Expected exactly Q1..Q32; questionnaire revision must be checked.')
    records=[]
    for number, row in enumerate(rows[1:],start=2):
        if all(missing(v) for v in row): continue
        records.append({'excel_row':number,'q':{q:row[index] if index<len(row) else None for q,index in questions.items()},
                        'metadata':{h:row[i] for i,h in enumerate(headers) if i not in questions.values()}})
    result=(records,{q:headers[i] for q,i in questions.items()},sheet.title,len(headers),formula_count)
    book.close()
    return result


def make_plots(result, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none'})
    output.mkdir(parents=True,exist_ok=True)
    order=result['order']; colors=['#9c2f48','#c85b64','#e9a7a7','#d8dde1','#a5cfc4','#57a98d','#167b65']
    fig,axes=plt.subplots(2,2,figsize=(12,8),sharex=True)
    for ax,metric in zip(axes.ravel(),METRICS):
        left=np.zeros(4)
        for score,color in enumerate(colors,start=1):
            values=np.array([result['descriptive'][c][metric]['counts'][score-1] for c in order])
            ax.barh(order,values,left=left,color=color,label=str(score),height=.65)
            for i,count in enumerate(values):
                if count: ax.text(left[i]+count/2,i,str(count),ha='center',va='center',fontsize=10)
            left+=values
        ax.invert_yaxis();ax.set_xlim(0,result['included_n']);ax.set_xticks(range(0,result['included_n']+1,3))
        ax.set_title(metric.title()+(' (lower is better)' if metric in LOWER_BETTER else ' (higher is better)'))
        ax.set_xlabel('Participants');ax.spines[['top','right']].set_visible(False)
    handles,labels=axes[0,0].get_legend_handles_labels()
    fig.legend(handles,labels,title='Response on the 1-7 scale',ncol=7,loc='lower center',bbox_to_anchor=(.5,.005))
    fig.suptitle('Observed response distributions | fixed order N -> E -> A -> S',fontsize=14)
    fig.tight_layout(rect=(0,.08,1,.96))
    for suffix in ['png','svg']:fig.savefig(output/('rating-distributions.'+suffix),dpi=180)
    plt.close(fig)
    prefs=result['preferences'];names=['N','E','A','S','No preference'];keys=['N','E','A','S','no_preference']
    fig,ax=plt.subplots(figsize=(9,4.5));values=[prefs[k]['n'] for k in keys]
    bars=ax.bar(names,values,color=['#727e89','#3978a8','#d58a47','#258e79','#bac3cb'],width=.65)
    ax.set_ylim(0,result['included_n']);ax.set_yticks(range(0,result['included_n']+1,3));ax.set_ylabel('Participants')
    for bar,key in zip(bars,keys):
        item=prefs[key];ax.text(bar.get_x()+bar.get_width()/2,item['n']+.25,f"{item['n']}/{result['included_n']} ({item['percent']:.1f}%)",ha='center')
    ax.set_title('Preferred condition | all consented formal responses');ax.spines[['top','right']].set_visible(False)
    fig.tight_layout()
    for suffix in ['png','svg']:fig.savefig(output/('condition-preference.'+suffix),dpi=180)
    plt.close(fig)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--private-out',type=Path)
    ap.add_argument('--order',nargs=4,choices=('N','E','A','S'),required=True)
    ap.add_argument('--order-source',required=True)
    ap.add_argument('--qualitative-source',choices=('researcher-summary','verbatim','mixed'),required=True)
    ap.add_argument('--context-json',type=Path)
    ap.add_argument('--no-plots',action='store_true')
    args=ap.parse_args()
    if set(args.order)!=set('NEAS'):ap.error('--order must contain every condition once.')
    if args.private_out and not args.private_out.resolve().is_relative_to((ROOT/'StudyData').resolve()):
        ap.error('Row-level outputs must remain inside ignored StudyData/.')
    records,questions,sheet,columns,formulas=read_export(args.input)
    context=json.loads(args.context_json.read_text()) if args.context_json else {}
    if context.get('actual_order',args.order)!=args.order:
        raise ValueError('Context confirmation and requested condition order disagree.')
    if context.get('source_sha256',hashlib.sha256(args.input.read_bytes()).hexdigest())!=hashlib.sha256(args.input.read_bytes()).hexdigest():
        raise ValueError('Context belongs to a different source workbook.')
    ids=[clean(r['q'][1]) for r in records]
    if any(not x for x in ids) or len(set(ids))!=len(ids):
        raise ValueError('Missing/duplicate participant identifiers: resolve explicitly before analysis.')
    exclusions=Counter(); included=[]
    for row in records:
        phase=code(row['q'][2],3); consent=code(row['q'][3],2)
        if consent!=1:exclusions['no_recorded_consent']+=1
        elif phase!=3:exclusions['not_formal']+=1
        else:included.append(row)
    if len(included)<2:raise ValueError('At least two eligible participants are required for this report.')
    n=len(included); x=np.array([[[rating(r['q'][8+b*5+m]) for m in range(4)] for b in range(4)] for r in included])
    result={'generated_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),
            'source':{'filename':args.input.name,'sha256':hashlib.sha256(args.input.read_bytes()).hexdigest(),
                      'questionnaire_id':'389439995','sheet':sheet,'columns':columns,'formula_count':formulas,
                      'acquisition':'User-supplied WJX export from paper transcription; not a fresh direct website download.'},
            'order':args.order,'order_source':args.order_source,'qualitative_source':args.qualitative_source,
            'research_context':context,
            'total_records':len(records),'included_n':n,'exclusions':dict(exclusions),
            'questions':questions,'descriptive':{},'pairwise':[],'friedman':{},
            'versions':{name:importlib.metadata.version(name) for name in ['numpy','openpyxl','scipy','matplotlib']},
            'methods':{'seed':SEED,'bootstrap_replicates':BOOTSTRAPS,'bootstrap_unit':'participant, preserving all four conditions',
                       'bootstrap_interval':'percentile 95%; unadjusted; mean score differences are descriptive ordinal-scale summaries',
                       'pairwise_test':'two-sided exact binomial sign test on non-tied paired differences',
                       'pairwise_family':'all 12 S-vs-N/E/A by four items; Holm adjusted',
                       'omnibus_family':'four exploratory Friedman participant-wise label permutation tests; Holm adjusted',
                       'causal_identification':False,'fixed_order_confounding':True,'preference_ci':'Wilson 95%, denominator all included participants'}}
    for b,condition in enumerate(args.order):
        result['descriptive'][condition]={metric:dict(question=8+b*5+m,**describe(x[:,b,m])) for m,metric in enumerate(METRICS)}
    s=args.order.index('S'); rng=np.random.default_rng(SEED)
    sampled_rows=rng.integers(n,size=(BOOTSTRAPS,n))
    for metric_index,metric in enumerate(METRICS):
        for other in ['N','E','A']:
            delta=x[:,s,metric_index]-x[:,args.order.index(other),metric_index]
            finite=delta[np.isfinite(delta)]; benefit=-finite if metric in LOWER_BETTER else finite
            better=int(sum(benefit>0)); worse=int(sum(benefit<0)); ties=int(sum(benefit==0)); effective=better+worse
            p=float(stats.binomtest(better,effective,.5).pvalue) if effective else 1.
            if effective:
                ci=stats.binomtest(better,effective).proportion_ci(.95,method='exact')
                effect=(better-worse)/effective; effect_ci=[2*ci.low-1,2*ci.high-1]
            else:effect=None;effect_ci=[None,None]
            with np.errstate(invalid='ignore'):
                means=np.nanmean(delta[sampled_rows],axis=1)
            means=means[np.isfinite(means)]
            result['pairwise'].append(dict(metric=metric,comparison='S-'+other,n=int(len(finite)),better=better,worse=worse,ties=ties,
                non_tied_n=effective,mean_difference=float(np.mean(finite)) if len(finite) else None,
                median_difference=float(np.median(finite)) if len(finite) else None,
                mean_difference_ci95=np.quantile(means,[.025,.975]).tolist() if len(means) else [None,None],
                sign_effect=effect,sign_effect_ci95=effect_ci,p_exact=p))
        result['friedman'][metric]=friedman_permutation(x[:,:,metric_index],SEED+metric_index+1)
        complete=x[:,:,metric_index]
        complete=complete[np.isfinite(complete).all(axis=1)]
        if len(complete)>=2:
            ranks=stats.rankdata(complete,axis=1); k=4; nc=len(complete)
            indices=sampled_rows if nc==n else np.random.default_rng(SEED+100+metric_index).integers(nc,size=(BOOTSTRAPS,nc))
            rank_sums=ranks[indices].sum(axis=1)
            participant_ties=np.array([sum(c**3-c for c in Counter(row).values()) for row in complete])
            corrections=1-participant_ties[indices].sum(axis=1)/(nc*(k**3-k))
            valid=corrections>0
            ws=(12/(nc*k*(k+1))*np.sum(rank_sums[valid]**2,axis=1)-3*nc*(k+1))/corrections[valid]/(nc*(k-1))
            result['friedman'][metric]['kendall_w_bootstrap_ci95']=np.quantile(ws,[.025,.975]).tolist() if len(ws) else [None,None]
    for item,p in zip(result['pairwise'],holm([v['p_exact'] for v in result['pairwise']])):item['p_holm']=p
    for metric,p in zip(METRICS,holm([result['friedman'][m]['permutation_p'] for m in METRICS])):result['friedman'][metric]['p_holm']=p
    option_counts={}
    for q,maximum in [(2,3),(3,2),(4,5),(5,3),(6,3),(28,7)]:
        counts=Counter('missing' if missing(r['q'][q]) else str(code(r['q'][q],maximum)) for r in included)
        option_counts[str(q)]=dict(counts)
    result['categorical_counts']=option_counts
    pref_counts=Counter()
    for r in included:
        pref=code(r['q'][28],7)
        key=args.order[pref-1] if pref in (1,2,3,4) else {5:'no_preference',6:'none',7:'cannot_judge',None:'missing'}[pref]
        pref_counts[key]+=1
    result['preferences']={key:dict(n=pref_counts[key],percent=100*pref_counts[key]/n,ci95=wilson(pref_counts[key],n))
                           for key in ['N','E','A','S','no_preference','none','cannot_judge','missing']}
    # Explicit, auditable coding of the six researcher-summary formulations in this export.
    rules={'execute_then_repair':['先按指令执行'],'selective_feels_easier':['省心'],
           'native_selective_not_distinct':['区别不明显'],'prefers_native_spontaneity':['原味AI'],
           'limited_vr_relevance':['不太会用到VR'],'novelty_overwhelms_comparison':['新鲜']}
    themes=Counter();theme_preferences={};unclassified=0;private_codes=[]
    for r in included:
        text=clean(r['q'][29]);tags=[tag for tag,words in rules.items() if any(word in text for word in words)]
        if not missing(text) and not tags:unclassified+=1
        themes.update(tags);private_codes.append({'excel_row':r['excel_row'],'tags':tags})
        choice=code(r['q'][28],7)
        preferred=args.order[choice-1] if choice in (1,2,3,4) else {5:'no_preference',6:'none',7:'cannot_judge',None:'missing'}[choice]
        for tag in tags:theme_preferences.setdefault(tag,Counter())[preferred]+=1
    result['qualitative']={'rules':rules,'counts':dict(themes),'unclassified_nonempty':unclassified,
                           'preference_counts':{tag:dict(counts) for tag,counts in theme_preferences.items()},
                           'unit':'participant; each theme counted at most once per participant; multiple labels allowed',
                           'verbatim_quotes_used':False}
    signatures=Counter(tuple(np.nan_to_num(row,nan=-1).flatten()) for row in x)
    times=[clean(r['metadata'].get('提交答卷时间')) for r in records]
    result['quality']={'unique_participant_ids':len(set(ids)),'missing_participant_ids':0,'duplicate_participant_ids':0,
       'canonical_ids':sum(bool(re.fullmatch(r'P\d{3}',i)) for i in ids),
       'total_rating_cells':int(x.size),'valid_rating_cells':int(np.isfinite(x).sum()),'missing_rating_cells':int(np.isnan(x).sum()),
       'option8_cells':sum(code(r['q'][8+b*5+m],8)==8 for r in included for b in range(4) for m in range(4)),
       'complete_four_round_participants':int(np.isfinite(x).all(axis=(1,2)).sum()),
       'identical_rating_vector_groups':sum(c>1 for c in signatures.values()),
       'participants_in_identical_rating_vector_groups':sum(c for c in signatures.values() if c>1),
       'duplicate_score_vectors_excluded':False,
       'open_answer_nonempty':{str(q):sum(not missing(r['q'][q]) for r in included) for q in OPEN_QUESTIONS},
       'q29_distinct_summary_texts':len(set(clean(r['q'][29]) for r in included if not missing(r['q'][29]))),
       'zero_variance_rating_questions':[v['question'] for ds in result['descriptive'].values() for v in ds.values() if v['zero_variance']],
       'recorded_entry_time_min':min(times),'recorded_entry_time_max':max(times),
       'distinct_recorded_ips':len(set(clean(r['metadata'].get('来自IP')) for r in records)),
       'source_counts':dict(Counter(clean(r['metadata'].get('来源')) for r in records)),
       'timestamps_are_transcription_metadata':True,'paper_originals_independently_verified':False}
    if args.private_out:
        args.private_out.mkdir(parents=True,exist_ok=True)
        private={'condition_order':args.order,'records':[{'excel_row':r['excel_row'],'participant_id':clean(r['q'][1]),'ratings':x[i].tolist(),'preference_code':code(r['q'][28],7)} for i,r in enumerate(included)],'qualitative_codes':private_codes}
        (args.private_out/'row-audit-private.json').write_text(json.dumps(private,ensure_ascii=False,indent=2)+'\n')
    args.out.mkdir(parents=True,exist_ok=True)
    (args.out/'analysis.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    if not args.no_plots:make_plots(result,args.out/'figures')
    print(json.dumps({'included':n,'valid_ratings':result['quality']['valid_rating_cells'],'out':str(args.out),'source_sha256':result['source']['sha256']},ensure_ascii=False))


if __name__=='__main__':
    main()
