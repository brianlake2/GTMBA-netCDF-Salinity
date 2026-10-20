# NetCDF Migration - Complete Guide

This directory contains the netCDF version of `cond_drift.py` (saved as `cond_drift_netcdf.py`) and supporting documentation for migrating from pickle (.pkl) to netCDF (.nc) format.

**Note:** The original `cond_drift.py` remains in the parent directory and continues to use pickle format. This directory provides the netCDF alternative for when your team is ready to migrate.

## 📋 Quick Start

### 1. Install Dependencies
```bash
conda install xarray netcdf4
```

### 2. Run the Script
```bash
# Use the netCDF version
python netCDF/cond_drift_netcdf.py pt006

# Or from within the netCDF directory:
cd netCDF
python cond_drift_netcdf.py pt006
```

### 3. Verify Output
```bash
python netCDF/test_netcdf_conversion.py pt006
```

### 4. View Results
```bash
python netCDF/read_netcdf_example.py pt006 --variable salinity
```

## 📚 Documentation Index

### For Users
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick commands and common operations ⭐ START HERE
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Step-by-step migration instructions
- **[WORKFLOW.md](WORKFLOW.md)** - Data processing workflow with diagrams

### For Developers
- **[CHANGES.md](CHANGES.md)** - Summary of code changes
- **[NETCDF_README.md](NETCDF_README.md)** - Comprehensive netCDF usage guide
- **cond_drift_netcdf.py** - NetCDF version of the main script (outputs .nc files)

### Utility Scripts
- **[read_netcdf_example.py](read_netcdf_example.py)** - Example reader script
- **[convert_pkl_to_nc.py](convert_pkl_to_nc.py)** - Convert old pickle files
- **[test_netcdf_conversion.py](test_netcdf_conversion.py)** - Validate netCDF output

## 🎯 What Changed

### File Format
- ❌ OLD: `pt006cond_drift.pkl`, `pt006sal_drift.pkl`, `pt006dens_drift.pkl`
- ✅ NEW: `pt006_cond_drift.nc`, `pt006_sal_drift.nc`, `pt006_dens_drift.nc`

### Key Improvements
1. **Self-describing format** - Files contain metadata (units, sensor info, etc.)
2. **Cross-platform** - Works in Python, R, MATLAB, IDL, command line
3. **No version issues** - No Python 3.8 vs 3.12 compatibility problems
4. **Industry standard** - Follows CF-1.8 conventions
5. **Better for archival** - Long-term storage and data sharing

### Also Fixed
- Bokeh timezone warning resolved

## 📖 Common Tasks

### Read NetCDF File
```python
import xarray as xr
ds = xr.open_dataset('pt006_sal_drift.nc')
df = ds.to_dataframe()  # Convert to pandas if needed
ds.close()
```

### Inspect File Structure
```bash
ncdump -h pt006_sal_drift.nc
```

### Convert Old Pickle Files
```bash
python convert_pkl_to_nc.py pt006sal_drift.pkl \
    --type salinity --dep-id pt006 --lat 0.0 --lon -140.0
```

### View Example
```bash
python read_netcdf_example.py pt006 --variable salinity
```

### Validate Output
```bash
python test_netcdf_conversion.py pt006
```

## 🔧 Updating Your Code

### Minimal Change Required
```python
# OLD CODE:
import pandas as pd
df = pd.read_pickle('pt006sal_drift.pkl')

# NEW CODE:
import xarray as xr
ds = xr.open_dataset('pt006_sal_drift.nc')
df = ds.to_dataframe()
ds.close()
```

The DataFrame structure is the same!

## 📊 File Contents

Each netCDF file contains:

### Global Metadata
- Deployment ID
- Latitude/Longitude
- Institution (NOAA/PMEL)
- Processing description
- Creation date
- CF conventions

### Data Variables
Each sensor/depth combination is a separate variable:
- Variable name: `{type}_{serial_number}_{depth_label}`
- Units (PSU, mS/cm, kg/m³)
- Long descriptive name
- Serial number
- Depth label

### Example
```
salinity_12345_SSS:
  units = "PSU"
  long_name = "Practical salinity (drift-corrected) at SSS"
  serial_number = "12345"
  depth_label = "SSS"
```

