"""Audit fresh captures and calculate direction, variation, and waveform summaries."""
import pathlib,sys,json,csv,collections,statistics,math
import numpy as np
R=pathlib.Path(sys.argv[1]);raw=[json.loads(l) for l in (R/'raw.jsonl').read_text().splitlines()];rows=[r['metadata'] for r in raw]
def write(name,rs):
 if not rs:return
 keys=list(dict.fromkeys(k for r in rs for k in r))
 with (R/name).open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rs)
wave=[];capture_analysis=[];samples_count=0
for record in raw:
 r=record['metadata'];samples=[]
 for line in record['serial_lines_verbatim']:
  if line.startswith('S,'):
   v=line.split(',');samples.append([int(v[1])/1e6,float(v[5]),int(v[4])])
 samples_count+=len(samples)
 detail={k:r.get(k) for k in ('time_utc','request_id','pass','command_pct','mode','window_index','settling_target_seconds','settling_elapsed_seconds','accepted')}
 for col,k in ((5,'lux'),(6,'x'),(7,'y'),(8,'cct')):
  values=[float(line.split(',')[col]) for line in record['serial_lines_verbatim'] if line.startswith('S,') and line.split(',')[col]]
  values=[v for v in values if math.isfinite(v)]
  if values:
   detail.update({k+'_individual_'+name:value for name,value in [('count',len(values)),('mean',statistics.mean(values)),('min',min(values)),('max',max(values)),('range',max(values)-min(values)),('sample_sd',statistics.stdev(values) if len(values)>1 else None)]})
 capture_analysis.append(detail)
 if r['mode']!='fast' or not samples:continue
 a=np.array(samples);t=a[:,0];y=a[:,1];mu=float(np.mean(y));dt=np.diff(t);med=float(np.median(dt));fs=1/med;nyquist=fs/2
 qmax=float(np.max(.00215*2048*2**a[:,2]));qmin=float(np.min(.00215*2048*2**a[:,2]))
 out={k:r[k] for k in ('time_utc','request_id','pass','command_pct','window_index','settling_target_seconds','settling_elapsed_seconds','accepted')}
 out.update(samples=len(y),mean_lux=mu,min_lux=float(np.min(y)),max_lux=float(np.max(y)),sample_sd_lux=float(np.std(y,ddof=1)),median_interval_seconds=med,max_interval_seconds=float(np.max(dt)),interval_cv_pct=100*float(np.std(dt,ddof=1))/float(np.mean(dt)),mean_sample_rate_hz=r.get('actual_sample_rate_hz'),median_cadence_hz=fs,nominal_nyquist_hz=nyquist,lux_quantization_step_min=qmin,lux_quantization_step_max=qmax,mean_in_quantization_steps=mu/qmax if qmax else None,low_signal_quantization_screen=mu<10*qmax,fast_flicker_excluded=False,certified_flicker_metrics_available=False)
 if np.max(y)+np.min(y)>0:out['observed_modulation_pct']=100*float(np.ptp(y))/(float(np.max(y))+float(np.min(y)))
 # Timestamp-based spectral candidate; above-band light modulation can alias.
 # Do not interpolate high frequencies near Nyquist, where interpolation distorts amplitude.
 if mu>0 and len(y)>10:
  freq=np.arange(1.,r['actual_sample_rate_hz']/2,.2)
  center=y-np.mean(y)
  kernel=np.exp(-2j*np.pi*np.outer(freq,t))
  power=np.abs(kernel @ (center*np.hanning(len(center))))**2
  idx=int(np.argmax(power));candidate=float(freq[idx])
  out['dominant_frequency_candidate_hz']=candidate
  out['candidate_within_conservative_band']=candidate < .8*r['actual_sample_rate_hz']/2
  out['candidate_fraction_of_scanned_power']=float(power[idx]/sum(power)) if sum(power) else None
  for hz in (100,120):
   eligible=hz<r['actual_sample_rate_hz']/2
   out[f'{hz}Hz_within_nominal_band']=eligible
   out[f'{hz}Hz_within_conservative_band']=hz<.8*r['actual_sample_rate_hz']/2
   if eligible:
    matrix=np.column_stack([np.ones(len(t)),t-t.mean(),np.cos(2*np.pi*hz*t),np.sin(2*np.pi*hz*t)])
    coef=np.linalg.lstsq(matrix,y,rcond=None)[0];out[f'{hz}Hz_component_amplitude_pct_of_mean']=100*float(np.hypot(coef[2],coef[3]))/mu
 wave.append(out)
write('flicker-waveform-summary.csv',wave)
write('capture-analysis.csv',capture_analysis)
groups=collections.defaultdict(list)
for r in rows:
 if r['accepted'] and r['mode']=='color' and r['command_pct']>0:groups[(r['pass'],r['command_pct'],r['settling_target_seconds'])].append(r)
sums=[]
for (direction,pct,settle),rs in groups.items():
 d={'pass':direction,'command_pct':pct,'settling_target_seconds':settle,'windows':len(rs),'samples':sum(r['samples'] for r in rs)}
 for k in ('lux','cct','cct_planck_K','x','y','uv_distance'):
  vs=[r[k] for r in rs if k in r]
  if vs:
   d[k+'_window_means_count']=len(vs)
   d.update({k+'_window_means_'+name:v for name,v in [('mean',statistics.mean(vs)),('min',min(vs)),('max',max(vs)),('range',max(vs)-min(vs)),('sample_sd',statistics.stdev(vs) if len(vs)>1 else None)]})
 d.update(lux_overall_min=min(r['lux_min'] for r in rs),lux_overall_max=max(r['lux_max'] for r in rs),max_within_window_peak_to_peak_pct=max(r['lux_peak_to_peak_pct'] for r in rs),max_exposure_averaged_modulation_pct=max(r['exposure_averaged_modulation_pct'] for r in rs))
 d['lux_window_means_cv_pct']=100*d['lux_window_means_sample_sd']/d['lux_window_means_mean'] if d['lux_window_means_sample_sd'] is not None else None
 sums.append(d)
