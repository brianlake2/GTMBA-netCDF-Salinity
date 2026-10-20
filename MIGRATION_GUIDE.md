# Migration Guide: Pickle to NetCDF

## Summary of Changes

The `cond_drift.py` script has been updated to save data in **netCDF format** instead of pickle format. This change provides better long-term compatibility, interoperability, and follows oceanographic data standards.

## What Changed

### File Formats
| Old (Pickle) | New (NetCDF) |
|-------------|--------------|
| `{dep_id}cond_drift.pkl` | `{dep_id}_cond_drift.nc` |
| `{dep_id}sal_drift.pkl` | `{dep_id}_sal_drift.nc` |
| `{dep_id}dens_drift.pkl` | `{dep_id}_dens_drift.nc` |

### New Dependencies
- **xarray**: Added for netCDF handling
  ```bash
  conda install xarray netcdf4
  # or
  pip install xarray netcdf4
  ```

### Bug Fixes
- Fixed Bokeh timezone warning by converting datetime index to UTC-aware timestamps

## Quick Start

### Running the Updated Script
```bash
python cond_drift.py pt006
```

This now creates `.nc` files instead of `.pkl` files.

### Reading the Output Files

**Option 1: Using the example script**
```bash
python read_netcdf_example.py pt006 --variable salinity
```

**Option 2: In your own Python code**
```python
import xarray as xr

# Open the dataset
ds = xr.open_dataset('pt006_sal_drift.nc')

# Convert to pandas DataFrame (similar to old pickle format)
df = ds.to_dataframe()

# Or access individual variables
for var_name in ds.data_vars:
    data = ds[var_name].values
    time = ds.time.values
    # ... your processing here ...

ds.close()
```

## Updating Existing Code

### If Your Code Used Pickle Files

**Old code:**
```python
import pandas as pd

# Load pickle file
sal_drift = pd.read_pickle('pt006sal_drift.pkl')
```

**New code:**
```python
import xarray as xr

# Load netCDF file
ds = xr.open_dataset('pt006_sal_drift.nc')
sal_drift = ds.to_dataframe()
ds.close()

# sal_drift is now a pandas DataFrame, just like before!
```

### Converting Existing Pickle Files

If you have existing pickle files you want to convert:

```bash
python convert_pkl_to_nc.py pt006sal_drift.pkl \
    --type salinity \
    --dep-id pt006 \
    --lat 0.0 \
    --lon -140.0
```

## Benefits of NetCDF

### 1. **Long-term Compatibility**
- Pickle files can break between Python versions
- NetCDF files from 20+ years ago still work today
- No need to keep old Python environments around

### 2. **Self-Documenting**
NetCDF files include metadata:
```bash
$ ncdump -h pt006_sal_drift.nc
netcdf pt006_sal_drift {
dimensions:
        time = UNLIMITED ;
variables:
        double time(time) ;
                time:standard_name = "time" ;
                time:long_name = "time" ;
        double salinity_12345_SSS(time) ;
                salinity_12345_SSS:units = "PSU" ;
                salinity_12345_SSS:long_name = "Practical salinity at SSS" ;
                salinity_12345_SSS:serial_number = "12345" ;
                salinity_12345_SSS:depth_label = "SSS" ;
...
```

### 3. **Cross-Platform & Language Independent**
Read your data in:
- **Python** (xarray, netCDF4)
- **R** (ncdf4)
- **MATLAB** (ncread)
- **IDL** (ncdf_open)
- **Julia** (NetCDF.jl)
- **Command line** (ncdump, ncview, Panoply)

### 4. **Industry Standard**
- Used by NOAA, NASA, NCAR, and oceanographic community
- Follows CF (Climate and Forecast) conventions
- Compatible with THREDDS data servers, OPeNDAP

### 5. **Better for Collaboration**
- Team members don't need to ask "what's in this file?"
- Units and descriptions are embedded
- Processing history is recorded

## Testing Your Migration

### Verify Output Files
```bash
# Check files were created
ls -lh *_drift.nc

# Inspect structure
ncdump -h pt006_sal_drift.nc

# View in Python
python read_netcdf_example.py pt006 --variable salinity
```

### Compare with Old Pickle Files
If you have both formats:
```python
import pandas as pd
import xarray as xr
import numpy as np

# Load both formats
df_pkl = pd.read_pickle('pt006sal_drift.pkl')
ds_nc = xr.open_dataset('pt006_sal_drift.nc')
df_nc = ds_nc.to_dataframe()

# Compare shapes
print(f"Pickle shape: {df_pkl.shape}")
print(f"NetCDF shape: {df_nc.shape}")

# Compare values (they should be identical)
# Note: column names may differ, so compare by position
for i in range(len(df_pkl.columns)):
    pkl_col = df_pkl.iloc[:, i]
    nc_col = df_nc.iloc[:, i]
    max_diff = np.nanmax(np.abs(pkl_col - nc_col))
    print(f"Column {i} max difference: {max_diff}")
```

## Troubleshooting

### "No module named 'xarray'"
Install xarray:
```bash
conda install xarray netcdf4
# or
pip install xarray netcdf4
```

### "No module named 'netCDF4'"
Install the netCDF4 Python library:
```bash
conda install netcdf4
# or
pip install netcdf4
```

### Old Scripts Still Expect Pickle Files
Two options:
1. Update your scripts to read netCDF (recommended)
2. Convert netCDF back to pickle temporarily (not recommended):
   ```python
   import xarray as xr
   ds = xr.open_dataset('pt006_sal_drift.nc')
   df = ds.to_dataframe()
   df.to_pickle('pt006sal_drift.pkl')  # backwards compatibility
   ```

### NetCDF File is Larger than Pickle
You can enable compression:
```python
# In cond_drift.py, when saving:
encoding = {var: {'zlib': True, 'complevel': 4} for var in ds.data_vars}
ds.to_netcdf(filename, format='NETCDF4', encoding=encoding)
```

## Additional Resources

- **NETCDF_README.md** - Comprehensive guide to working with netCDF files
- **read_netcdf_example.py** - Example script for reading the new format
- **convert_pkl_to_nc.py** - Convert existing pickle files to netCDF

## Questions?

Common questions:

**Q: Can I still use pandas DataFrames?**  
A: Yes! Just convert: `df = xr.open_dataset('file.nc').to_dataframe()`

**Q: Do I need to change my analysis code?**  
A: Minimal changes - mainly just how you load the data.

**Q: What about old pickle files?**  
A: Use `convert_pkl_to_nc.py` to migrate them.

**Q: Is netCDF slower than pickle?**  
A: No, netCDF with compression is often faster and smaller.

**Q: Can I view the files without Python?**  
A: Yes! Use ncdump, ncview, Panoply, or any netCDF-compatible tool.

## Checklist

- [ ] Install xarray and netCDF4 libraries
- [ ] Run updated `cond_drift.py` and verify `.nc` files are created
- [ ] Test reading with `read_netcdf_example.py`
- [ ] Update downstream scripts to read netCDF instead of pickle
- [ ] Convert any existing pickle files with `convert_pkl_to_nc.py`
- [ ] Update documentation/workflows to reference `.nc` files
- [ ] Consider adding netCDF files to version control (they're smaller with compression)

---

**Migration Date:** 2026-10-19  
**Script Version:** cond_drift.py with netCDF support  
**Contact:** Your Team Lead / Data Manager