## ✅ Benefits

| Feature | Pickle | NetCDF |
|---------|--------|--------|
| Python version compatibility | ❌ | ✅ |
| Self-describing | ❌ | ✅ |
| Works in R, MATLAB | ❌ | ✅ |
| Industry standard | ❌ | ✅ |
| Long-term archival | ❌ | ✅ |
| Metadata included | ❌ | ✅ |
| Security issues | ⚠️ | ✅ |

## 🐛 Troubleshooting

### ImportError: No module named 'xarray'
```bash
conda install xarray netcdf4
```

### File not found
- Check filename has underscore: `pt006_sal_drift.nc` (not `pt006sal_drift.nc`)
- Old format: `pt006sal_drift.pkl`
- New format: `pt006_sal_drift.nc` (note the underscore)

### Bokeh timezone warning
- Fixed in updated `cond_drift.py`
- Datetimes now converted to UTC-aware timestamps

## 📞 Support

1. **Quick answers:** [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
2. **Migration help:** [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
3. **Technical details:** [NETCDF_README.md](NETCDF_README.md)
4. **Code changes:** [CHANGES.md](CHANGES.md)

## 🧪 Testing

Run the test suite to verify your output:
```bash
python test_netcdf_conversion.py pt006
```

Expected output:
```
Testing NetCDF files for deployment: pt006
============================================================

Testing pt006_cond_drift.nc:
------------------------------------------------------------
  ✓ pt006_cond_drift.nc exists
  ✓ pt006_cond_drift.nc is readable
  ✓ pt006_cond_drift.nc has 4 data variables
  ✓ pt006_cond_drift.nc has required metadata
  ✓ pt006_cond_drift.nc variables have required attributes
  ✓ pt006_cond_drift.nc has time dimension
  ✓ pt006_cond_drift.nc contains valid data
  ✓ pt006_cond_drift.nc follows CF conventions

  ✅ All tests passed for pt006_cond_drift.nc

... (similar for sal and dens files)

============================================================
✅ ALL TESTS PASSED

NetCDF files are valid and ready to use!
```

## 📦 File Summary

### Main Script
- `cond_drift_netcdf.py` - NetCDF version (outputs .nc files)
- `../cond_drift.py` - Original version in parent directory (outputs .pkl files)

### New Documentation
- `README_NETCDF.md` - This file (overview)
- `QUICK_REFERENCE.md` - Quick commands
- `MIGRATION_GUIDE.md` - Migration instructions
- `NETCDF_README.md` - Comprehensive guide
- `WORKFLOW.md` - Processing workflow
- `CHANGES.md` - Change summary

### New Utilities
- `read_netcdf_example.py` - Example reader
- `convert_pkl_to_nc.py` - Format converter
- `test_netcdf_conversion.py` - Validation tests

## 🚀 Next Steps

1. ✅ Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
2. ✅ Install xarray and netcdf4
3. ✅ Run `cond_drift.py` on a test deployment
4. ✅ Validate with `test_netcdf_conversion.py`
5. ✅ Update downstream analysis scripts
6. ✅ Convert old pickle files if needed
7. ✅ Share with team!

## 🎓 Learning Resources

### NetCDF Basics
- [Unidata NetCDF](https://www.unidata.ucar.edu/software/netcdf/)
- [CF Conventions](http://cfconventions.org/)
- [Xarray Tutorial](http://xarray.pydata.org/en/stable/getting-started-guide/quick-overview.html)

### Command Line Tools
```bash
# View header (structure and metadata)
ncdump -h file.nc

# View all data
ncdump file.nc

# View specific variable
ncdump -v varname file.nc

# View coordinates only
ncdump -c file.nc
```

### Visualization Tools
- **Panoply** (NASA) - Cross-platform viewer
- **ncview** - Quick Linux viewer
- **Python** - matplotlib, xarray built-in plotting
- **MATLAB** - Built-in netCDF support

---

**Last Updated:** 2026-10-19  
**Version:** 1.0  
**Author:** NOAA/PMEL TAO Project  

For questions or issues, contact your team lead or data manager.
