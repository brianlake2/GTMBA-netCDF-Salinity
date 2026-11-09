"""
Salinity Quality Flagging Tool with netCDF Output

Interactive tool for flagging salinity and density data quality for GTMBA moorings.
Saves quality flags to netCDF format files.

Usage:
    python flag_sal_netcdf.py <deployment_id>

Example:
    python flag_sal_netcdf.py pt005
    
The tool will start a Bokeh server and open a browser window with interactive plots.
"""

from tao.flex.data import Deployment
import pandas as pd
import xarray as xr
import numpy as np
import os
import sys
import argparse
from datetime import datetime

from bokeh.plotting import figure, curdoc
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    Button,
    Div,
    DatetimeTickFormatter,
    TextInput
)
from bokeh.layouts import column as bokeh_column, row as bokeh_row, layout


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_sensor_configs(dep):
    """
    Automatically detect sensor configurations from deployment data.
    
    Parameters:
    -----------
    dep : Deployment
        GTMBA deployment object
        
    Returns:
    --------
    list
        List of (column_tuple, depth_label) tuples
    """
    configs = []
    columns = dep.SZ.data.columns
    depth_map = {
        "SSS": "Surface",
        "S001": "1m",
        "S005": "5m",
        "S010": "10m",
        "S015": "15m",
        "S020": "20m",
        "S025": "25m",
        "S040": "40m",
        "S060": "60m",
        "S080": "80m",
        "S100": "100m",
        "S120": "120m",
        "S140": "140m",
        "S180": "180m",
        "S250": "250m",
        "S300": "300m",
        "S500": "500m",
    }

    for col in columns:
        instance, serial, label = col
        if label in depth_map:
            configs.append((col, depth_map[label]))

    return sorted(configs, key=lambda x: list(depth_map.keys()).index(x[0][2]))


def extract_depth_from_label(label):
    """
    Extract numeric depth from a depth label.
    
    Parameters:
    -----------
    label : str
        Depth label (e.g., 'S010', 'SSS')
    
    Returns:
    --------
    float
        Depth in meters (0.0 for SSS)
    """
    if label == 'SSS':
        return 0.0
    
    # Extract digits from label
    digits = ''.join(filter(str.isdigit, label))
    return float(digits) if digits else 0.0


def flags_to_dataset(flags_df, variable_prefix, deployment_id, lat, lon):
    """
    Convert quality flags DataFrame to xarray Dataset.
    
    Parameters:
    -----------
    flags_df : pd.DataFrame
        DataFrame with quality flags (multi-index columns)
    variable_prefix : str
        Prefix for variable names (e.g., 'salinity', 'density')
    deployment_id : str
        Deployment identifier
    lat : float
        Latitude
    lon : float
        Longitude
        
    Returns:
    --------
    xr.Dataset
    """
    data_vars = {}
    
    for col in flags_df.columns:
        instance, serial, depth_label = col
        depth = extract_depth_from_label(depth_label)
        
        var_name = f"{variable_prefix}_flags_{serial}_{depth_label}"
        
        data_vars[var_name] = (
            ['time'],
            flags_df[col].values,
            {
                'long_name': f"Quality flags for {variable_prefix} at {depth_label}",
                'serial_number': str(serial),
                'depth_label': depth_label,
                'depth_meters': depth,
                'flag_meanings': '-2: bad data (manually flagged), -1: missing, 0: unprocessed, 1: good data (auto QC), 2: good data (manual QC)',
                'comment': 'Flag value 2 indicates good data, -2 indicates manually flagged bad data'
            }
        )
    
    # Create the dataset
    ds = xr.Dataset(
        data_vars=data_vars,
        coords={'time': flags_df.index.values},
    )
    
    # Add global attributes
    ds.attrs['deployment_id'] = deployment_id
    ds.attrs['latitude'] = lat
    ds.attrs['longitude'] = lon
    ds.attrs['creation_date'] = datetime.now().isoformat()
    ds.attrs['institution'] = 'NOAA/PMEL'
    ds.attrs['source'] = 'GTMBA mooring array'
    ds.attrs['conventions'] = 'CF-1.8'
    ds.attrs['title'] = f'Quality control flags for {deployment_id}'
    ds.attrs['processing'] = 'Manually flagged using interactive quality control tool'
    
    # Add time attributes
    ds.time.attrs['standard_name'] = 'time'
    ds.time.attrs['long_name'] = 'time'
    
    return ds


