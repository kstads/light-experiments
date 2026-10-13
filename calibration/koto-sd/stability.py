"""Sensor-bandwidth-limited output stability, not a certified flicker metric."""
import csv,json,pathlib,statistics
ROOT=pathlib.Path(__file__).resolve().parent
raw=[json.loads(l) for l in (ROOT/'raw.jsonl').read_text().splitlines()]
rows=[]
for pct in range(1,101):
 for direction in ['ascending','descending']:
  samples=[r for r in raw if r.get('command_pct')==pct and r.get('pass') in [direction,'stability_'+direction] and 'error' not in r]
  if not samples:continue
  means=[r['lux'] for r in samples];lo=min(r['lux_min'] for r in samples);hi=max(r['lux_max'] for r in samples);avg=statistics.mean(means)
  peak=max((r['lux_max']-r['lux_min'])/r['lux']*100 for r in samples)
  spread=(max(means)-min(means))/avg*100
  # A 5% envelope is an explicitly chosen repeatability screen, not a flicker standard.
  rows.append({'dimmer_pct':pct,'direction':direction,'capture_windows':len(samples),'sensor_samples':sum(r['samples'] for r in samples),'mean_lux':round(avg,4),'minimum_lux':lo,'maximum_lux':hi,'max_window_peak_to_peak_percent':round(peak,2),'between_window_mean_spread_percent':round(spread,2),'smoothed_modulation_percent':round((hi-lo)/(hi+lo)*100,2),'stability_screen':('incomplete' if len(samples)<2 else 'variation_detected' if max(peak,spread)>5 else 'variation_not_detected'),'visible_flicker':'not_assessed','bandwidth_note':'100 ms sensor exposures; fast flicker may be missed'})
with (ROOT/'low-level-stability.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['dimmer_pct']);w.writeheader();w.writerows(rows)
complete=[r for r in rows if r['capture_windows']>=2]
print(json.dumps(complete,indent=2))
# Require stable screens in both directions at every remaining low-end setting.
by={(r['dimmer_pct'],r['direction']):r for r in rows}
if all((p,d) in by and by[p,d]['capture_windows']>=2 for p in range(1,21) for d in ['ascending','descending']):
 floor=next((p for p in range(2,21) if all(by[q,d]['stability_screen']=='variation_not_detected' for q in range(p,21) for d in ['ascending','descending'])),None)
 lowest=next((p for p in range(2,21) if all(by[p,d]['stability_screen']=='variation_not_detected' for d in ['ascending','descending'])),None)
 excluded=sorted({r['dimmer_pct'] for r in rows if r['stability_screen']=='variation_detected'})
 (ROOT/'stability-floor.json').write_text(json.dumps({'candidate_minimum_dimmer_pct':lowest,'conservative_contiguous_floor_pct':floor,'excluded_dimmer_pcts':excluded,'criterion':'max 5% window peak-to-peak or between-window mean spread, in both directions, through 20%','visible_flicker_boundary_confirmed':False,'known_visible_flicker_pct':1},indent=2))
 print('Candidate operating floor:',floor)
