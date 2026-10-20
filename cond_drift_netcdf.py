import gsw
from tao.flex.data import Deployment
import pandas as pd
import numpy as np
import xarray as xr
import os
import argparse
import sys
from datetime import datetime
from bokeh.plotting import figure, show
from bokeh.layouts import gridplot
from bokeh.models import Legend, Title
from bokeh.io import output_notebook, output_file

# argument parser
parser = argparse.ArgumentParser(description='Process TAO deployment data')
parser.add_argument('dep_id', type=str, help='Deployment ID (e.g., pt006)')
args = parser.parse_args()

# Load deployment data
dep_id = args.dep_id
home = os.path.expanduser("~")

# Define the base path for both data and config files
base_path = (
    home
    + "/data/flexram/"
    + dep_id
    + "-proc"
    + "/data/subsurface/"
)

print(base_path + dep_id + "-sbe-data.bz2")

dep_id = Deployment(
    base_path + dep_id + "-sbe-data.bz2",
    metaSrc=base_path + "config.xml",
)


# Check if postcalibration coefficients exist
def check_postcals(deployment):
    for sn in set(col[1] for col in deployment.CZ.data.columns):
        if len(deployment.CZ.meta.postcalcoef[1, sn]) == 0:
            print(f"No postcalibration coefficients available for instrument {sn}")
            return False
    return True

if not check_postcals(dep_id):
    print("Exiting program: No postcalibration coefficients available for one or more instruments")
    sys.exit(1)

def calculate_conductivity(f, coeffs):
    result = 0
    for i, coeff in enumerate(coeffs):
        result += coeff * (f ** i)
    return result

