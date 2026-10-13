import csv,json,pathlib,statistics,sys,collections
R=pathlib.Path(sys.argv[1])
rows=[json.loads(l) for l in (R/'raw.jsonl').read_text().splitlines()]
groups=collections.defaultdict(list)
for r in rows:
 if r['accepted'] and r['command_pct']>0:groups[(r['pass'],r['command_pct'],r['settling_target_seconds'])].append(r)
summaries=[]
for (direction,pct,settle),rs in groups.items():
 d={'pass':direction,'command_pct':pct,'settling_target_seconds':settle,'windows':len(rs),'published_sample_count':sum(r['samples'] for r in rs),'unique_exposures_verified':False}
 for field in ('lux','cct','cct_planck_K','x','y'):
  vs=[r[field] for r in rs];d.update({field+'_window_means_'+key:value for key,value in [('mean',statistics.mean(vs)),('min',min(vs)),('max',max(vs)),('range',max(vs)-min(vs)),('sample_sd',statistics.stdev(vs) if len(vs)>1 else None)]})
 d.update(lux_overall_min=min(r['lux_min'] for r in rs),lux_overall_max=max(r['lux_max'] for r in rs),max_within_window_peak_to_peak_pct=max(r['lux_peak_to_peak_pct'] for r in rs),max_exposure_averaged_modulation_pct=max(r['exposure_averaged_modulation_pct'] for r in rs))
 d['lux_window_means_cv_pct']=100*d['lux_window_means_sample_sd']/d['lux_window_means_mean'] if d['lux_window_means_sample_sd'] is not None else None
 summaries.append(d)
def csvout(name,rs):
 keys=list(dict.fromkeys(k for r in rs for k in r))
 with (R/name).open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rs)
csvout('setting-summary.csv',summaries)
curve=[]
for pct in range(1,101):
 a=next((r for r in summaries if r['pass']=='ascending' and r['command_pct']==pct),None)
 b=next((r for r in summaries if r['pass']=='descending' and r['command_pct']==pct),None)
 if not a:continue
 row={'command_pct':pct}
 for label,r in [('ascending',a),('descending',b)]:
  if r:
   row.update({label+'_'+k:v for k,v in r.items() if k not in ('pass','command_pct')})
 if b:row.update(descending_minus_ascending_lux=b['lux_window_means_mean']-a['lux_window_means_mean'],descending_minus_ascending_cct_planck_K=b['cct_planck_K_window_means_mean']-a['cct_planck_K_window_means_mean'])
 curve.append(row)
csvout('curve.csv',curve)
with (R/'all-captures.csv').open() as f:exported=list(csv.DictReader(f))
assert len(exported)==len(rows)
for r in rows:
 if r.get('mqtt_payload_verbatim'):
  for k,v in json.loads(r['mqtt_payload_verbatim']).items():assert r[k]==v
(R/'export-audit.json').write_text(json.dumps({'raw_records':len(rows),'csv_records':len(exported),'accepted':sum(r['accepted'] for r in rows),'all_published_fields_retained':True,'ascending_points':len(curve),'summary_groups':len(summaries)},indent=2))
print(json.dumps({'records':len(rows),'ascending_points':len(curve),'endpoint_summaries':[r for r in summaries if r['pass'].startswith('endpoint') or (r['pass']=='ascending' and r['command_pct'] in (1,2,5,100))]},indent=2))