write('setting-summary.csv',sums)
comparisons=[]
for prefix,settings,checkpoints in [('endpoint',[1,2,5],[15,45]),('midrange',[30,60],[15,45])]:
 for pct in settings:
  for checkpoint in checkpoints:
   a=next((d for d in sums if d['pass']==prefix+'_from_high' and d['command_pct']==pct and d['settling_target_seconds']==checkpoint),None)
   b=next((d for d in sums if d['pass']==prefix+'_from_off_ascending' and d['command_pct']==pct and d['settling_target_seconds']==checkpoint),None)
   if not a or not b:continue
   d={'check':prefix,'command_pct':pct,'settling_target_seconds':checkpoint}
   for label,r in [('from_high',a),('from_off_ascending',b)]:
    for k in ('windows','samples','lux_window_means_mean','lux_window_means_range','cct_planck_K_window_means_mean','cct_planck_K_window_means_range'):
     d[label+'_'+k]=r.get(k)
   d.update(from_off_minus_from_high_lux=b['lux_window_means_mean']-a['lux_window_means_mean'],from_off_minus_from_high_lux_pct=100*(b['lux_window_means_mean']-a['lux_window_means_mean'])/a['lux_window_means_mean'],from_off_minus_from_high_cct_planck_K=(b['cct_planck_K_window_means_mean']-a['cct_planck_K_window_means_mean']) if 'cct_planck_K_window_means_mean' in b and 'cct_planck_K_window_means_mean' in a else None)
   comparisons.append(d)
write('direction-settling-comparison.csv',comparisons)

curve=[]
for pct in range(1,101):
 a=next((d for d in sums if d['pass']=='ascending' and d['command_pct']==pct),None)
 b=next((d for d in sums if d['pass']=='descending' and d['command_pct']==pct),None)
 if not a:continue
 d={'command_pct':pct}
 for label,r in [('ascending',a),('descending',b)]:
  if r:d.update({label+'_'+k:v for k,v in r.items() if k not in ('pass','command_pct')})
 if b:d.update(descending_minus_ascending_lux=b['lux_window_means_mean']-a['lux_window_means_mean'],directional_lux_difference_pct_of_ascending=100*(b['lux_window_means_mean']-a['lux_window_means_mean'])/a['lux_window_means_mean'],descending_minus_ascending_cct_planck_K=(b['cct_planck_K_window_means_mean']-a['cct_planck_K_window_means_mean']) if 'cct_planck_K_window_means_mean' in b and 'cct_planck_K_window_means_mean' in a else None)
 for label in ('ascending','descending'):
  wr=next((q for q in wave if q['pass']==label and q['command_pct']==pct and q['accepted']),None)
  if wr:d.update({label+'_fast_'+k:v for k,v in wr.items() if k not in ('pass','command_pct','request_id')})
 curve.append(d)
write('curve.csv',curve)
with (R/'all-captures.csv').open() as f:captures=list(csv.DictReader(f))
with (R/'individual-samples.csv').open() as f:sample_csv_count=sum(1 for _ in csv.DictReader(f))
assert len(captures)==len(rows)
assert sample_csv_count==samples_count
for source,exported in zip(rows,captures):
 for key,value in source.items():
  assert exported[key]==('' if value is None else str(value)),(source['request_id'],key,value,exported.get(key))
with (R/'individual-samples.csv').open() as f:
 reader=csv.DictReader(f)
 for rec in raw:
  meta=rec['metadata'];i=0
  for line in rec['serial_lines_verbatim']:
   if not line.startswith('S,'):continue
   v=line.split(',');sample={'elapsed_us':int(v[1]),'raw_ch1':int(v[2]),'counter':int(v[3]),'exponent':int(v[4]),**{key:float(value) if value else None for key,value in zip(('lux','x','y','cct'),v[5:])}}
   expected={key:meta[key] for key in ('time_utc','request_id','pass','command_pct','mode','window_index')}
   expected.update(sample_index=i,conversion_us_per_channel=meta.get('conversion_us_per_channel'),**sample);exported=next(reader)
   for key,value in expected.items():assert exported[key]==('' if value is None else str(value)),(meta['request_id'],i,key)
   i+=1
 assert next(reader,None) is None

for rec in raw:
 if rec.get('mqtt_payload_verbatim'):
  for k,v in json.loads(rec['mqtt_payload_verbatim']).items():assert rec['metadata'][k]==v
 for line in rec['serial_lines_verbatim']:
  if line.startswith('{'):
   obj=json.loads(line)
   if obj.get('type') in ('begin','end'):
    for k,v in obj.items():
     if k not in ('type',):assert rec['metadata'][k]==v,(k,v,rec['metadata'].get(k))
audit={'captures':len(rows),'individual_samples':samples_count,'accepted_captures':sum(r['accepted'] for r in rows),'ascending_points':len(curve),'descending_points':sum(d['pass']=='descending' for d in sums),'all_recorded_fields_retained':True,'capture_csv_reconciled':True,'individual_sample_csv_reconciled':True,'capture_values_reconciled':True,'individual_sample_values_reconciled':True,'unique_request_ids':len({r['request_id'] for r in rows})}
(R/'export-audit.json').write_text(json.dumps(audit,indent=2));print(json.dumps(audit))
