"""Prepare lossless CSV tables from saved observations; no device access."""
import csv, hashlib, json, pathlib, statistics
ROOT = pathlib.Path(__file__).resolve().parent
OUT = pathlib.Path('/path/to/output/sd-csv-export')
protected = [ROOT/'curve.json', ROOT/'adaptive_lighting_dim_to_warm_overheads.yaml', ROOT/'deployment.json']
hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
settling = {r['request_id']: r for r in csv.DictReader((ROOT/'settling-check.csv').open())}
visual = json.loads((ROOT/'visual-observations.json').read_text())
records, originals = [], []
reasons = {'final': '', 'preliminary-unsecured': 'Sensor position uncertain',
           'fixed-sensor-initial-protocol': 'Superseded protocol and possible tape obstruction',
           'tape-obstructed-check': 'Possible tape obstruction'}
for source in sorted(ROOT.rglob('*.jsonl')):
    if source.name not in ('raw.jsonl', 'rejected.jsonl'): continue
    run = 'final' if source.parent == ROOT else source.parent.name
    for line_number, line in enumerate(source.read_text().splitlines(), 1):
        if not line: continue
        original = json.loads(line)
        r = dict(original)
        rejected = source.name == 'rejected.jsonl'
        accepted = not rejected and not r.get('error') and r.get('samples') == 20
        curve_pass = r.get('pass') in ('ascending', 'stability_ascending', 'descending', 'stability_descending')
        r.update(run_id=run, source_file=str(source.relative_to(ROOT)), source_line=line_number,
                 record_status='rejected' if rejected else ('accepted' if accepted else 'invalid_or_failed'),
                 run_exclusion_reason=reasons.get(run, 'Endpoint verification; not incorporated into installed lookup'), final_curve_observation=run=='final' and accepted and curve_pass,
                 rejection_reason='Incomplete sample count' if rejected else r.get('error', ''),
                 visible_flicker_observation=visual.get(str(r.get('command_pct'))+'_pct', '') if run=='final' else '',
                 individual_samples_available=False, individual_sample_stddev_lux=None,
                 fast_flicker_excluded=False, exposure_ms=100)
        if r.get('request_id') in settling:
            extra = settling[r['request_id']]
            r['elapsed_seconds'] = float(extra['elapsed_seconds'])
            r['direction'] = extra['direction']
        if 'requested_kelvin' not in original:
            r['command_requested_kelvin_reconstructed'] = 0
        if 'requested_brightness_pct' not in original:
            r['command_requested_brightness_pct_reconstructed'] = r.get('command_pct')
        mean = r.get('lux')
        if isinstance(mean, (float, int)):
            r['foot_candles_derived'] = mean/10.7639104167097
            low, high = r.get('lux_min'), r.get('lux_max')
            if low is not None and high is not None:
                r['lux_peak_to_peak'] = high-low
                r['lux_peak_to_peak_percent_of_mean'] = 100*(high-low)/mean if mean else None
                r['exposure_averaged_modulation_percent'] = 100*(high-low)/(high+low) if high+low else None
        records.append(r)
        originals.append(original)

