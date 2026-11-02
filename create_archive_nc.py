"""
Create CF-Compliant Archive NetCDF Files with Embedded Quality Flags

This script merges data netCDF files with their corresponding quality flag files
into a single CF-compliant archive file suitable for distribution and long-term storage.

Usage:
    python create_archive_netcdf.py <data_file.nc>

Example:
    python create_archive_netcdf.py pt005_sal_drift.nc
    python create_archive_netcdf.py pt005_cond_adjusted.nc
    python create_archive_netcdf.py pt005_dens_drift.nc

Output:
    Creates {original_name}_archive.nc with data and QC flags merged
"""

import xarray as xr
import argparse
import os
import sys
from datetime import datetime
import pandas as pd


def determine_flag_file(data_file):
    """
    Determine the appropriate quality flag file for a data file.
    
    Parameters:
    -----------
    data_file : str
        Path to data netCDF file
        
    Returns:
    --------
    tuple
        (flag_filename, data_type) or (None, None) if not determinable
    """
    basename = os.path.basename(data_file)
    
    # Extract deployment ID
    dep_id = basename.split('_')[0]
    
    # Determine data type and corresponding flag file
    if 'sal' in basename.lower():
        flag_file = f"qual_dm_sz_{dep_id}.nc"
        data_type = 'salinity'
    elif 'cond' in basename.lower():
        flag_file = f"qual_dm_sz_{dep_id}.nc"  # Conductivity uses salinity flags
        data_type = 'conductivity'
    elif 'dens' in basename.lower():
        flag_file = f"qual_dm_dz_{dep_id}.nc"
        data_type = 'density'
    else:
        return None, None
    
    return flag_file, data_type


def match_variables(data_ds, flag_ds, data_type):
    """
    Match data variables with their corresponding flag variables.
    
    Parameters:
    -----------
    data_ds : xr.Dataset
        Data dataset
    flag_ds : xr.Dataset
        Quality flag dataset
    data_type : str
        Type of data (salinity, conductivity, density)
        
    Returns:
    --------
    dict
        Dictionary mapping data variable names to flag variable names
    """
    matches = {}
    
    # Get prefix for data variables
    if data_type == 'salinity':
        data_prefix = 'salinity_'
        flag_prefix = 'salinity_flags_'
    elif data_type == 'conductivity':
        data_prefix = 'conductivity_'
        flag_prefix = 'salinity_flags_'  # Conductivity uses salinity flags
    elif data_type == 'density':
        data_prefix = 'density_'
        flag_prefix = 'density_flags_'
    else:
        return matches
    
    # Match variables by serial number and depth
    for data_var in data_ds.data_vars:
        if data_var.startswith(data_prefix):
            # Extract identifiers from data variable
            data_serial = data_ds[data_var].attrs.get('serial_number', '')
            data_depth = data_ds[data_var].attrs.get('depth_label', '')
            
            # Find matching flag variable
            for flag_var in flag_ds.data_vars:
                if flag_var.startswith(flag_prefix):
                    flag_serial = flag_ds[flag_var].attrs.get('serial_number', '')
                    flag_depth = flag_ds[flag_var].attrs.get('depth_label', '')
                    
                    if data_serial == flag_serial and data_depth == flag_depth:
                        matches[data_var] = flag_var
                        break
    
    return matches


