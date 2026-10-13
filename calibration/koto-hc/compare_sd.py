"""Compare matched-protocol SD and HC observations; preserve direction and raw units."""
import pathlib,csv,sys,json
R=pathlib.Path(sys.argv[1]);SD=R.parent.parent/'fixture-sd/mqtt-fast-run'
a={int(r['command_pct']):r for r in csv.DictReader((R/'curve.csv').open())};b={int(r['command_pct']):r for r in csv.DictReader((SD/'curve.csv').open())}
rows=[]
for p,hc in a.items():
 sd=b.get(p)
 if not sd:continue
 row={'command_pct':p}
 for direction in ('ascending','descending'):
  for field in ('lux_window_means_mean','cct_planck_K_window_means_mean','cct_window_means_mean','x_window_means_mean','y_window_means_mean','fast_observed_modulation_pct','fast_low_signal_quantization_screen'):
   key=direction+'_'+field
   for module,r in [('hc',hc),('sd',sd)]:row[module+'_'+key]=r.get(key,'')
   if field!='fast_low_signal_quantization_screen' and hc.get(key) and sd.get(key):row['hc_minus_sd_'+key]=float(hc[key])-float(sd[key])
 rows.append(row)
keys=list(dict.fromkeys(k for r in rows for k in r))
with (R/'hc-vs-sd.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
(R/'sd-comparison-provenance.json').write_text(json.dumps({'sd_source':str(SD),'hc_source':str(R),'same_sensor_position':'Confirmed unchanged by user for HC; SD protocol describes fixed position and light blocking','same_protocol':'mqtt-fast-v1, color 25ms/30samples and fast 600us/5s','sensor_accuracy':'Uncalibrated estimates; matched placement improves comparison but does not establish absolute accuracy','fixture_optics':'HC beam/optics may differ; illuminance is not fixture lumen output','direction_separated':True,'sensor_coefficients_changed':False},indent=2))
print('Compared '+str(len(rows))+' command levels')
