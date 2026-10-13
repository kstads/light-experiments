"""Summarize measured data without scaling to fixture specifications."""
import csv,json,pathlib,statistics
ROOT=pathlib.Path(__file__).resolve().parent
if not (ROOT/'capture-complete.json').exists(): raise SystemExit('Capture has not completed')
raw=[json.loads(l) for l in (ROOT/'raw.jsonl').read_text().splitlines()]
def aggregate(samples):
 result=dict(samples[0])
 for k in ['cct_planck_K','lux','x','y','uv_distance']:result[k]=statistics.mean(r[k] for r in samples)
 result['lux_min']=min(r['lux_min'] for r in samples);result['lux_max']=max(r['lux_max'] for r in samples)
 result['samples']=sum(r['samples'] for r in samples);result['capture_windows']=len(samples)
 result['window_peak_to_peak_percent']=max((r['lux_max']-r['lux_min'])/r['lux']*100 for r in samples)
 result['mean_spread_percent']=(max(r['lux'] for r in samples)-min(r['lux'] for r in samples))/result['lux']*100
 return result
asc=[aggregate([r for r in raw if r.get('command_pct')==p and r['pass'] in ['ascending','stability_ascending']]) for p in range(1,101)]
desc={p:aggregate([r for r in raw if r.get('command_pct')==p and r['pass'] in ['descending','stability_descending']]) for p in sorted({r['command_pct'] for r in raw if r['pass']=='descending'})}
assert [r['command_pct'] for r in asc]==list(range(1,101))
stability_floor=json.loads((ROOT/'stability-floor.json').read_text())
minimum=stability_floor['candidate_minimum_dimmer_pct']
excluded=stability_floor['excluded_dimmer_pcts']
if minimum is None:raise SystemExit('No stable low-end floor found; do not install the curve')
# Pool adjacent violations only to remove measurement-scale reversals. Keep raw values.
blocks=[]
for r in asc:
 p=r['command_pct']
 if p < minimum or p in excluded:continue
 values=[r['cct_planck_K']]
 if p in desc:values.append(desc[p]['cct_planck_K'])
 blocks.append({'p':[p],'sum':sum(values),'n':len(values)})
 while len(blocks)>1 and blocks[-2]['sum']/blocks[-2]['n']>blocks[-1]['sum']/blocks[-1]['n']:
  b=blocks.pop();a=blocks[-1];a['p']+=b['p'];a['sum']+=b['sum'];a['n']+=b['n']
fitted={p:b['sum']/b['n'] for b in blocks for p in b['p']}
rows=[]
for r in asc:
 p=r['command_pct']; d=desc.get(p); vals=[r['lux']]+([d['lux']] if d else [])
 rows.append({'dimmer_pct':p,'ascending_samples':r['samples'],'descending_samples':d['samples'] if d else '', 'descending_lux_min':d['lux_min'] if d else '', 'descending_lux_max':d['lux_max'] if d else '', 'descending_window_peak_to_peak_percent':round(d['window_peak_to_peak_percent'],2) if d else '', 'descending_between_window_spread_percent':round(d['mean_spread_percent'],2) if d else '', 'ascending_lux_min':r['lux_min'],'ascending_lux_max':r['lux_max'],'ascending_window_peak_to_peak_percent':round(r['window_peak_to_peak_percent'],2),'ascending_between_window_spread_percent':round(r['mean_spread_percent'],2),'lookup_eligible':p not in excluded and p>=minimum,'sensor_variation_screen':('variation_detected' if max(r['window_peak_to_peak_percent'],r['mean_spread_percent'],d['window_peak_to_peak_percent'] if d else 0,d['mean_spread_percent'] if d else 0)>5 else 'variation_not_detected'),'fast_flicker_excluded':False,'ha_brightness':r['ha_brightness'],'cct_kelvin':round(fitted[p],1) if p in fitted else '','ascending_cct_kelvin':r['cct_planck_K'],'descending_cct_kelvin':d['cct_planck_K'] if d else '', 'lux_mean':round(statistics.mean(vals),4),'ascending_lux':round(r['lux'],4),'descending_lux':round(d['lux'],4) if d else '', 'repeat_delta_kelvin':abs(r['cct_planck_K']-d['cct_planck_K']) if d else '', 'uv_distance':round(r['uv_distance'],8)})