# ============================================================================
# ARGUMENT PARSING AND DATA LOADING
# ============================================================================

# Set up argument parser
parser = argparse.ArgumentParser(description="Salinity Flagging Tool with netCDF Output")
parser.add_argument("dep_id", help="Deployment ID (e.g., pt005)")
args = parser.parse_args()

# Load and process data
dep_id = args.dep_id
dep_name = dep_id
home = os.path.expanduser("~")

# Define the base path for both data and config files
base_path = (
    home
    + "/data/flexram/"
    + dep_id
    + "-proc"
    + "/data/subsurface/"
)

# Define full paths for data and config files
data_file = base_path + dep_id + "-sbe-data.bz2"
config_file = base_path + "config.xml"

# Check if necessary files exist
if not os.path.exists(base_path):
    print(f"Error: Base directory not found: {base_path}")
    sys.exit(1)

if not (os.path.exists(data_file) and os.path.exists(config_file)):
    print(f"Error: Required files not found.")
    print(f"Data file: {data_file}")
    print(f"Config file: {config_file}")
    sys.exit(1)

print(f"Loading deployment from: {data_file}")

# Load the deployment
dep = Deployment(
    data_file,
    metaSrc=config_file,
)

# Get sensor configurations automatically
sensor_configs = get_sensor_configs(dep)

# Create sources dictionary to store all ColumnDataSources
sources = {}
plots = {}


# ============================================================================
# CREATE PLOTS AND DATA SOURCES
# ============================================================================

# Create a figure for each sensor
for config, label in sensor_configs:
    # Filter out points where qual_dm is less than 0
    mask = dep.SZ.qual_dm[config] >= 0

    # Create DataFrame for this sensor with filtered data
    df = pd.DataFrame(
        {
            "time": dep.SZ.data.index[mask],
            "salinity": dep.SZ.data[config][mask],
            "flags": dep.SZ.qual_dm[config][mask],
            "colors": [
                "red" if f != 2 else "blue" for f in dep.SZ.qual_dm[config][mask]
            ],
        }
    )

    # Create ColumnDataSource
    sources[label] = ColumnDataSource(df)

    # Create figure
    p = figure(
        width=800,
        height=200,
        tools="box_select,lasso_select,pan,box_zoom,reset,save",
        title=f"{label}",
        x_axis_type="datetime",
        background_fill_color='#eaeaf2'
    )
    
    # Style fonts consistently
    p.title.text_font_size = "14pt"
    p.title.align = "center"
    p.xaxis.major_label_text_font_size = "11pt"
    p.yaxis.major_label_text_font_size = "11pt"
    p.yaxis.axis_label_text_font_size = "11pt"

    # Format x-axis ticks
    p.xaxis.formatter = DatetimeTickFormatter(
        hours="%m/%d/%Y", days="%m/%d/%Y", months="%m/%d/%Y", years="%m/%d/%Y"
    )

    # Plot points
    scatter = p.scatter(
        "time", "salinity", source=sources[label], size=3, color="colors", alpha=0.6
    )

    # Add hover tool
    hover = HoverTool(
        tooltips=[
            ("Time", "@time{%F %H:%M:%S}"),
            ("Salinity", "@salinity{0.000}"),
            ("Flag", "@flags"),
        ],
        formatters={"@time": "datetime"},
    )
    p.add_tools(hover)
    
    # Disable hover by default
    p.toolbar.active_inspect = []

    plots[label] = p


# ============================================================================
# CALLBACK FUNCTIONS
# ============================================================================

def selection_callback(attr, old, new):
    """Update colors and flags when points are selected."""
    for label, src in sources.items():
        if src.selected.indices:
            selected = src.selected.indices
            flags = src.data["flags"].copy()
            colors = src.data["colors"].copy()

            # Set flags to -2 and colors to red for selected points
            flags[selected] = -2
            colors[selected] = "red"

            src.data.update({"flags": flags, "colors": colors})

    # Update statistics after flagging
    update_stats()


