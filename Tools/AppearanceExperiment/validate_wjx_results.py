#!/usr/bin/env python3
"""Independently audit the published aggregate using XLSX ZIP/XML and stdlib.

No openpyxl, NumPy or production analysis functions are used. Never emits row
answers, participant identifiers or IP addresses. Intended for this fixed-order
32-question export, not arbitrary WJX questionnaires.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import xml.etree.ElementTree as ET
from zipfile import ZipFile

NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def rows_from_xml(path):
    with ZipFile(path) as book:
        strings = []
        if 'xl/sharedStrings.xml' in book.namelist():
            for item in ET.fromstring(book.read('xl/sharedStrings.xml')).findall('x:si', NS):
                strings.append(''.join(item.itertext()))
        sheet = ET.fromstring(book.read('xl/worksheets/sheet1.xml'))
        if sheet.findall('.//x:f', NS):
            raise AssertionError('Unexpected formulas in raw export')
        rows = []
        for row in sheet.findall('x:sheetData/x:row', NS):
            cells = {}
            for c in row.findall('x:c', NS):
                col = re.match('[A-Z]+', c.attrib['r']).group()
                v = c.find('x:v', NS)
                if c.attrib.get('t') == 'inlineStr':
                    value = ''.join(c.find('x:is', NS).itertext())
                else:
                    value = v.text if v is not None else ''
                    if c.attrib.get('t') == 's': value = strings[int(value)]
                cells[col] = value
            rows.append(cells)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--analysis', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    r = json.loads(args.analysis.read_text())
    rows = rows_from_xml(args.input)
    qcols = {int(m.group(1)): col for col, val in rows[0].items()
             if (m := re.match(r'^(\d+)[.、．]', val))}
    assert set(qcols) == set(range(1, 33))
    raw = [{q: row.get(col, '') for q, col in qcols.items()} for row in rows[1:]]
    included = [row for row in raw if row[2] == '3' and row[3] == '1']
    assert len(raw) == r['total_records'] == 15
    assert len(included) == r['included_n'] == 15
    assert len({row[1] for row in raw}) == len(raw)
    assert r['order'] == ['N', 'E', 'A', 'S']
    source_sha = hashlib.sha256(args.input.read_bytes()).hexdigest()
    assert source_sha == r['source']['sha256']
    metrics = ['interruption', 'control', 'effort', 'satisfaction']
    for b, condition in enumerate(r['order']):
        for m, metric in enumerate(metrics):
            values = [int(row[8 + 5*b + m]) for row in included]
            assert all(1 <= v <= 7 for v in values)
            d = r['descriptive'][condition][metric]
            assert d['question'] == 8 + 5*b + m
            assert d['counts'] == [values.count(i) for i in range(1, 8)]
            assert math.isclose(d['mean'], statistics.mean(values), abs_tol=1e-12)
            assert math.isclose(d['sd'], statistics.stdev(values), abs_tol=1e-12)
            assert d['median'] == statistics.median(values)
    pvalues = []
    for pair in r['pairwise']:
        m = metrics.index(pair['metric']); other = r['order'].index(pair['comparison'][-1])
        delta = [int(row[23+m])-int(row[8+5*other+m]) for row in included]
        benefit = [-v for v in delta] if m in (0, 2) else delta
        better = sum(v > 0 for v in benefit); worse = sum(v < 0 for v in benefit)
        ties = sum(v == 0 for v in benefit); n = better + worse
        p = min(1., 2*sum(math.comb(n, k) for k in range(min(better, worse)+1))/2**n) if n else 1.
        assert (pair['better'], pair['ties'], pair['worse']) == (better, ties, worse)
        assert math.isclose(pair['mean_difference'], statistics.mean(delta), abs_tol=1e-12)
        assert math.isclose(pair['p_exact'], p, abs_tol=1e-12)
        pvalues.append(p)
    previous = 0.
    for rank, index in enumerate(sorted(range(len(pvalues)), key=pvalues.__getitem__)):
        previous = min(1., max(previous, (len(pvalues)-rank)*pvalues[index]))
        assert math.isclose(r['pairwise'][index]['p_holm'], previous, abs_tol=1e-12)
    counts = Counter(row[28] for row in included)
    for code, key in enumerate(['N', 'E', 'A', 'S', 'no_preference', 'none', 'cannot_judge'], 1):
        assert r['preferences'][key]['n'] == counts[str(code)]
    assert r['preferences']['missing']['n'] == 0
    empty = {'', '(空)', '（空）'}
    for q in (12, 17, 22, 27, 29, 30, 31, 32):
        assert r['quality']['open_answer_nonempty'][str(q)] == sum(row[q].strip() not in empty for row in included)
    significant = [f"{p['comparison']}:{p['metric']}" for p in r['pairwise'] if p['p_holm'] < .05]
    assert significant == ['S-E:interruption', 'S-A:interruption', 'S-A:effort']
    result = {'validated_at': datetime.now(timezone.utc).isoformat(), 'status': 'passed',
              'source_sha256': source_sha, 'analysis_sha256': hashlib.sha256(args.analysis.read_bytes()).hexdigest(),
              'reader': 'Python standard library ZIP/XML; independent of openpyxl and production analysis',
              'checks': ['32-question schema and 15 eligible distinct respondents',
                         '16 rating histograms, means, sample SDs and medians',
                         '12 paired direction counts and mean differences',
                         '12 exact sign-test p values by binomial coefficient summation',
                         '12 Holm-adjusted p values', 'All preference option counts',
                         'All eight open-question coverage counts', 'Exactly three adjusted contrasts below 0.05'],
              'limitations': ['Bootstrap intervals and Monte Carlo permutations are produced by the analysis script, not independently rerun here.',
                              'Q29 theme coding requires human review; this audit checks coverage only.',
                              'Paper originals and reported study context were not independently verified.']}
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': 'passed', 'checks': len(result['checks'])}))


if __name__ == '__main__':
    main()
