import xarray as xr
import sys

filename = sys.argv[1]
ds = xr.open_dataset(filename)

print(f"\nVariables in {filename}:")
print("="*60)
for var_name in sorted(ds.data_vars):
    var = ds[var_name]
    depth_label = var.attrs.get('depth_label', 'unknown')
    serial = var.attrs.get('serial_number', 'unknown')
    print(f"  {var_name:30} -> depth: {depth_label:6} serial: {serial}")

ds.close()