# Add selection callback to each source
for label in sources:
    sources[label].selected.on_change("indices", selection_callback)

# Create statistics div
stats_div = Div(text="", width=800)


def update_stats():
    """Update statistics display."""
    stats_text = "<h3>Statistics:</h3><table><tr><th>Depth</th><th>Total Points</th><th>Flagged Points</th><th>Percentage</th></tr>"
    for label in sources.keys():
        flags = sources[label].data["flags"]
        total_points = len(flags)
        flagged_points = sum(1 for f in flags if f != 2)
        percentage = (flagged_points / total_points) * 100
        stats_text += f"<tr><td>{label}</td><td>{total_points}</td><td>{flagged_points}</td><td>{percentage:.2f}%</td></tr>"
    stats_text += "</table>"
    stats_div.text = stats_text


def unflag_points():
    """Unflag selected points (reset flags to 2)."""
    total_unflagged = 0

    for label, source in sources.items():
        if source.selected.indices:
            selected = source.selected.indices

            # Reset flags to 2
            flags = source.data["flags"].copy()
            colors = source.data["colors"].copy()

            flags[selected] = 2
            colors[selected] = "blue"

            source.data.update({"flags": flags, "colors": colors})
            total_unflagged += len(selected)

    update_stats()
    info_div.text = f"Total points unflagged: {total_unflagged}"