with (ROOT/'curve.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
raw_fields=sorted(set().union(*(set(r) for r in raw)))
with (ROOT/'raw-readings.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=raw_fields);w.writeheader();w.writerows(raw)
curve=[[r['cct_kelvin'],r['dimmer_pct']] for r in rows if r['dimmer_pct']>=minimum and r['dimmer_pct'] not in excluded]
# Collapse exact fitted plateaus to their lowest command before inversion.
inverse=[]
for b in blocks:
 kelvin=round(b['sum']/b['n'],1)
 if inverse and inverse[-1][0]==kelvin:continue
 inverse.append([kelvin,min(b['p'])])
metrics={'excluded_dimmer_pcts':excluded,'conservative_contiguous_floor_pct':stability_floor['conservative_contiguous_floor_pct'],'minimum_operating_dimmer_pct':minimum,'visible_flicker_boundary_confirmed':False,'points':len(asc),'descending_checks':len(desc),'minimum_kelvin':curve[0][0],'maximum_kelvin':curve[-1][0],'lux_at_1_pct':rows[0]['lux_mean'],'lux_at_100_pct':rows[-1]['lux_mean'],'maximum_repeat_delta_kelvin':max(r['repeat_delta_kelvin'] for r in rows if r['repeat_delta_kelvin']!=''),'median_repeat_delta_kelvin':statistics.median(r['repeat_delta_kelvin'] for r in rows if r['repeat_delta_kelvin']!=''),'maximum_repeat_lux_percent':max(abs(r['lux']-desc[r['command_pct']]['lux'])/max(r['lux'],1e-9)*100 for r in asc if r['command_pct'] in desc),'maximum_uv_distance':max(r['uv_distance'] for r in asc),'largest_monotonic_adjustment_kelvin':max(abs(fitted[r['command_pct']]-r['cct_planck_K']) for r in asc if r['command_pct'] in fitted),'ambient_baseline_valid':all('error' not in r for r in raw if r['pass'].startswith('baseline'))}
(ROOT/'curve.json').write_text(json.dumps({'metrics':metrics,'brightness_to_cct':curve,'cct_to_brightness':inverse},indent=2))
print(json.dumps(metrics,indent=2))
# Static publication/export plot via bundled matplotlib.
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,axs=plt.subplots(3,1,figsize=(9,10),sharex=False)
axs[0].plot([r['command_pct'] for r in asc],[r['cct_planck_K'] for r in asc],label='Ascending measured',color='#2962a3')
axs[0].scatter(list(desc),[r['cct_planck_K'] for r in desc.values()],label='Descending checks',color='#da8932',s=15)
axs[0].plot([r['dimmer_pct'] for r in rows if r['dimmer_pct']>=minimum and r['dimmer_pct'] not in excluded],[r['cct_kelvin'] for r in rows if r['dimmer_pct']>=minimum and r['dimmer_pct'] not in excluded],label='Monotonic lookup',color='#469276',ls='--')

for i,p in enumerate(excluded):axs[0].axvspan(p-.5,p+.5,alpha=.12,color='red',label='Excluded setting' if i==0 else None)
axs[0].set_ylabel('CCT from chromaticity (K)');axs[0].legend();axs[0].grid(alpha=.2)
axs[1].plot([r['command_pct'] for r in asc],[r['lux'] for r in asc],color='#2962a3',label='Ascending measured')
axs[1].scatter(list(desc),[r['lux'] for r in desc.values()],color='#da8932',s=15,label='Descending checks')

for p in excluded:axs[1].axvspan(p-.5,p+.5,alpha=.12,color='red')
axs[1].set_ylabel('Illuminance at sensor (lux)');axs[1].grid(alpha=.2)
axs[2].plot([r['command_pct'] for r in asc],[r['window_peak_to_peak_percent'] for r in asc],color='#a94335',label='Ascending window variation')
axs[2].scatter(list(desc),[r['window_peak_to_peak_percent'] for r in desc.values()],color='#da8932',s=15,label='Descending checks')
axs[2].axhline(5,color='gray',ls='--',label='5% variation screen')
axs[2].set_xlim(.5,10.5);axs[2].set_xticks(range(1,11));
for p in excluded:axs[2].axvspan(p-.5,p+.5,alpha=.12,color='red')
axs[2].set_ylabel('Exposure-averaged\npeak-to-peak range (%)');axs[2].set_xlabel('RA3 dimmer command (%) — low end');axs[2].grid(alpha=.2);axs[2].legend(fontsize=8)
fig.suptitle('Fixture SD — ELCO Koto SD module\nIndependent OPT4048 measurements',fontsize=14)
fig.text(.08,.015,'100 ms exposure averages can hide fast flicker; dark baseline unavailable.\nIndependent sensor estimates; no scaling to ELCO ratings or reference-meter accuracy verification.',fontsize=9)
fig.tight_layout(rect=(0,.065,1,.94));fig.savefig(ROOT/'curve.png',dpi=170);fig.savefig(ROOT/'curve.pdf')
