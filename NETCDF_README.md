# NetCDF File Format Guide

## Why NetCDF Instead of Pickle?

### Problems with Pickle (.pkl)
- ❌ **Not backward compatible** - Files saved in Python 3.8 may not load in Python 3.12
- ❌ **Security risk** - Can execute arbitrary code when unpickling
- ❌ **Not self-documenting** - No metadata about what's inside
- ❌ **Python-only** - Can't read from R, MATLAB, IDL, etc.
- ❌ **Not human-readable** - Can't inspect without Python

### Advantages of NetCDF (.nc)
- ✅ **Self-describing** - Contains metadata (units, long names, provenance)
- ✅ **Cross-platform** - Works on Windows, Mac, Linux
- ✅ **Language independent** - Read from Python, R, MATLAB, IDL, Julia, etc.
- ✅ **Industry standard** - Used by NOAA, NASA, NCAR, and oceanographic community
- ✅ **CF conventions** - Follows Climate and Forecast metadata conventions
- ✅ **Inspectable** - Use `ncdump -h file.nc` to see contents
- ✅ **Compressed** - Built-in compression support
- ✅ **Forward/backward compatible** - Files from 2000 still work today

## File Structure

The cond_drift.py script now creates three netCDF files:

```
{dep_id}_cond_drift.nc  - Drift-corrected conductivity (mS/cm)
{dep_id}_sal_drift.nc   - Drift-corrected salinity (PSU)
{dep_id}_dens_drift.nc  - Potential density anomaly (kg/m³)
```

### Global Attributes (Metadata)
Each file contains deployment-level metadata:
- `deployment_id` - Deployment identifier
- `latitude` - Mooring latitude
- `longitude` - Mooring longitude
- `creation_date` - When file was created
- `institution` - NOAA/PMEL
- `source` - TAO/TRITON mooring array
- `conventions` - CF-1.8
- `processing` - Description of processing applied

### Variables
Each variable (sensor/depth combination) includes:
- `units` - Physical units
- `long_name` - Descriptive name
- `serial_number` - Instrument serial number
- `depth_label` - Depth identifier (SSS, S010, etc.)

## How to Use NetCDF Files

### Python (xarray - recommended)
```python
import xarray as xr

# Open dataset
ds = xr.open_dataset('pt006_sal_drift.nc')

# View metadata
print(ds.attrs)

# List all variables
print(ds.data_vars)

# Access a specific variable
salinity_ssc = ds['salinity_12345_SSS']

# Get values as numpy array
values = salinity_ssc.values

# Convert to pandas
df = ds.to_dataframe()

# Close when done
ds.close()
```

### Python (netCDF4 library)
```python
from netCDF4 import Dataset

# Open dataset
nc = Dataset('pt006_sal_drift.nc', 'r')

# View variables
print(nc.variables.keys())

# Access data
salinity = nc.variables['salinity_12345_SSS'][:]
time = nc.variables['time'][:]

# View attributes
print(nc.getncattr('deployment_id'))

nc.close()
```

### Python (pandas compatibility)
```python
import xarray as xr

# If you need a pandas DataFrame with multi-index columns
ds = xr.open_dataset('pt006_sal_drift.nc')

# Convert to DataFrame (long format)
df = ds.to_dataframe()

# Or reconstruct multi-index columns from attributes
# (custom code based on your column structure needs)
```

### Command Line Tools

**Inspect file structure:**
```bash
ncdump -h pt006_sal_drift.nc
```

**View all data:**
```bash
ncdump pt006_sal_drift.nc
```

**View specific variable:**
```bash
ncdump -v salinity_12345_SSS pt006_sal_drift.nc
```

### MATLAB
```matlab
% Read netCDF file
data = ncread('pt006_sal_drift.nc', 'salinity_12345_SSS');
time = ncread('pt006_sal_drift.nc', 'time');

% Read attributes
deployment = ncreadatt('pt006_sal_drift.nc', '/', 'deployment_id');
units = ncreadatt('pt006_sal_drift.nc', 'salinity_12345_SSS', 'units');
```

### R
```r
library(ncdf4)

# Open netCDF file
nc <- nc_open("pt006_sal_drift.nc")

# Read variable
salinity <- ncvar_get(nc, "salinity_12345_SSS")
time <- ncvar_get(nc, "time")

# Read attributes
deployment <- ncatt_get(nc, 0, "deployment_id")$value

nc_close(nc)
```

## Common Operations

### Reading Example Script
Run the provided example to explore your data:
```bash
python read_netcdf_example.py pt006 --variable salinity
```

### Merging Multiple Deployments
```python
import xarray as xr

# Open multiple files
ds1 = xr.open_dataset('pt006_sal_drift.nc')
ds2 = xr.open_dataset('pt007_sal_drift.nc')

# Concatenate along time dimension
combined = xr.concat([ds1, ds2], dim='time')

# Save combined file
combined.to_netcdf('combined_sal_drift.nc')
```

### Extracting Specific Sensor
```python
import xarray as xr

ds = xr.open_dataset('pt006_sal_drift.nc')

# Extract all variables for a specific serial number
sn = '12345'
sn_vars = [v for v in ds.data_vars if f'_{sn}_' in v]

# Create new dataset with just those variables
ds_subset = ds[sn_vars]
ds_subset.to_netcdf(f'pt006_sal_sn{sn}.nc')
```

### Adding More Metadata
```python
import xarray as xr

ds = xr.open_dataset('pt006_sal_drift.nc')

# Add more global attributes
ds.attrs['contact'] = 'your.email@noaa.gov'
ds.attrs['references'] = 'DOI or publication reference'

# Add variable-specific metadata
for var in ds.data_vars:
    ds[var].attrs['valid_min'] = float(ds[var].min())
    ds[var].attrs['valid_max'] = float(ds[var].max())

# Save with additional metadata
ds.to_netcdf('pt006_sal_drift_enhanced.nc')
```

## Visualization Tools

NetCDF files work with many visualization tools:

- **Panoply** (NASA) - Cross-platform netCDF viewer
- **ncview** - Quick Linux netCDF viewer  
- **Ferret** - NOAA analysis and visualization tool
- **ncBrowse** - Interactive netCDF browser
- **Python**: matplotlib, bokeh, holoviews (via xarray)
- **Web**: TDS (THREDDS Data Server) for data serving

## Migration from Pickle

If you have existing pickle files and code that reads them:

```python
import pandas as pd
import xarray as xr

# Old way - pickle
df_old = pd.read_pickle('pt006sal_drift.pkl')

# New way - netCDF
ds = xr.open_dataset('pt006_sal_drift.nc')
df_new = ds.to_dataframe()

# Both df_old and df_new contain the same data
# But df_new comes with all metadata preserved!
```

## Best Practices

1. **Always include metadata**: Units, long names, provenance
2. **Use CF conventions**: Follow standard names when applicable
3. **Add processing history**: Document what was done to the data
4. **Include contact info**: Who to ask about the data
5. **Use compression**: `ds.to_netcdf(file, encoding={var: {'zlib': True} for var in ds.data_vars})`
6. **Version your format**: If structure changes, note in global attributes

## Further Reading

- [NetCDF Documentation](https://www.unidata.ucar.edu/software/netcdf/)
- [CF Conventions](http://cfconventions.org/)
- [Xarray Tutorial](http://xarray.pydata.org/en/stable/getting-started-guide/quick-overview.html)
- [NOAA netCDF Guidelines](https://www.ncei.noaa.gov/netcdf/)
