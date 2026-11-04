"""
Apply Hanning Filter to netCDF Data

This script applies a Hanning window filter to smooth salinity, conductivity, 
and density data from netCDF files.

Usage:
    python hanning.py <deployment_id>

Example:
    python hanning.py pt005
"""

import pandas as pd
import numpy as np
import xarray as xr
import sys
import os
from datetime import datetime


def apply_hanning_filter(data, window_size=24):
    """
    Apply Hanning filter to smooth the data
    
    Parameters:
    -----------
    data : pd.DataFrame
        Data to smooth with multi-index columns
    window_size : int
        Window size in hours (default 24 hours)
        
    Returns:
    --------
    pd.DataFrame
        Smoothed data
    """
    # Create Hanning window using numpy
    hanning_window = np.hanning(window_size)
    hanning_window = hanning_window / np.sum(hanning_window)  # Normalize

    # Apply to each column
    smoothed_data = pd.DataFrame(index=data.index, columns=data.columns)
    for column in data.columns:
        series = data[column].copy()
        mask = ~series.isna()

        if mask.any():
            valid_data = series[mask].values

            # Pad the data to handle edges
            pad_width = window_size // 2
            padded_data = np.pad(valid_data, (pad_width, pad_width), mode="edge")

            # Apply convolution
            smoothed_valid = np.convolve(padded_data, hanning_window, mode="same")

            # Trim the padded portions to match original length
            smoothed_valid = smoothed_valid[pad_width:-pad_width]

            # Ensure lengths match
            if len(smoothed_valid) > len(series[mask]):
                smoothed_valid = smoothed_valid[: len(series[mask])]
            elif len(smoothed_valid) < len(series[mask]):
                # Pad with the last value if needed
                smoothed_valid = np.pad(
                    smoothed_valid,
                    (0, len(series[mask]) - len(smoothed_valid)),
                    mode="edge",
                )

            # Create temporary series and assign values
            temp_series = pd.Series(index=series[mask].index, data=smoothed_valid)
            smoothed_data[column] = temp_series

    return smoothed_data


def load_netcdf_data(filename):
    """
    Load netCDF file and convert to pandas DataFrame with multi-index columns
    
    Parameters:
    -----------
    filename : str
        Path to netCDF file
        
    Returns:
    --------
    pd.DataFrame
        DataFrame with multi-index columns (instance, serial, depth_label)
    """
    try:
        ds = xr.open_dataset(filename)
        print(f"Loaded {filename}")
        print(f"  Variables: {len(ds.data_vars)}")
        print(f"  Time points: {len(ds.time)}")
        
        # Reconstruct multi-index columns from variable names
        reconstructed_data = pd.DataFrame(index=ds.time.to_index())
        
        for var_name in sorted(ds.data_vars):
            # Get attributes
            serial_number = ds[var_name].attrs.get('serial_number', 'unknown')
            depth_label = ds[var_name].attrs.get('depth_label', 'unknown')
            
            # Create multi-index column tuple (1, serial_number, depth_label)
            col_tuple = (1, serial_number, depth_label)
            
            # Add to DataFrame
            reconstructed_data[col_tuple] = ds[var_name].values
        
        # Sort columns by depth label
        def depth_sort_key(col):
            depth = col[2]
            if depth.startswith('SS'):  # SSS, SSC, SSD
                return (0, depth)
            else:
                # Extract numeric part for ordering
                import re
                match = re.search(r'\d+', depth)
                if match:
                    return (1, int(match.group()))
                return (2, depth)
        
        reconstructed_data = reconstructed_data[sorted(reconstructed_data.columns, key=depth_sort_key)]
        
        ds.close()
        
        return reconstructed_data
        
    except Exception as e:
        print(f"Error loading netCDF file {filename}: {e}")
        return None


