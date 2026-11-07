"""Shared loader for the four NOAA-GLERL Western Lake Erie buoy CSVs (GLOS Seagull / ERDDAP)."""
import pandas as pd, numpy as np, os
UP = '/mnt/user-data/uploads/'
FILES = {'WE2': 'obs_80_55c9_3b03_d94b.csv', 'WE4': 'obs_81_0b83_f02c_75d2.csv',
         'WE8': 'obs_82_382e_34e9_51a8.csv', 'WE13': 'obs_215_e358_af2a_241c.csv'}
IDS = {'WE2': 'obs_80', 'WE4': 'obs_81', 'WE8': 'obs_82', 'WE13': 'obs_215'}
SENS = {'chl': 'chlorophyll_fluorescence', 'phyco': 'phycocyanin_fluorescence',
        'bga': 'mass_concentration_of_blue_green_algae_in_sea_water_rfu',
        'do': 'fractional_saturation_of_oxygen_in_sea_water', 'temp': 'sea_surface_temperature',
        'turb': 'sea_water_turbidity', 'cond': 'sea_water_electrical_conductivity'}
TESTS = {'agg': 'aggregate_test', 'flat': 'flat_line_test', 'gross': 'gross_range_test',
         'roc': 'rate_of_change_test', 'spike': 'spike_test'}
SENSORS = ['chl', 'phyco', 'do', 'temp', 'turb', 'cond']  # phyco = merged phycocyanin + blue-green-algae RFU
NAMES = {'chl': 'Chlorophyll (RFU)', 'phyco': 'Phycocyanin (RFU)', 'do': 'Oxygen (% sat.)',
         'temp': 'Water temp (°C)', 'turb': 'Turbidity (NTU)', 'cond': 'Conductivity (S/m)'}


def load_raw(buoy):
    df = pd.read_csv(UP + FILES[buoy], skiprows=[1])
    df['time'] = pd.to_datetime(df['time'], utc=True).dt.tz_localize(None)
    return df.sort_values('time').reset_index(drop=True)


def load(buoy):
    """Wide tidy frame: value + 5 flags per sensor. -999 -> NaN (counted in sent_*), K -> degC,
    phycocyanin and blue-green-algae columns merged into one series (phyco)."""
    r = load_raw(buoy)
    out = pd.DataFrame({'time': r['time']})
    out['buoy'] = buoy
    out['batt'] = r['battery_voltage']
    for s, col in SENS.items():
        if col not in r:
            continue
        v = r[col].astype(float)
        out['sent_' + s] = (v == -999)
        out[s] = v.mask(v == -999)
        for t, tn in TESTS.items():
            out[f'{s}_{t}'] = r[f'{col}_{tn}']
    if 'bga' in out:
        use_b = out['phyco'].isna() & out['bga'].notna()
        out['phyco_src'] = np.where(out['phyco'].notna(), 'phyco', np.where(out['bga'].notna(), 'bga', ''))
        for t in [''] + ['_' + k for k in TESTS]:
            out['phyco' + t] = out['phyco' + t].where(~use_b, out['bga' + t])
        out = out.drop(columns=[c for c in out if c.startswith('bga') or c == 'sent_bga'])
    else:
        out['phyco_src'] = np.where(out['phyco'].notna(), 'phyco', '')
    out['temp'] = out['temp'] - 273.15
    out['year'] = out['time'].dt.year
    return out


def load_all():
    return {b: load(b) for b in FILES}