def save_flags():
    """Save quality flags to netCDF files."""
    # Create copies of the original qual_dm DataFrames
    updated_sz_qual_dm = dep.SZ.qual_dm.copy()
    updated_dz_qual_dm = dep.DZ.qual_dm.copy()

    # Create a mapping from salinity depth to density depth
    depth_mapping = {
        'SSS': 'SSD',
        'S001': 'D001',
        'S005': 'D005',
        'S010': 'D010',
        'S015': 'D015',
        'S020': 'D020',
        'S025': 'D025',
        'S040': 'D040',
        'S060': 'D060',
        'S080': 'D080',
        'S100': 'D100',
        'S120': 'D120',
        'S140': 'D140',
        'S180': 'D180',
        'S250': 'D250',
        'S300': 'D300',
        'S500': 'D500',
    }

    # Update the flags in both copies
    for config, label in sensor_configs:
        # Get the flags from the source
        new_flags = sources[label].data["flags"]

        # Create a boolean mask for the original salinity data
        s_mask = dep.SZ.qual_dm[config] >= 0

        # Update salinity flags
        full_flags_sz = updated_sz_qual_dm[config].values.copy()
        full_flags_sz[s_mask] = new_flags
        updated_sz_qual_dm[config] = full_flags_sz

        # Find the corresponding density column
        salinity_depth = config[2]
        density_depth = depth_mapping.get(salinity_depth)

        if density_depth:
            # Find columns in DZ that match this density depth
            matching_dz_cols = [col for col in updated_dz_qual_dm.columns if col[2] == density_depth]

            if matching_dz_cols:
                dz_config = matching_dz_cols[0]

                # Get the mask for the density data
                d_mask = dep.DZ.qual_dm[dz_config] >= 0

                # Make sure the masks have the same length
                if len(s_mask) == len(d_mask):
                    # Update density flags
                    full_flags_dz = updated_dz_qual_dm[dz_config].values.copy()
                    full_flags_dz[d_mask] = new_flags
                    updated_dz_qual_dm[dz_config] = full_flags_dz
                    print(f"Updated density flags for {dz_config} (corresponding to {config})")
                else:
                    print(f"Warning: Mask length mismatch between {config} and {dz_config}")
            else:
                print(f"Warning: No density column found for depth {density_depth}")
        else:
            print(f"Warning: No density mapping for salinity depth {salinity_depth}")

    # Define filenames for netCDF format
    sz_nc_filename = f"qual_dm_sz_{dep_id}.nc"
    cz_nc_filename = f"qual_dm_cz_{dep_id}.nc"
    dz_nc_filename = f"qual_dm_dz_{dep_id}.nc"

    # Convert to xarray datasets and save
    try:
        # Save salinity flags to netCDF
        sz_ds = flags_to_dataset(
            updated_sz_qual_dm,
            variable_prefix='salinity',
            deployment_id=dep_id,
            lat=dep.latitude,
            lon=dep.longitude
        )
        sz_ds.attrs['data_type'] = 'salinity_quality_flags'
        sz_ds.to_netcdf(sz_nc_filename, format='NETCDF4', engine='netcdf4')
        print(f"✓ Saved salinity flags to {sz_nc_filename}")
        
        # Create conductivity flags (identical to salinity since same sensors)
        print("Creating conductivity flags (identical to salinity flags)...")
        conductivity_mapping = {
            'SSS': 'SSC',
            'S001': 'C001',
            'S005': 'C005',
            'S010': 'C010',
            'S015': 'C015',
            'S020': 'C020',
            'S025': 'C025',
            'S040': 'C040',
            'S060': 'C060',
            'S080': 'C080',
            'S100': 'C100',
            'S120': 'C120',
            'S140': 'C140',
            'S180': 'C180',
            'S250': 'C250',
            'S300': 'C300',
            'S500': 'C500',
        }
        
        # Create a new dataset for conductivity flags
        cz_data_vars = {}
        for var in sz_ds.data_vars:
            if var.startswith('salinity_flags_'):
                # Get metadata from salinity variable
                serial = sz_ds[var].attrs.get('serial_number', '')
                sal_depth_label = sz_ds[var].attrs.get('depth_label', '')
                depth_meters = sz_ds[var].attrs.get('depth_meters', 0.0)
                
                # Convert to conductivity depth label
                cond_depth = conductivity_mapping.get(sal_depth_label, sal_depth_label)
                
                # Create conductivity flag variable name
                cond_var_name = f"conductivity_flags_{serial}_{cond_depth}"
                
                # Copy the data with new attributes
                cz_data_vars[cond_var_name] = (
                    ['time'],
                    sz_ds[var].values,
                    {
                        'long_name': f"Quality flags for conductivity at {cond_depth}",
                        'serial_number': serial,
                        'depth_label': cond_depth,
                        'depth_meters': depth_meters,
                        'flag_meanings': '-2: bad data (manually flagged), -1: missing, 0: unprocessed, 1: good data (auto QC), 2: good data (manual QC)',
                        'comment': 'Flag value 2 indicates good data, -2 indicates manually flagged bad data'
                    }
                )
        
        # Create conductivity dataset
        cz_ds = xr.Dataset(
            data_vars=cz_data_vars,
            coords={'time': sz_ds.time.values}
        )
        
        # Copy global attributes from salinity dataset
        cz_ds.attrs = sz_ds.attrs.copy()
        cz_ds.attrs['data_type'] = 'conductivity_quality_flags'
        cz_ds.attrs['comment'] = 'Conductivity quality flags (identical to salinity flags, same sensors)'
        
        # Add time attributes
        cz_ds.time.attrs['standard_name'] = 'time'
        cz_ds.time.attrs['long_name'] = 'time'
        
        cz_ds.to_netcdf(cz_nc_filename, format='NETCDF4', engine='netcdf4')
        print(f"✓ Saved conductivity flags to {cz_nc_filename}")

        # Save density flags to netCDF
        dz_ds = flags_to_dataset(
            updated_dz_qual_dm,
            variable_prefix='density',
            deployment_id=dep_id,
            lat=dep.latitude,
            lon=dep.longitude
        )
        dz_ds.attrs['data_type'] = 'density_quality_flags'
        dz_ds.to_netcdf(dz_nc_filename, format='NETCDF4', engine='netcdf4')
        print(f"✓ Saved density flags to {dz_nc_filename}")

    except Exception as e:
        print(f"Error saving netCDF files: {e}")
        info_div.text = f"Error saving netCDF files: {e}"
        return

    # Count the number of -2 flags in the updated data
    sz_flag_count = 0
    dz_flag_count = 0

    # Count salinity flags
    for config, _ in sensor_configs:
        sz_flag_count += (updated_sz_qual_dm[config] == -2).sum()

    # Count density flags
    for s_config, _ in sensor_configs:
        salinity_depth = s_config[2]
        density_depth = depth_mapping.get(salinity_depth)
        if density_depth:
            matching_dz_cols = [col for col in updated_dz_qual_dm.columns if col[2] == density_depth]
            if matching_dz_cols:
                dz_config = matching_dz_cols[0]
                dz_flag_count += (updated_dz_qual_dm[dz_config] == -2).sum()

    # Print confirmation
    print("\n" + "="*80)
    print("QUALITY FLAGS SAVED")
    print("="*80)
    print(f"Salinity flags:     {sz_nc_filename}")
    print(f"Conductivity flags: {cz_nc_filename}")
    print(f"Density flags:      {dz_nc_filename}")
    print(f"Number of -2 flags in salinity data: {sz_flag_count}")
    print(f"Number of -2 flags in density data: {dz_flag_count}")
    print(f"Number of -2 flags in conductivity data: {sz_flag_count} (same as salinity)")
    print("="*80 + "\n")

    info_div.text = (
        f"Quality flags saved to netCDF files: "
        f"{sz_flag_count} salinity/conductivity flags and {dz_flag_count} density flags"
    )


