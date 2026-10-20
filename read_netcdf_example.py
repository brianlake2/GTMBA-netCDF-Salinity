#!/usr/bin/env python3
"""
Example script demonstrating how to read and work with netCDF files 
produced by cond_drift.py

This shows the advantages of netCDF format:
- Self-describing (metadata included)
- Can be read by many tools (Python, R, MATLAB, IDL, ncdump, etc.)
- Backward compatible
- No security concerns like pickle files
"""

import xarray as xr
import pandas as pd
import numpy as np
import argparse

def main():
    parser = argparse.ArgumentParser(description='Read and display netCDF data from drift correction')
    parser.add_argument('dep_id', type=str, help='Deployment ID (e.g., pt006)')
    parser.add_argument('--variable', type=str, default='salinity', 
                       choices=['salinity', 'conductivity', 'density'],
                       help='Variable to display')
    args = parser.parse_args()
    
    # Construct filename
    if args.variable == 'salinity':
        filename = f"{args.dep_id}_sal_drift.nc"
    elif args.variable == 'conductivity':
        filename = f"{args.dep_id}_cond_drift.nc"
    else:
        filename = f"{args.dep_id}_dens_drift.nc"
    
    print(f"\nReading {filename}...")
    print("=" * 60)
    
    # Read the netCDF file
    ds = xr.open_dataset(filename)
    
    # Display global metadata
    print("\nGlobal Attributes:")
    print("-" * 60)
    for attr, value in ds.attrs.items():
        print(f"  {attr}: {value}")
    
    # Display data variables
    print("\nData Variables:")
    print("-" * 60)
    for var_name in ds.data_vars:
        var = ds[var_name]
        print(f"\n  {var_name}:")
        print(f"    Shape: {var.shape}")
        print(f"    Units: {var.attrs.get('units', 'N/A')}")
        print(f"    Long name: {var.attrs.get('long_name', 'N/A')}")
        print(f"    Serial number: {var.attrs.get('serial_number', 'N/A')}")
        print(f"    Depth label: {var.attrs.get('depth_label', 'N/A')}")
        print(f"    Valid data points: {np.sum(~np.isnan(var.values))}")
        print(f"    Data range: [{np.nanmin(var.values):.4f}, {np.nanmax(var.values):.4f}]")
    
    # Display time range
    print("\nTime Coverage:")
    print("-" * 60)
    print(f"  Start: {pd.Timestamp(ds.time.values[0])}")
    print(f"  End: {pd.Timestamp(ds.time.values[-1])}")
    print(f"  Total points: {len(ds.time)}")
    
    # Example: Convert back to pandas DataFrame if needed
    print("\nConverting to pandas DataFrame:")
    print("-" * 60)
    
    # Method 1: Convert entire dataset
    df = ds.to_dataframe()
    print(f"  DataFrame shape: {df.shape}")
    print(f"  Columns: {list(df.columns)[:3]}..." if len(df.columns) > 3 else f"  Columns: {list(df.columns)}")
    
    # Method 2: Access specific variable
    if len(ds.data_vars) > 0:
        first_var = list(ds.data_vars)[0]
        var_series = ds[first_var].to_series()
        print(f"\n  Example - accessing '{first_var}':")
        print(f"    Type: {type(var_series)}")
        print(f"    Length: {len(var_series)}")
        print(f"    First 3 values:\n{var_series.head(3)}")
    
    # Close the dataset
    ds.close()
    
    print("\n" + "=" * 60)
    print("✓ Successfully read and displayed netCDF file")
    print("\nNetCDF advantages demonstrated:")
    print("  • Self-describing format with metadata")
    print("  • Cross-platform and language independent")
    print("  • No Python version compatibility issues")
    print("  • Can be inspected with tools like 'ncdump -h'")
    print("  • Follows CF conventions for oceanographic data")

if __name__ == '__main__':
    main()