def dataframe_to_dataset(df, variable_name, units, long_name, deployment_id, lat, lon):
    """
    Convert a pandas DataFrame with multi-level columns to an xarray Dataset.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with multi-index columns (type, serial_number, depth_label)
    variable_name : str
        Name for the data variable (e.g., 'conductivity', 'salinity', 'density')
    units : str
        Units of the variable (e.g., 'mS/cm', 'PSU', 'kg/m^3')
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
    # Create a dictionary to hold data variables
    data_vars = {}
    
    for col in df.columns:
        # Extract instrument serial number and depth label
        _, serial_number, depth_label = col
        
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
    ds.attrs['latitude'] = lat
    ds.attrs['longitude'] = lon
    ds.attrs['creation_date'] = datetime.now().isoformat()
    ds.attrs['institution'] = 'NOAA/PMEL'
    ds.attrs['source'] = 'TAO/TRITON mooring array'
    ds.attrs['conventions'] = 'CF-1.8'
    
    # Add time attributes
    ds.time.attrs['standard_name'] = 'time'
    ds.time.attrs['long_name'] = 'time'
    
    return ds

def apply_time_dependent_drift(original_values, differences, timestamps, start_time, end_time):
    """
    Apply time-dependent drift correction, excluding NaN values from the calculation
    """
    # Create mask for non-NaN values
    valid_mask = ~np.isnan(original_values)

    # Calculate percentage of valid data
    valid_data_percentage = (np.sum(valid_mask) / len(original_values)) * 100

    # Find first and last valid data points
    valid_indices = np.where(valid_mask)[0]
    if len(valid_indices) == 0:
        return original_values, None, None, 0  # Return original if all values are NaN

    first_valid_idx = valid_indices[0]
    last_valid_idx = valid_indices[-1]

    # Get corresponding timestamps for valid data
    valid_start_time = timestamps[first_valid_idx]
    valid_end_time = timestamps[last_valid_idx]

    # Calculate deployment duration using only valid data period
    deployment_duration = (valid_end_time - valid_start_time).total_seconds()

    # Initialize corrected values array
    corrected_values = original_values.copy()

    # Calculate time elapsed for valid points only
    for idx in valid_indices:
        time_elapsed = (timestamps[idx] - valid_start_time).total_seconds()
        drift_fraction = time_elapsed / deployment_duration
        corrected_values[idx] = original_values[idx] + (differences[idx] * drift_fraction)

    return corrected_values, valid_start_time, valid_end_time, valid_data_percentage

# Get conductivity data and timestamps
cz = dep_id.CZ.data
dfcz = cz.copy()
c_array = dfcz.to_numpy()

# Get deployment start and end times from the data index
start_time = dfcz.index[0]
end_time = dfcz.index[-1]

print(f"\nFull Deployment period: {start_time} to {end_time}")

# Get unique instrument serial numbers
instruments = set(col[1] for col in dfcz.columns)

# Dictionary to store calibration coefficients and results
pre_coeffs = {}
post_coeffs = {}
pre_cond = {}
post_cond = {}
differences = {}
valid_periods = {}  # Store valid data periods for each sensor

# Get calibration coefficients for each instrument
for sn in instruments:
    try:
        pre_coeffs[sn] = dep_id.CZ.meta.precalcoef[1, sn]
        post_coeffs[sn] = dep_id.CZ.meta.postcalcoef[1, sn]

        if len(post_coeffs[sn]) == 0:
            print(f"No postcalibration coefficients available for instrument {sn}")
            sys.exit(1)

        pre_cond[sn] = np.zeros_like(c_array)
        post_cond[sn] = np.zeros_like(c_array)
        differences[sn] = np.zeros_like(c_array)
        valid_periods[sn] = {}
    except KeyError:
        print(f"No calibration coefficients found for instrument {sn}")

# Calculate conductivity and differences
for i in range(c_array.shape[1]):
    column_idx = dfcz.columns[i]
    instrument_sn = column_idx[1]
    if instrument_sn in pre_coeffs:
        pre_cond[instrument_sn][:, i] = calculate_conductivity(c_array[:, i], pre_coeffs[instrument_sn])
        post_cond[instrument_sn][:, i] = calculate_conductivity(c_array[:, i], post_coeffs[instrument_sn])
        differences[instrument_sn][:, i] = post_cond[instrument_sn][:, i] - pre_cond[instrument_sn][:, i]

# Create DataFrame for time-dependent adjusted conductivity
cond_drift = pd.DataFrame(index=dfcz.index)

# Apply time-dependent drift correction
print("\nValid Data Periods for Each Sensor:")
print("-----------------------------------")

for i in range(c_array.shape[1]):
    column_idx = dfcz.columns[i]
    instrument_sn = column_idx[1]
    if instrument_sn in pre_coeffs:
        # Get the difference values for this column
        diff_values = differences[instrument_sn][:, i]

        # Apply time-dependent drift correction
        corrected_conductivity, valid_start, valid_end, valid_percentage = apply_time_dependent_drift(
            c_array[:, i],
            diff_values,
            dfcz.index,
            start_time,
            end_time
        )

        # Store valid period information
        valid_periods[instrument_sn][column_idx] = {
            'start': valid_start,
            'end': valid_end,
            'valid_percentage': valid_percentage
        }

        # Print valid period information
        print(f"\nSensor {instrument_sn} at {column_idx[2]}:")
        print(f"Valid data period: {valid_start} to {valid_end}")
        print(f"Valid data percentage: {valid_percentage:.2f}%")

        # Convert to mS/cm and add to DataFrame
        column_name = (1, column_idx[1], column_idx[2])
        cond_drift[column_name] = corrected_conductivity * 10

# Calculate salinity with time-dependent drift correction
n_instruments = c_array.shape[1]
original_salinity = {}
corrected_salinity = {}

for i in range(n_instruments):
    column_idx = dfcz.columns[i]
    instrument_sn = column_idx[1]

    if instrument_sn in pre_coeffs:
        # Get temperature data
        temp_label = column_idx[2].replace('C', 'T')
        temperature = dep_id.TZ.data[1, instrument_sn if temp_label == 'SST' else column_idx[1], temp_label]

        # Set pressure based on depth
        if column_idx[2] == 'SSC':
            depth = 0
        else:
            depth = float(''.join(filter(str.isdigit, column_idx[2])))
        pressure = np.full_like(temperature, depth)

        # Get original and corrected conductivity
        conductivity = dfcz[column_idx] * 10  # Convert to S/m
        conductivity_corrected = cond_drift[column_idx]

        # Remove NaN values
        mask = ~np.isnan(conductivity) & ~np.isnan(temperature)

        try:
            # Calculate salinity
            original_salinity[column_idx] = gsw.SP_from_C(
                conductivity[mask],
                temperature[mask],
                pressure[mask]
            )

            corrected_salinity[column_idx] = gsw.SP_from_C(
                conductivity_corrected[mask],
                temperature[mask],
                pressure[mask]
            )
        except Exception as e:
            print(f"Error calculating salinity for sensor {column_idx}: {str(e)}")
            continue

# Create and save salinity DataFrames
sal_drift = pd.DataFrame(index=dfcz.index)
sal_orig = pd.DataFrame(index=dfcz.index)

for column_idx in corrected_salinity.keys():
    # Handle SSC to SSS conversion correctly
    if column_idx[2] == 'SSC':
        new_label = 'SSS'
    else:
        new_label = column_idx[2].replace('C', 'S')

    column_name = (1, column_idx[1], new_label)
    sal_drift[column_name] = pd.Series(corrected_salinity[column_idx], index=dfcz.index[~np.isnan(dfcz[column_idx])])
    sal_orig[column_name] = pd.Series(original_salinity[column_idx], index=dfcz.index[~np.isnan(dfcz[column_idx])])

# Save conductivity drift file as netCDF
cond_filename = f"{args.dep_id}_cond_drift.nc"
cond_ds = dataframe_to_dataset(
    cond_drift,
    variable_name='conductivity',
    units='mS/cm',
    long_name='Drift-corrected conductivity',
    deployment_id=args.dep_id,
    lat=dep_id.latitude,
    lon=dep_id.longitude
)
cond_ds.attrs['processing'] = 'Time-dependent drift correction applied using pre- and post-deployment calibration coefficients'
cond_ds.to_netcdf(cond_filename, format='NETCDF4', engine='netcdf4')
print(f"Saved conductivity to {cond_filename}")

# Calculate and save density with fixed temperature label handling
dens_drift = pd.DataFrame(index=dfcz.index)

for column in sal_drift.columns:
    try:
        # Get corresponding temperature data with corrected label handling
        if column[2] == 'SSS':
            temp_label = 'SST'
        else:
            temp_label = column[2].replace('S', 'T')

        temperature = dep_id.TZ.data[1, column[1], temp_label]

        # Set pressure based on depth
        if column[2] == 'SSS':
            depth = 0
        else:
            depth = float(''.join(filter(str.isdigit, column[2])))
        pressure = np.full_like(temperature, depth)

        # Calculate density using sigma0
        valid_mask = ~np.isnan(sal_drift[column]) & ~np.isnan(temperature)

        # Convert inputs to numpy arrays with float64 dtype
        SP = np.asarray(sal_drift[column][valid_mask].values, dtype=np.float64).flatten()
        temp = np.asarray(temperature[valid_mask].values, dtype=np.float64).flatten()
        pres = np.asarray(pressure[valid_mask], dtype=np.float64).flatten()

        # Ensure longitude and latitude are float64
        lon = np.float64(dep_id.longitude)
        lat = np.float64(dep_id.latitude)

        # Calculate Absolute Salinity
        SA = gsw.SA_from_SP(SP, pres, lon, lat)

        # Calculate Conservative Temperature
        CT = gsw.CT_from_t(SA, temp, pres)

        # Calculate potential density anomaly (sigma0)
        density = gsw.density.sigma0(SA, CT)

        # Store in DataFrame
        # Map salinity depth labels to density depth labels
        # SSS -> SSD (Sea Surface Density), S010 -> D010, etc.
        sal_depth_label = column[2]
        if sal_depth_label == 'SSS':
            dens_depth_label = 'SSD'
        else:
            dens_depth_label = sal_depth_label.replace('S', 'D')
        
        dens_column = (1, column[1], dens_depth_label)
        dens_drift[dens_column] = pd.Series(density, index=dfcz.index[valid_mask])

    except Exception as e:
        print(f"Error calculating density for sensor {column}: {str(e)}")
        continue

# Save density file as netCDF
dens_filename = f"{args.dep_id}_dens_drift.nc"
dens_ds = dataframe_to_dataset(
    dens_drift,
    variable_name='density',
    units='kg/m^3',
    long_name='Potential density anomaly (sigma0)',
    deployment_id=args.dep_id,
    lat=dep_id.latitude,
    lon=dep_id.longitude
)
dens_ds.attrs['processing'] = 'Calculated from drift-corrected salinity using GSW toolbox'
dens_ds.attrs['reference_pressure'] = '0 dbar'
dens_ds.to_netcdf(dens_filename, format='NETCDF4', engine='netcdf4')
print(f"Saved density to {dens_filename}")

# Save salinity file as netCDF
sal_filename = f"{args.dep_id}_sal_drift.nc"
sal_ds = dataframe_to_dataset(
    sal_drift,
    variable_name='salinity',
    units='PSU',
    long_name='Practical salinity (drift-corrected)',
    deployment_id=args.dep_id,
    lat=dep_id.latitude,
    lon=dep_id.longitude
)
sal_ds.attrs['processing'] = 'Calculated from drift-corrected conductivity using GSW toolbox'
sal_ds.attrs['standard_name'] = 'sea_water_practical_salinity'
sal_ds.to_netcdf(sal_filename, format='NETCDF4', engine='netcdf4')
print(f"Saved salinity to {sal_filename}")

print("\nCreating comparison plots...")

# Create Bokeh plot output file
plot_filename = f"{args.dep_id}_salinity_comparison.html"
output_file(plot_filename)
print(f"Plot output file: {plot_filename}")

# Calculate number of rows and columns for the subplot grid
n_cols = 2
n_rows = (len(sal_orig.columns) + n_cols - 1) // n_cols

# Create list to hold plots
plots = []

# Create plots for each sensor
for column in sal_orig.columns:
    # Skip if no data
    if sal_orig[column].empty or sal_drift[column].empty:
        continue

    # Create figure
    p = figure(width=600, height=400,
               x_axis_type='datetime',
               title=f'Salinity Comparison at {column[2]}')

    try:
        # Calculate statistics
        valid_mask = ~np.isnan(sal_orig[column]) & ~np.isnan(sal_drift[column])
        salinity_diff = sal_drift[column][valid_mask] - sal_orig[column][valid_mask]
        mean_diff = np.nanmean(salinity_diff)
        std_diff = np.nanstd(salinity_diff)

        # Plot original data
        # Get datetime index - check if already timezone-aware
        x_data = sal_orig.index[valid_mask]
        if x_data.tz is None:
            # If not timezone-aware, add UTC timezone
            x_data = pd.to_datetime(x_data).tz_localize('UTC')
        
        p.line(x_data,
               sal_orig[column][valid_mask],
               line_color='blue',
               line_alpha=0.7,
               legend_label='Original')

        # Plot corrected data
        p.line(x_data,
               sal_drift[column][valid_mask],
               line_color='red',
               line_alpha=0.7,
               legend_label='Corrected')

        # Add statistics text
        stats_text = f'Mean diff: {mean_diff:.6f}\nStd dev: {std_diff:.6f}'
        p.add_layout(Title(text=stats_text, align='left'), 'above')

        # Configure legend
        p.legend.click_policy = 'hide'
        p.legend.location = 'top_left'

        # Customize plot
        p.xaxis.axis_label = 'Time'
        p.yaxis.axis_label = 'Salinity (PSU)'
        p.grid.grid_line_alpha = 0.3

        plots.append(p)

    except Exception as e:
        print(f"Error creating plot for sensor {column}: {str(e)}")
        continue

if plots:  # Only create grid if there are plots
    print(f"\nCreated {len(plots)} subplot(s)")
    # Create the grid of plots
    grid = gridplot(plots, ncols=n_cols)

    # Show the plot
    print(f"Saving plot to {plot_filename}...")
    show(grid)
    print(f"✓ Plot saved successfully to {plot_filename}")
else:
    print("No valid data to plot")

# Create Salnotes file
print("\nCreating Salnotes file...")
salnotes_filename = f"{args.dep_id}_Salnotes.txt"
try:
    with open(salnotes_filename, 'w') as f:
        # Write header information
        f.write(f"Deployment: {args.dep_id}\n")
        f.write(f"Full deployment period: {start_time} to {end_time}\n\n")

        # Write Instrument Coefficients section
        f.write("Instrument Coefficients:\n")
        f.write("------------------------\n")

        # Find SSC instrument first
        ssc_sn = None
        for sn in instruments:
            for column_idx in valid_periods[sn]:
                if column_idx[2] == 'SSC':
                    ssc_sn = sn
                    break
            if ssc_sn:
                break

        # Write SSC instrument first, then others
        ordered_instruments = sorted([sn for sn in instruments if sn != ssc_sn])
        if ssc_sn:
            ordered_instruments.insert(0, ssc_sn)

        for sn in ordered_instruments:
            if sn in pre_coeffs and sn in post_coeffs:
                f.write(f"\nInstrument {sn}:\n")
                pre_coeff_str = ", ".join(f"{x:.6e}" for x in pre_coeffs[sn])
                post_coeff_str = ", ".join(f"{x:.6e}" for x in post_coeffs[sn])
                f.write(f"Pre-calibration coefficients: {pre_coeff_str}\n")
                f.write(f"Post-calibration coefficients: {post_coeff_str}\n")

# Write Mean Differences section
        f.write("\nSalinity Drift\n")
        f.write("------------------\n")

        mean_diffs = []
        for column_idx in original_salinity:
            if column_idx in corrected_salinity:
                sal_diff = corrected_salinity[column_idx] - original_salinity[column_idx]
                mean_diff = np.nanmean(sal_diff)

                # Convert depth label
                depth_label = column_idx[2]
                if depth_label == 'SSC':
                    depth_label = 'SSC'
                else:
                    depth_label = 'S' + depth_label[1:]

                mean_diffs.append((depth_label, mean_diff))

        # Sort mean differences (SSC first, then by depth)
        def mean_diff_sort_key(x):
            label = x[0]
            if label == 'SSC':
                return (-1, '')
            return (0, int(''.join(filter(str.isdigit, label))))

        mean_diffs.sort(key=mean_diff_sort_key)

        # Write mean differences with aligned values and + signs
        for label, mean_diff in mean_diffs:
            sign = '+' if mean_diff >= 0 else ''
            f.write(f"{label:>4} = {sign}{mean_diff:8.6f}\n")
        # Force write to disk
        f.flush()
        os.fsync(f.fileno())
    
    print(f"✓ Salnotes file created: {salnotes_filename}")

except Exception as e:
    print(f"Error creating Salnotes file: {str(e)}")

# Verify file was written
try:
    with open(salnotes_filename, 'r') as f:
        content = f.read()
        print(f"\nFile content length: {len(content)} characters")
        if len(content) == 0:
            print("Warning: File is empty after writing")
        else:
            print("File was written successfully")
except Exception as e:
    print(f"Error verifying file contents: {str(e)}")


print(f"\n" + "="*60)
print(f"PROCESSING COMPLETE")
print("="*60)
print(f"\nOutput files:")
print(f"  Conductivity: {cond_filename}")
print(f"  Density:      {dens_filename}")
print(f"  Salinity:     {sal_filename}")
print(f"  Plot:         {plot_filename}")
print(f"  Salnotes:     {salnotes_filename}")
print(f"\nAll files saved in current directory: {os.getcwd()}")
print("="*60)