def exit_server():
    """Exit the Bokeh server."""
    print("Exiting the program...")
    from tornado.ioloop import IOLoop

    def shutdown():
        IOLoop.current().stop()
        sys.exit(0)

    IOLoop.current().add_callback(shutdown)


def apply_slice(label):
    """Create callback to apply slice/date range flagging."""
    def callback():
        slice_expr = slice_inputs[label].value
        if not slice_expr:
            info_div.text = "Please enter a slice expression or date range"
            return

        try:
            # Get the current data
            times = sources[label].data["time"].copy()
            flags = sources[label].data["flags"].copy()
            colors = sources[label].data["colors"].copy()

            print(f"Input expression: {slice_expr}")

            # Handle open-ended date range
            if "+" in slice_expr and slice_expr.endswith(":"):
                try:
                    start_str = slice_expr[:-1]
                    print(f"Parsing open-ended range starting at: {start_str}")

                    start_date = pd.to_datetime(start_str).tz_localize(None)
                    print(f"Parsed start date (tz-naive): {start_date}")

                    pd_times = pd.to_datetime(times)
                    mask = (pd_times >= start_date)
                    flagged_count = mask.sum()
                    print(f"Points to flag: {flagged_count} out of {len(times)}")

                    if flagged_count == 0:
                        info_div.text = f"Warning: No points matched the date range {start_date} onwards for {label}"
                        return

                    flags[mask] = -2
                    colors[mask] = 'red'

                    info_div.text = f"Flagged {flagged_count} points from {start_date} onwards for {label}"

                except Exception as e:
                    raise ValueError(f"Error parsing open-ended date range: {e}")

            # Handle date range
            elif ":" in slice_expr and "+" in slice_expr and slice_expr.count(":") >= 2:
                try:
                    print(f"Trying to parse date range: {slice_expr}")

                    plus_pos = slice_expr.find("+")
                    if plus_pos > 0:
                        sep_colon_pos = slice_expr.find(":", plus_pos + 5)

                        if sep_colon_pos > 0:
                            start_str = slice_expr[:sep_colon_pos]
                            end_str = slice_expr[sep_colon_pos+1:]

                            print(f"Split into: start='{start_str}', end='{end_str}'")

                            start_date = pd.to_datetime(start_str).tz_localize(None)
                            end_date = pd.to_datetime(end_str).tz_localize(None)

                            print(f"Parsed dates (tz-naive): start={start_date}, end={end_date}")

                            pd_times = pd.to_datetime(times)
                            mask = (pd_times >= start_date) & (pd_times <= end_date)
                            flagged_count = mask.sum()
                            print(f"Points to flag: {flagged_count} out of {len(times)}")

                            if flagged_count == 0:
                                info_div.text = f"Warning: No points matched the date range from {start_date} to {end_date} for {label}"
                                return

                            flags[mask] = -2
                            colors[mask] = 'red'

                            info_div.text = f"Flagged {flagged_count} points from {start_date} to {end_date} for {label}"
                        else:
                            raise ValueError("Could not find separator colon in date range")
                    else:
                        raise ValueError("Could not find '+' in date format")

                except Exception as e:
                    raise ValueError(f"Error parsing date format: {e}")

            elif ":" in slice_expr:
                # Handle numeric slice notation
                print(f"Handling numeric slice: {slice_expr}")
                try:
                    parts = slice_expr.split(":")
                    print(f"Slice parts: {parts}")

                    if len(parts) == 2:
                        start = int(parts[0]) if parts[0].strip() else 0
                        end = int(parts[1]) if parts[1].strip() else len(flags)

                        print(f"Interpreted as slice({start}, {end})")

                        indices = list(range(start, end))

                        if not indices:
                            info_div.text = f"Warning: Slice {slice_expr} resulted in no points to flag"
                            return

                        for idx in indices:
                            flags[idx] = -2
                            colors[idx] = 'red'

                        flagged_count = len(indices)

                    elif len(parts) == 3:
                        start = int(parts[0]) if parts[0].strip() else 0
                        end = int(parts[1]) if parts[1].strip() else len(flags)
                        step = int(parts[2]) if parts[2].strip() else 1

                        print(f"Interpreted as slice({start}, {end}, {step})")

                        indices = list(range(start, end, step))

                        if not indices:
                            info_div.text = f"Warning: Slice {slice_expr} resulted in no points to flag"
                            return

                        for idx in indices:
                            flags[idx] = -2
                            colors[idx] = 'red'

                        flagged_count = len(indices)
                    else:
                        raise ValueError(f"Invalid slice format: {slice_expr}")

                    info_div.text = f"Applied slice {slice_expr} to {label}, flagged {flagged_count} points"

                except ValueError as e:
                    raise ValueError(f"Error with numeric slice: {e}")
                except IndexError as e:
                    raise ValueError(f"Index error with slice {slice_expr}: {e}")

            else:
                # Single index
                try:
                    idx = int(slice_expr)
                    print(f"Flagging single index: {idx}")

                    if idx < 0 or idx >= len(flags):
                        raise ValueError(f"Index {idx} out of range (0-{len(flags)-1})")

                    flags[idx] = -2
                    colors[idx] = 'red'
                    info_div.text = f"Flagged point at index {idx} for {label}"
                except ValueError as e:
                    if "out of range" in str(e):
                        raise e
                    else:
                        raise ValueError(f"Invalid input format: {slice_expr}")

            # Update the source data
            sources[label].data.update({
                'flags': flags,
                'colors': colors
            })

            update_stats()

        except Exception as e:
            info_div.text = f"Error applying slice/date range: {str(e)}"
            print(f"Error details: {e}")
            import traceback
            traceback.print_exc()

    return callback