def table(rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    return {'fields': fields, 'rows': [[r.get(k) for k in fields] for r in rows]}

curve = list(csv.DictReader((ROOT/'curve.csv').open()))
original_curve = [dict(r) for r in curve]
for r in curve:
    p = int(r['dimmer_pct'])
    r['visible_flicker_observation'] = visual.get(str(p)+'_pct', '')
    r['individual_samples_available'] = False
    for direction in ('ascending', 'descending'):
        group = [x for x in records if x['final_curve_observation'] and x['command_pct']==p
                 and x['pass'] in (direction, 'stability_'+direction)]
        r[direction+'_capture_windows'] = len(group)
        if not group: continue
        r[direction+'_capture_seconds_total'] = sum(x.get('capture_seconds', 0) for x in group)
        r[direction+'_first_capture_utc'] = min(x['time_utc'] for x in group)
        r[direction+'_last_capture_utc'] = max(x['time_utc'] for x in group)
        for key in ('lux', 'cct', 'cct_planck_K', 'x', 'y', 'uv_distance'):
            vals = [x[key] for x in group]
            prefix = direction+'_'+key+'_window_means_'
            r[prefix+'mean'] = statistics.mean(vals)
            r[prefix+'min'] = min(vals)
            r[prefix+'max'] = max(vals)
            r[prefix+'range'] = max(vals)-min(vals)
            r[prefix+'sample_stddev'] = statistics.stdev(vals) if len(vals)>1 else None
            if key=='lux':
                r[prefix+'cv_percent'] = 100*statistics.stdev(vals)/statistics.mean(vals) if len(vals)>1 and statistics.mean(vals) else None
        lo = min(x['lux_min'] for x in group)
        hi = max(x['lux_max'] for x in group)
        r[direction+'_all_windows_lux_peak_to_peak'] = hi-lo
        r[direction+'_all_windows_lux_peak_to_peak_percent_of_mean'] = 100*(hi-lo)/statistics.mean(x['lux'] for x in group)
        r[direction+'_maximum_window_modulation_percent'] = max(x['exposure_averaged_modulation_percent'] for x in group)
    if r['descending_lux']:
        a, d = float(r['ascending_lux']), float(r['descending_lux'])
        r['descending_minus_ascending_lux'] = d-a
        r['directional_lux_difference_percent_of_ascending'] = 100*(d-a)/a if a else None
        r['descending_minus_ascending_cct_K'] = float(r['descending_cct_kelvin'])-float(r['ascending_cct_kelvin'])

assert len(curve)==100
for a,b in zip(original_curve, curve):
    for k,v in a.items():
        candidate=b[k]
        if isinstance(candidate,bool): assert str(candidate).lower()==v.lower()
        elif isinstance(candidate,(float,int)): assert float(v)==candidate
        else: assert ('' if candidate is None else candidate)==v, (k,candidate,v)
for original, augmented in zip(originals, records):
    assert all(augmented[k]==v for k,v in original.items())
payload = {'all-captures.csv':table(records), 'raw-readings.csv':table([r for r in records if r['run_id']=='final']), 'curve.csv':table(curve)}
retest = [r for r in records if r['run_id'].startswith('endpoint-retest-')]
if retest:
    payload['endpoint-retest.csv'] = table(retest)
    summary = []
    keys = sorted({(r['run_id'],r['command_pct'],r.get('direction',''),r.get('settling_target_seconds',0)) for r in retest if r['record_status']=='accepted'})
    for run,pct,direction,settle in keys:
        group = [r for r in retest if (r['run_id'],r['command_pct'],r.get('direction',''),r.get('settling_target_seconds',0))==(run,pct,direction,settle) and r['record_status']=='accepted']
        row={'run_id':run,'dimmer_pct':pct,'direction':direction,'settling_target_seconds':settle,'capture_windows':len(group),'sensor_samples':sum(r['samples'] for r in group)}
        for k in ('lux','cct','cct_planck_K','x','y','uv_distance'):
            vals=[r[k] for r in group]
            row.update({k+'_mean':statistics.mean(vals),k+'_window_mean_min':min(vals),k+'_window_mean_max':max(vals),k+'_window_mean_sample_stddev':statistics.stdev(vals) if len(vals)>1 else None})
        row.update(lux_min=min(r['lux_min'] for r in group),lux_max=max(r['lux_max'] for r in group),max_window_peak_to_peak_percent=max(r['lux_peak_to_peak_percent_of_mean'] for r in group),lookup_updated=False)
        summary.append(row)
    payload['endpoint-summary.csv']=table(summary)
OUT.mkdir(exist_ok=True, parents=True)
(OUT/'tables.json').write_text(json.dumps(payload, allow_nan=False))
audit = {'total_records':len(records), 'final_records':sum(r['run_id']=='final' for r in records),
         'source_records_by_file': {str(f.relative_to(ROOT)):sum(r['source_file']==str(f.relative_to(ROOT)) for r in records) for f in sorted(ROOT.rglob('*.jsonl')) if f.name in ('raw.jsonl','rejected.jsonl')},
         'all_recorded_fields_preserved':True, 'existing_curve_values_preserved':True, 'protected_file_hashes':hashes}
(OUT/'audit.json').write_text(json.dumps(audit,indent=2))
print(json.dumps({k:v for k,v in audit.items() if k!='protected_file_hashes'},indent=2))