def create_archive_file(data_file, flag_file, output_file):
    """
    Create CF-compliant archive file with merged data and quality flags.
    
    Parameters:
    -----------
    data_file : str
        Path to data netCDF file
    flag_file : str
        Path to quality flag netCDF file
    output_file : str
        Path to output archive file
        
    Returns:
    --------
    bool
        True if successful, False otherwise
    """
    try:
        # Load datasets
        print(f"Loading data file: {data_file}")
        data_ds = xr.open_dataset(data_file)
        
        print(f"Loading quality flag file: {flag_file}")
        flag_ds = xr.open_dataset(flag_file)
        
        # Determine data type
        basename = os.path.basename(data_file)
        if 'sal' in basename.lower():
            data_type = 'salinity'
        elif 'cond' in basename.lower():
            data_type = 'conductivity'
        elif 'dens' in basename.lower():
            data_type = 'density'
        else:
            print("Error: Could not determine data type")
            return False
        
        # Match data and flag variables
        print(f"\nMatching {data_type} variables with quality flags...")
        matches = match_variables(data_ds, flag_ds, data_type)
        
        if not matches:
            print("Warning: No matching variables found between data and flags")
            return False
        
        print(f"Found {len(matches)} matching variable pairs")
        
        # Create new dataset starting with data
        archive_ds = data_ds.copy(deep=True)
        
        # Reindex flag data to match data time coordinate if needed
        if not flag_ds.time.equals(data_ds.time):
            print("Reindexing quality flags to match data time coordinate...")
            flag_ds_reindexed = flag_ds.reindex(
                time=data_ds.time,
                method='nearest',
                tolerance=pd.Timedelta('1min')
            )
        else:
            flag_ds_reindexed = flag_ds
        
        # Add quality flag variables with CF-compliant naming and attributes
        for data_var, flag_var in matches.items():
            qc_var_name = f"{data_var}_qc"
            
            # Add QC variable to archive
            archive_ds[qc_var_name] = flag_ds_reindexed[flag_var]
            
            # Set CF-compliant QC attributes
            archive_ds[qc_var_name].attrs = {
                'long_name': f'Quality flags for {data_var}',
                'standard_name': 'status_flag',
                'flag_values': [-2, -1, 0, 1, 2],
                'flag_meanings': 'bad_data missing_data unprocessed good_data_auto good_data_manual',
                'valid_min': -2,
                'valid_max': 2,
                'comment': 'Flag value 2 indicates manually verified good data, -2 indicates manually flagged bad data'
            }
            
            # Link data variable to its QC variable
            if 'ancillary_variables' in archive_ds[data_var].attrs:
                archive_ds[data_var].attrs['ancillary_variables'] += f" {qc_var_name}"
            else:
                archive_ds[data_var].attrs['ancillary_variables'] = qc_var_name
        
        # Update global attributes
        archive_ds.attrs['title'] = archive_ds.attrs.get('title', '') + ' (Archive with QC flags)'
        archive_ds.attrs['history'] = (
            f"{datetime.now().isoformat()}: Merged quality flags from {os.path.basename(flag_file)} "
            f"using create_archive_netcdf.py"
        )
        archive_ds.attrs['comment'] = (
            'This file contains both data and quality control flags in CF-compliant format. '
            'Each data variable has an associated _qc variable containing quality flags. '
            'Use the ancillary_variables attribute to find the QC variable for each data variable.'
        )
        
        # Add processing provenance
        archive_ds.attrs['source_data_file'] = os.path.basename(data_file)
        archive_ds.attrs['source_qc_file'] = os.path.basename(flag_file)
        archive_ds.attrs['archive_creation_date'] = datetime.now().isoformat()
        
        # Save to file
        print(f"\nSaving archive file: {output_file}")
        archive_ds.to_netcdf(output_file, format='NETCDF4', engine='netcdf4')
        
        # Close datasets
        data_ds.close()
        flag_ds.close()
        archive_ds.close()
        
        return True
        
    except Exception as e:
        print(f"Error creating archive file: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_summary(data_file, flag_file, output_file):
    """
    Print summary of the archive file creation.
    
    Parameters:
    -----------
    data_file : str
        Input data file
    flag_file : str
        Input flag file
    output_file : str
        Output archive file
    """
    print("\n" + "="*80)
    print("ARCHIVE FILE CREATED SUCCESSFULLY")
    print("="*80)
    print(f"Input data file:  {data_file}")
    print(f"Input flag file:  {flag_file}")
    print(f"Output file:      {output_file}")
    print("\nArchive file structure:")
    print("  - All original data variables")
    print("  - Quality flag variables (with _qc suffix)")
    print("  - CF-compliant ancillary_variables linkage")
    print("  - Complete metadata and provenance")
    
    # Load and show brief contents
    try:
        ds = xr.open_dataset(output_file)
        data_vars = [v for v in ds.data_vars if not v.endswith('_qc')]
        qc_vars = [v for v in ds.data_vars if v.endswith('_qc')]
        
        print(f"\nData variables: {len(data_vars)}")
        for var in sorted(data_vars):
            print(f"  {var}")
        
        print(f"\nQC variables: {len(qc_vars)}")
        for var in sorted(qc_vars):
            print(f"  {var}")
        
        ds.close()
    except:
        pass
    
    print("\nTo view contents:")
    print(f"  ncdump -h {output_file}")
    print(f"  python -c \"import xarray as xr; print(xr.open_dataset('{output_file}'))\"")
    print("="*80 + "\n")


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description='Create CF-compliant archive netCDF with embedded quality flags',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python create_archive_netcdf.py pt005_sal_drift.nc
  python create_archive_netcdf.py pt005_cond_adjusted.nc
  python create_archive_netcdf.py pt005_dens_drift.nc

The script will automatically find the matching quality flag file
(qual_dm_sz_*.nc or qual_dm_dz_*.nc) and create an archive file
with the suffix '_archive.nc'.
        """
    )
    parser.add_argument('data_file', help='Input data netCDF file')
    parser.add_argument(
        '-o', '--output',
        help='Output archive filename (default: {input}_archive.nc)',
        default=None
    )
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.data_file):
        print(f"Error: Data file not found: {args.data_file}")
        sys.exit(1)
    
    # Determine flag file
    flag_file, data_type = determine_flag_file(args.data_file)
    
    if flag_file is None:
        print(f"Error: Could not determine data type from filename: {args.data_file}")
        print("Expected filename pattern: {dep_id}_sal/cond/dens_*.nc")
        sys.exit(1)
    
    if not os.path.exists(flag_file):
        print(f"Error: Quality flag file not found: {flag_file}")
        print(f"Please run flag_sal_netcdf.py first to create quality flags")
        sys.exit(1)
    
    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        base = os.path.splitext(args.data_file)[0]
        output_file = f"{base}_archive.nc"
    
    print("="*80)
    print("CF-COMPLIANT ARCHIVE NETCDF CREATOR")
    print("="*80)
    print(f"Data type: {data_type}")
    print(f"Input data file:  {args.data_file}")
    print(f"Quality flag file: {flag_file}")
    print(f"Output file:      {output_file}")
    print("="*80 + "\n")
    
    # Create archive file
    success = create_archive_file(args.data_file, flag_file, output_file)
    
    if success:
        print_summary(args.data_file, flag_file, output_file)
    else:
        print("\nArchive file creation failed.")
        sys.exit(1)


if __name__ == '__main__':
    main()