def clear_slice(label):
    """Create callback to clear all flags for a sensor."""
    def callback():
        # Clear the slice input field
        slice_inputs[label].value = ""

        # Reset all points to flag=2 (good) and color=blue
        flags = sources[label].data["flags"].copy()
        colors = sources[label].data["colors"].copy()

        flags[:] = 2
        colors[:] = "blue"

        sources[label].data.update({
            "flags": flags,
            "colors": colors
        })

        update_stats()
        info_div.text = f"Reset all points for {label}"
    
    return callback


# ============================================================================
# CREATE UI LAYOUT
# ============================================================================

# Create top buttons
unflag_button_top = Button(label="Unflag Selected Points", button_type="success")
save_button_top = Button(label="Save Flags", button_type="primary")
exit_button_top = Button(label="Exit", button_type="warning")

# Create bottom buttons
unflag_button_bottom = Button(label="Unflag Selected Points", button_type="success")
save_button_bottom = Button(label="Save Flags", button_type="primary")
exit_button_bottom = Button(label="Exit", button_type="warning")

# Set up callbacks for all buttons
unflag_button_top.on_click(unflag_points)
save_button_top.on_click(save_flags)
exit_button_top.on_click(exit_server)
unflag_button_bottom.on_click(unflag_points)
save_button_bottom.on_click(save_flags)
exit_button_bottom.on_click(exit_server)

