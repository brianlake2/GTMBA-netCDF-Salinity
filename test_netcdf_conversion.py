#!/usr/bin/env python3
"""
Test script to verify netCDF conversion is working correctly

This script performs basic validation tests on the netCDF output files.
Run this after processing a deployment to verify the files are valid.

Usage:
    python test_netcdf_conversion.py pt006
"""

import xarray as xr
import numpy as np
import argparse
import os
import sys

def test_file_exists(filename):
    """Test if file exists"""
    if os.path.exists(filename):
        print(f"  ✓ {filename} exists")
        return True
    else:
        print(f"  ✗ {filename} not found")
        return False

def test_file_readable(filename):
    """Test if file can be opened and read"""
    try:
        ds = xr.open_dataset(filename)
        ds.close()
        print(f"  ✓ {filename} is readable")
        return True
    except Exception as e:
        print(f"  ✗ {filename} cannot be read: {e}")
        return False

def test_has_variables(filename):
    """Test if file has data variables"""
    try:
        ds = xr.open_dataset(filename)
        n_vars = len(ds.data_vars)
        ds.close()
        if n_vars > 0:
            print(f"  ✓ {filename} has {n_vars} data variables")
            return True
        else:
            print(f"  ✗ {filename} has no data variables")
            return False
    except Exception as e:
        print(f"  ✗ Error checking variables: {e}")
        return False

def test_has_metadata(filename):
    """Test if file has required global attributes"""
    required_attrs = ['deployment_id', 'creation_date', 'institution']
    try:
        ds = xr.open_dataset(filename)
        missing = [attr for attr in required_attrs if attr not in ds.attrs]
        ds.close()
        
        if not missing:
            print(f"  ✓ {filename} has required metadata")
            return True
        else:
            print(f"  ✗ {filename} missing attributes: {missing}")
            return False
    except Exception as e:
        print(f"  ✗ Error checking metadata: {e}")
        return False

def test_variable_attributes(filename):
    """Test if variables have required attributes"""
    required_attrs = ['units', 'long_name']
    try:
        ds = xr.open_dataset(filename)
        issues = []
        
        for var_name in ds.data_vars:
            var = ds[var_name]
            missing = [attr for attr in required_attrs if attr not in var.attrs]
            if missing:
                issues.append(f"{var_name} missing {missing}")
        
        ds.close()
        
        if not issues:
            print(f"  ✓ {filename} variables have required attributes")
            return True
        else:
            print(f"  ✗ {filename} attribute issues:")
            for issue in issues:
                print(f"      {issue}")
            return False
    except Exception as e:
        print(f"  ✗ Error checking variable attributes: {e}")
        return False

def test_has_time_dimension(filename):
    """Test if file has time dimension"""
    try:
        ds = xr.open_dataset(filename)
        has_time = 'time' in ds.dims
        ds.close()
        
        if has_time:
            print(f"  ✓ {filename} has time dimension")
            return True
        else:
            print(f"  ✗ {filename} missing time dimension")
            return False
    except Exception as e:
        print(f"  ✗ Error checking time dimension: {e}")
        return False

def test_data_values(filename):
    """Test if file has valid (non-all-NaN) data"""
    try:
        ds = xr.open_dataset(filename)
        has_valid_data = False
        
        for var_name in ds.data_vars:
            if not np.all(np.isnan(ds[var_name].values)):
                has_valid_data = True
                break
        
        ds.close()
        
        if has_valid_data:
            print(f"  ✓ {filename} contains valid data")
            return True
        else:
            print(f"  ✗ {filename} contains only NaN values")
            return False
    except Exception as e:
        print(f"  ✗ Error checking data values: {e}")
        return False

def test_cf_compliance(filename):
    """Test basic CF compliance"""
    try:
        ds = xr.open_dataset(filename)
        
        # Check for conventions attribute
        has_conventions = 'conventions' in ds.attrs or 'Conventions' in ds.attrs
        
        # Check time has standard attributes
        time_ok = ('standard_name' in ds.time.attrs or 
                  'long_name' in ds.time.attrs)
        
        ds.close()
        
        if has_conventions and time_ok:
            print(f"  ✓ {filename} follows CF conventions")
            return True
        else:
            if not has_conventions:
                print(f"  ⚠ {filename} missing conventions attribute")
            if not time_ok:
                print(f"  ⚠ {filename} time coordinate needs attributes")
            return False
    except Exception as e:
        print(f"  ✗ Error checking CF compliance: {e}")
        return False

def run_all_tests(dep_id):
    """Run all tests for a deployment"""
    print(f"\nTesting NetCDF files for deployment: {dep_id}")
    print("=" * 60)
    
    files = [
        f"{dep_id}_cond_drift.nc",
        f"{dep_id}_sal_drift.nc",
        f"{dep_id}_dens_drift.nc"
    ]
    
    all_passed = True
    
    for filename in files:
        print(f"\nTesting {filename}:")
        print("-" * 60)
        
        tests = [
            test_file_exists,
            test_file_readable,
            test_has_variables,
            test_has_metadata,
            test_variable_attributes,
            test_has_time_dimension,
            test_data_values,
            test_cf_compliance,
        ]
        
        file_passed = True
        for test in tests:
            if not test(filename):
                file_passed = False
                all_passed = False
        
        if file_passed:
            print(f"\n  ✅ All tests passed for {filename}")
        else:
            print(f"\n  ❌ Some tests failed for {filename}")
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
        print("\nNetCDF files are valid and ready to use!")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        print("\nPlease review the issues above.")
        return 1

def main():
    parser = argparse.ArgumentParser(
        description='Test netCDF output files from cond_drift.py'
    )
    parser.add_argument('dep_id', type=str, 
                       help='Deployment ID (e.g., pt006)')
    
    args = parser.parse_args()
    
    sys.exit(run_all_tests(args.dep_id))

if __name__ == '__main__':
    main()
