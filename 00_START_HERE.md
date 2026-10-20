# 🚀 Start Here - NetCDF Version

Welcome to the netCDF version of the TAO salinity drift correction tool!

## What's in This Directory?

This directory contains everything you need to use netCDF format instead of pickle files.

### 📁 Directory Contents

```
netCDF/
├── 00_START_HERE.md ← You are here!
├── README.md                      # Complete overview
│
├── Main Script:
│   └── cond_drift_netcdf.py      # NetCDF version (replaces ../cond_drift.py)
│
├── Documentation:
│   ├── QUICK_REFERENCE.md        # Quick commands ⭐ READ THIS FIRST
│   ├── MIGRATION_GUIDE.md        # Step-by-step migration
│   ├── NETCDF_README.md          # Comprehensive guide
│   ├── WORKFLOW.md               # Processing workflow
│   └── CHANGES.md                # What changed from pickle version
│
└── Utilities:
    ├── read_netcdf_example.py    # Example: how to read .nc files
    ├── convert_pkl_to_nc.py      # Convert old .pkl files to .nc
    └── test_netcdf_conversion.py # Validate your .nc output
```

## 🎯 Quick Start (3 Steps)

### 1️⃣ Install Dependencies
```bash
conda install xarray netcdf4
```

### 2️⃣ Run the Script
```bash
# From the Salinity_dev directory:
python netCDF/cond_drift_netcdf.py pt006

# Or from within this netCDF directory:
cd netCDF
python cond_drift_netcdf.py pt006
```

### 3️⃣ Verify Output
```bash
# Test the output files
python netCDF/test_netcdf_conversion.py pt006

# View the data
python netCDF/read_netcdf_example.py pt006 --variable salinity
```

## 📖 Where to Go Next?

### If you're new to netCDF:
1. Read [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for common commands
2. Try the example: `python read_netcdf_example.py pt006 --variable salinity`
3. Browse [NETCDF_README.md](NETCDF_README.md) for detailed information

### If you're migrating from pickle:
1. Read [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) for step-by-step instructions
2. Convert old files: `python convert_pkl_to_nc.py old_file.pkl --type salinity --dep-id pt006`
3. Update your scripts (see examples in MIGRATION_GUIDE.md)

### If you want to understand the changes:
1. Read [CHANGES.md](CHANGES.md) for technical details
2. Read [WORKFLOW.md](WORKFLOW.md) for the processing workflow

## 🤔 Why NetCDF Instead of Pickle?

| Feature | Pickle (.pkl) | NetCDF (.nc) |
|---------|---------------|--------------|
| Python version issues | ❌ Common | ✅ None |
| Includes metadata | ❌ No | ✅ Yes |
| Works in R, MATLAB | ❌ No | ✅ Yes |
| Long-term archival | ❌ Risky | ✅ Safe |
| Self-documenting | ❌ No | ✅ Yes |

## 🔄 The Original Version

The original `cond_drift.py` (pickle version) is still in the parent directory:
```
../cond_drift.py  ← Original version (still works!)
```

Use whichever format works best for your workflow!

## 📊 Output Files

### Pickle Version (../cond_drift.py)
```
pt006cond_drift.pkl
pt006sal_drift.pkl
pt006dens_drift.pkl
```

### NetCDF Version (cond_drift_netcdf.py)
```
pt006_cond_drift.nc
pt006_sal_drift.nc
pt006_dens_drift.nc
```

Note the underscore before the variable name in netCDF files!

## 💡 Common Tasks

### Read a netCDF file in Python:
```python
import xarray as xr
ds = xr.open_dataset('pt006_sal_drift.nc')
df = ds.to_dataframe()  # Convert to pandas
```

### Inspect a netCDF file from command line:
```bash
ncdump -h pt006_sal_drift.nc
```

### Convert old pickle file to netCDF:
```bash
python convert_pkl_to_nc.py pt006sal_drift.pkl \
    --type salinity --dep-id pt006
```

## ❓ Need Help?

1. **Quick questions:** See [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
2. **Migration help:** See [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)
3. **Detailed guide:** See [NETCDF_README.md](NETCDF_README.md)
4. **Overview:** See [README.md](README.md)

## ✅ Next Steps

- [ ] Install xarray and netcdf4
- [ ] Run `cond_drift_netcdf.py` on a test deployment
- [ ] Validate output with `test_netcdf_conversion.py`
- [ ] Try reading the output with `read_netcdf_example.py`
- [ ] Update your analysis scripts to use netCDF
- [ ] Share with your team!

---

**Questions?** Check the documentation files listed above or contact your team lead.

**Date:** 2026-10-19  
**Version:** 1.0
