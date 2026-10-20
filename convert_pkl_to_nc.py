#!/usr/bin/env python3
"""
Utility script to convert existing pickle files to netCDF format

This script helps migrate legacy pickle files created before the
netCDF conversion to the new self-describing netCDF format.

Usage:
    python convert_pkl_to_nc.py pt006sal_drift.pkl --type salinity --dep-id pt006
"""

import pandas as pd
import xarray as xr
import argparse
from datetime import datetime
import sys
import os

def dataframe_to_dataset(df, variable_name, units, long_name, deployment_id, 
                        lat=None, lon=None):
    """
    Convert a pandas DataFrame with multi-level columns to an xarray Dataset.
    """
    data_vars = {}
    
    for col in df.columns:
        # Handle different column structures
        if isinstance(col, tuple):
            if len(col) == 3:
                _, serial_number, depth_label = col
            else:
                serial_number = col[0]
                depth_label = col[1] if len(col) > 1 else 'unknown'
        else:
            # Single level column
            serial_number = 'unknown'
            depth_label = str(col)
        
        # Create a unique variable name
        var_name = f"{variable_name}_{serial_number}_{depth_label}"
        
        # Add data variable with attributes
        data_vars[var_name] = (
            ['time'],
            df[col].values,
            {
                'units': units,
                'long_name': f"{long_name} at {depth_label}",
                'serial_number': str(serial_number),
                'depth_label': depth_label,
            }
        )
    
    # Create the dataset
    ds = xr.Dataset(
        data_vars=data_vars,
        coords={'time': df.index.values},
    )
    
    # Add global attributes
    ds.attrs['deployment_id'] = deployment_id
    if lat is not None:
        ds.attrs['latitude'] = lat
    if lon is not None:
        ds.attrs['longitude'] = lon
    ds.attrs['creation_date'] = datetime.now().isoformat()
    ds.attrs['institution'] = 'NOAA/PMEL'
    ds.attrs['source'] = 'TAO/TRITON mooring array'
    ds.attrs['conventions'] = 'CF-1.8'
    ds.attrs['history'] = f'Converted from pickle format on {datetime.now().isoformat()}'
    
    # Add time attributes
    ds.time.attrs['standard_name'] = 'time'
    ds.time.attrs['long_name'] = 'time'
    
    return ds


def main():
    parser = argparse.ArgumentParser(
        description='Convert pickle files to netCDF format',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python convert_pkl_to_nc.py pt006sal_drift.pkl --type salinity --dep-id pt006
  python convert_pkl_to_nc.py pt006cond_drift.pkl --type conductivity --dep-id pt006 --lat 0.0 --lon -140.0
  python convert_pkl_to_nc.py pt006dens_drift.pkl --type density --dep-id pt006 --lat 0.0 --lon -140.0
        """
    )
    
    parser.add_argument('pkl_file', type=str, 
                       help='Path to pickle file to convert')
    parser.add_argument('--type', type=str, required=True,
                       choices=['salinity', 'conductivity', 'density'],
                       help='Type of data in the file')
    parser.add_argument('--dep-id', type=str, required=True,
                       help='Deployment ID (e.g., pt006)')
    parser.add_argument('--lat', type=float, default=None,
                       help='Latitude of deployment (optional)')
    parser.add_argument('--lon', type=float, default=None,
                       help='Longitude of deployment (optional)')
    parser.add_argument('--output', type=str, default=None,
                       help='Output filename (default: auto-generated)')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.pkl_file):
        print(f"Error: File '{args.pkl_file}' not found")
        sys.exit(1)
    
    # Load pickle file
    print(f"Loading pickle file: {args.pkl_file}")
    try:
        df = pd.read_pickle(args.pkl_file)
    except Exception as e:
        print(f"Error loading pickle file: {e}")
        sys.exit(1)
    
    print(f"  Shape: {df.shape}")
    print(f"  Columns: {len(df.columns)}")
    print(f"  Time range: {df.index[0]} to {df.index[-1]}")
    
    # Set parameters based on type
    if args.type == 'salinity':
        variable_name = 'salinity'
        units = 'PSU'
        long_name = 'Practical salinity (drift-corrected)'
        processing = 'Calculated from drift-corrected conductivity using GSW toolbox'
    elif args.type == 'conductivity':
        variable_name = 'conductivity'
        units = 'mS/cm'
        long_name = 'Drift-corrected conductivity'
        processing = 'Time-dependent drift correction applied using pre- and post-deployment calibration coefficients'
    else:  # density
        variable_name = 'density'
        units = 'kg/m^3'
        long_name = 'Potential density anomaly (sigma0)'
        processing = 'Calculated from drift-corrected salinity using GSW toolbox'
    
    # Convert to xarray dataset
    print(f"\nConverting to netCDF...")
    ds = dataframe_to_dataset(
        df,
        variable_name=variable_name,
        units=units,
        long_name=long_name,
        deployment_id=args.dep_id,
        lat=args.lat,
        lon=args.lon
    )
    
    # Add processing info
    ds.attrs['processing'] = processing
    
    # Generate output filename if not provided
    if args.output is None:
        output_file = f"{args.dep_id}_{args.type[0:4]}_drift.nc"
    else:
        output_file = args.output
    
    # Save to netCDF
    print(f"Saving to: {output_file}")
    ds.to_netcdf(output_file, format='NETCDF4', engine='netcdf4')
    
    # Verify file was created
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file) / 1024  # KB
        print(f"\n✓ Successfully created netCDF file")
        print(f"  File size: {file_size:.2f} KB")
        print(f"  Variables: {len(ds.data_vars)}")
        print(f"\nYou can inspect the file with:")
        print(f"  ncdump -h {output_file}")
        print(f"  python read_netcdf_example.py {args.dep_id} --variable {args.type}")
    else:
        print(f"\n✗ Error: Output file was not created")
        sys.exit(1)
    
    ds.close()


if __name__ == '__main__':
    main()
