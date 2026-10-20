# Quick Reference - NetCDF Migration

## Installation
```bash
conda install xarray netcdf4
```

## Running the Script
```bash
python cond_drift.py pt006
```

**Output:** `pt006_cond_drift.nc`, `pt006_sal_drift.nc`, `pt006_dens_drift.nc`

## Reading NetCDF Files

### Python (xarray)
```python
import xarray as xr

ds = xr.open_dataset('pt006_sal_drift.nc')
df = ds.to_dataframe()  # Convert to pandas
ds.close()
```

### Python (one-liner)
```python
import xarray as xr
df = xr.open_dataset('pt006_sal_drift.nc').to_dataframe()
```

### Command Line
```bash
ncdump -h pt006_sal_drift.nc  # View structure
ncdump pt006_sal_drift.nc     # View all data
```

### MATLAB
```matlab
sal = ncread('pt006_sal_drift.nc', 'salinity_12345_SSS');
```

### R
```r
library(ncdf4)
nc <- nc_open("pt006_sal_drift.nc")
sal <- ncvar_get(nc, "salinity_12345_SSS")
```

## Converting Old Pickle Files
```bash
python convert_pkl_to_nc.py pt006sal_drift.pkl \
    --type salinity --dep-id pt006 --lat 0.0 --lon -140.0
```

## Viewing Data
```bash
python read_netcdf_example.py pt006 --variable salinity
```

## File Naming Changes

| Old (Pickle) | New (NetCDF) |
|-------------|--------------|
| `pt006cond_drift.pkl` | `pt006_cond_drift.nc` |
| `pt006sal_drift.pkl` | `pt006_sal_drift.nc` |
| `pt006dens_drift.pkl` | `pt006_dens_drift.nc` |

Note: Added underscore before variable name

## Common Operations

### List all variables
```python
import xarray as xr
ds = xr.open_dataset('pt006_sal_drift.nc')
print(list(ds.data_vars))
```

### Access metadata
```python
import xarray as xr
ds = xr.open_dataset('pt006_sal_drift.nc')
print(ds.attrs)  # Global attributes
print(ds['salinity_12345_SSS'].attrs)  # Variable attributes
```

### Extract single sensor
```python
import xarray as xr
ds = xr.open_dataset('pt006_sal_drift.nc')
sss_data = ds['salinity_12345_SSS'].values
time = ds.time.values
```

### Plot time series
```python
import xarray as xr
ds = xr.open_dataset('pt006_sal_drift.nc')
ds['salinity_12345_SSS'].plot()
```

## Updating Your Code

### Before (Pickle)
```python
import pandas as pd
df = pd.read_pickle('pt006sal_drift.pkl')
```

### After (NetCDF)
```python
import xarray as xr
ds = xr.open_dataset('pt006_sal_drift.nc')
df = ds.to_dataframe()
ds.close()
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ImportError: xarray` | `conda install xarray netcdf4` |
| `FileNotFoundError` | Check filename has underscore: `_sal_drift.nc` |
| Timezone warning | Fixed in updated script |
| Need old pickle | Convert NC to pickle (not recommended) |

## Documentation Files

| File | Purpose |
|------|---------|
| **QUICK_REFERENCE.md** | This file - quick commands |
| **NETCDF_README.md** | Comprehensive netCDF guide |
| **MIGRATION_GUIDE.md** | Step-by-step migration |
| **WORKFLOW.md** | Data processing workflow |
| **CHANGES.md** | What changed in the code |

## Benefits at a Glance

✅ No Python version issues  
✅ Self-documenting files  
✅ Works in Python, R, MATLAB  
✅ Industry standard format  
✅ Better for long-term storage  
✅ No security concerns  

## Help Commands

```bash
# View file info
ncdump -h file.nc

# Get file dimensions
ncdump -c file.nc

# Extract one variable
ncdump -v varname file.nc

# Python help
python read_netcdf_example.py --help
python convert_pkl_to_nc.py --help
```

## Contact

Questions? See **MIGRATION_GUIDE.md** or contact your team lead.

---

**Version:** 1.0  
**Date:** 2026-10-19