# Create info div
info_div = Div(text="No points selected")

# Create title div
title_div = Div(
    text=f"<h1 style='text-align: center;'>Deployment: {dep_id}</h1>",
    width=1000,
    height=50,
)

# Initial statistics update
update_stats()

# Create vertical layout for plots
plot_list = [
    plots[label]
    for label, _ in sorted(
        sources.items(), key=lambda x: list(plots.keys()).index(x[0])
    )
]

# Create slice input controls
slice_inputs = {}
apply_slice_buttons = {}
clear_slice_buttons = {}

# Create help div
help_div = Div(
    text="""<div style="font-size: 12px; margin-bottom: 10px;">
    <b>Formats:</b>
    <ul style="margin: 0; padding-left: 20px;">
      <li>Index slice: <code>1000:2000</code></li>
      <li>Date range: <code>2016-03-14 00:50:00+00:00:2016-03-15 01:40:00+00:00</code></li>
      <li>Open range: <code>2016-03-14 00:50:00+00:00:</code></li>
    </ul>
    </div>""",
    width=800
)

# Create text input and buttons for each subplot
for config, label in sensor_configs:
    slice_inputs[label] = TextInput(
        value="",
        placeholder="Enter slice or date range",
        title=f"Flag range for {label}",
        width=300,
        height=30
    )

    apply_slice_buttons[label] = Button(
        label="Apply",
        button_type="primary",
        width=80
    )

    clear_slice_buttons[label] = Button(
        label="Clear",
        button_type="default",
        width=80
    )

    apply_slice_buttons[label].on_click(apply_slice(label))
    clear_slice_buttons[label].on_click(clear_slice(label))

# Create plots with controls
plot_with_controls = []

for i, plot in enumerate(plot_list):
    label = list(sources.keys())[i]
    slice_control_row = bokeh_row(
        [slice_inputs[label], apply_slice_buttons[label], clear_slice_buttons[label]],
        width=470
    )
    plot_with_controls.append(
        bokeh_row([plot, bokeh_column([slice_control_row])])
    )

# Create top and bottom controls
top_controls = bokeh_row([unflag_button_top, save_button_top, exit_button_top])
bottom_controls = bokeh_row([unflag_button_bottom, save_button_bottom, exit_button_bottom])

# Layout
l = layout(
    [
        [title_div],
        [top_controls],
        [help_div],
        *[[row] for row in plot_with_controls],
        [bottom_controls],
        [info_div],
        [stats_div],
    ]
)

# Add the layout to the document
curdoc().add_root(l)
curdoc().title = f"Salinity Flagging Tool - {dep_id}"

# Disable reconnection notifications
curdoc().config.reconnect_session = False
curdoc().config.notify_connection_status = False


# ============================================================================
# MAIN EXECUTION (Bokeh Server)
# ============================================================================

if __name__ == "__main__":
    print("Starting Bokeh server...")
    import subprocess
    import webbrowser
    from threading import Timer
    import signal

    def signal_handler(sig, frame):
        print("Shutting down server...")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Get the file path of the current script
    script_path = os.path.abspath(__file__)

    # Save the current file
    script_dir = os.path.dirname(script_path)
    app_name = "flag_sal_netcdf.py"
    app_path = os.path.join(script_dir, app_name)

    with open(script_path, 'r') as source_file:
        script_content = source_file.read()

    with open(app_path, 'w') as target_file:
        target_file.write(script_content)

    def open_browser():
        webbrowser.open("http://localhost:5006/flag_sal_netcdf")

    # Open browser after delay
    Timer(2, open_browser).start()

    # Start Bokeh server
    try:
        subprocess.run([
            "bokeh",
            "serve",
            "--show",
            app_path,
            f"--args",
            dep_id
        ])
    except KeyboardInterrupt:
        print("\nServer stopped by user")
        sys.exit(0)
