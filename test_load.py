import xarray as xr
import pandas as pd
import sys

filename = sys.argv[1]
ds = xr.open_dataset(filename)

# Reconstruct DataFrame like ncplot_flg.py does
reconstructed_data = pd.DataFrame(index=ds.time.to_index())

for var_name in ds.data_vars:
    serial_number = ds[var_name].attrs.get('serial_number', 'unknown')
    depth_label = ds[var_name].attrs.get('depth_label', 'unknown')
    col_tuple = (1, serial_number, depth_label)
    reconstructed_data[col_tuple] = ds[var_name].values

print(f"\nReconstructed DataFrame:")
print(f"Shape: {reconstructed_data.shape}")
print(f"\nColumns:")
for col in reconstructed_data.columns:
    non_nan = reconstructed_data[col].notna().sum()
    print(f"  {col} -> {non_nan} non-NaN values")

ds.close()