def dataframe_to_dataset(df, variable_name, units, long_name, deployment_id, lat, lon):
    """
    Convert DataFrame to xarray Dataset for netCDF export
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with multi-index columns
    variable_name : str
        Name prefix for variables (e.g., 'salinity', 'conductivity', 'density')
    units : str
        Units of the variable
    long_name : str
        Descriptive name for the variable
    deployment_id : str
        Deployment identifier
    lat : float
        Latitude of deployment
    lon : float
        Longitude of deployment
        
    Returns:
    --------
    xr.Dataset
    """
    data_vars = {}
    
    for col in df.columns:
        # Extract serial number and column name from tuple
        if isinstance(col, tuple):
            # Tuple format: (instance, serial, depth_label)
            serial_number = str(col[1])
            depth_label = col[-1]
        else:
            serial_number = 'unknown'
            depth_label = col
        
        # Extract depth in meters from label
        depth = 0.0
        if depth_label.startswith('SS'):  # Surface
            depth = 0.0
        else:
            import re
            match = re.search(r'\d+', depth_label)
            if match:
                depth = float(match.group())
        
        var_name = f"{variable_name}_{depth_label}"
        
        data_vars[var_name] = (
            ['time'],
            df[col].values,
            {
                'units': units,
                'long_name': f"{long_name} at {depth_label}",
                'serial_number': serial_number,
                'depth_label': depth_label,
                'depth_meters': depth,
            }
        )
    
    # Create the dataset
    ds = xr.Dataset(
        data_vars=data_vars,
        coords={'time': df.index.values},
    )
    
    # Add global attributes
    ds.attrs['deployment_id'] = deployment_id
    ds.attrs['latitude'] = lat
    ds.attrs['longitude'] = lon
    ds.attrs['creation_date'] = datetime.now().isoformat()
    ds.attrs['institution'] = 'NOAA/PMEL'
    ds.attrs['source'] = 'GTMBA mooring array'
    ds.attrs['conventions'] = 'CF-1.8'
    ds.attrs['processing'] = f'Hanning filter applied (window size: 24 hours)'
    
    # Add time attributes
    ds.time.attrs['standard_name'] = 'time'
    ds.time.attrs['long_name'] = 'time'
    
    return ds


def get_deployment_metadata(deployment_id):
    """
    Try to get deployment metadata from existing netCDF files
    
    Parameters:
    -----------
    deployment_id : str
        Deployment identifier
        
    Returns:
    --------
    tuple
        (latitude, longitude)
    """
    # Try to load metadata from existing adjusted files
    for suffix in ['sal_adjusted', 'cond_adjusted', 'dens_adjusted']:
        filename = f"{deployment_id}_{suffix}.nc"
        if os.path.exists(filename):
            try:
                ds = xr.open_dataset(filename)
                lat = ds.attrs.get('latitude', 0.0)
                lon = ds.attrs.get('longitude', 0.0)
                ds.close()
                return lat, lon
            except:
                continue
    
    # Default values if no file found
    return 0.0, 0.0


def load_and_smooth_data(deployment_id):
    """
    Load and smooth data for a given deployment ID
    
    Parameters:
    -----------
    deployment_id : str
        Deployment identifier (e.g., 'pt005')
        
    Returns:
    --------
    tuple
        (data_dict, smoothed_dict) - dictionaries of original and smoothed data
    """
    # File patterns
    file_types = {
        'sal': 'salinity',
        'cond': 'conductivity', 
        'dens': 'density'
    }
    files = {ftype: f"{deployment_id}_{ftype}_adjusted.nc" for ftype in file_types.keys()}

    # Load data
    data_dict = {}
    for ftype, fname in files.items():
        if os.path.exists(fname):
            data = load_netcdf_data(fname)
            if data is not None:
                data_dict[ftype] = data
        else:
            print(f"Warning: Could not find {fname}")

    if not data_dict:
        print("Error: No netCDF data files found")
        print(f"Expected files: {', '.join(files.values())}")
        sys.exit(1)

    # Apply Hanning filter to each dataset
    smoothed_dict = {}
    print("\nApplying Hanning filter...")
    for ftype, data in data_dict.items():
        print(f"  Smoothing {ftype}...")
        smoothed_dict[ftype] = apply_hanning_filter(data)

    return data_dict, smoothed_dict


def main():
    if len(sys.argv) != 2:
        print("Usage: python hanning.py deployment_id")
        print("Example: python hanning.py pt005")
        sys.exit(1)

    deployment_id = sys.argv[1]

    # Load and smooth data
    original_data, smoothed_data = load_and_smooth_data(deployment_id)
    
    # Get deployment metadata
    lat, lon = get_deployment_metadata(deployment_id)
    print(f"\nDeployment metadata: lat={lat}, lon={lon}")

    # Save smoothed data to netCDF files
    print("\nSaving smoothed data to netCDF files...")
    
    file_types = {
        'sal': ('salinity', 'PSU', 'Sea Water Practical Salinity'),
        'cond': ('conductivity', 'mS/cm', 'Sea Water Conductivity'),
        'dens': ('density', 'kg/m³', 'Sea Water Potential Density')
    }
    
    for data_type, data in smoothed_data.items():
        variable_name, units, long_name = file_types[data_type]
        output_file = f"{deployment_id}_{data_type}_smoothed.nc"
        
        ds = dataframe_to_dataset(
            data,
            variable_name,
            units,
            long_name,
            deployment_id,
            lat,
            lon
        )
        
        ds.to_netcdf(output_file, format='NETCDF4', engine='netcdf4')
        print(f"✓ Saved smoothed {data_type} to {output_file}")


if __name__ == "__main__":
    main()
