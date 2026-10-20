#!/usr/bin/env python3
"""
NetCDF plotting tool with quality flag support

This script reads netCDF files created by cond_drift_netcdf.py and creates
interactive plots with optional quality control flag masking.

Usage:
    python ncplot_flg.py pt005_sal_drift.nc
    python ncplot_flg.py pt005_sal_drift.nc -d SSS S010 S120
    python ncplot_flg.py pt005_sal_drift.nc --no-qc
"""

import xarray as xr
import pandas as pd
from bokeh.plotting import figure, show, output_file
# No longer need Category20
from bokeh.layouts import column
from bokeh.models import DatetimeTickFormatter, HoverTool, DataRange1d
import argparse
import sys
import numpy as np
import os

def extract_dep_id(filename):
    """Extract deployment ID from filename (e.g., 'pt005' from 'pt005_sal_drift.nc')"""
    basename = os.path.basename(filename)
    # Extract deployment ID before the first underscore or before 'sal'/'dens'/'cond'
    return basename.split('_')[0].split('sal')[0].split('dens')[0].split('cond')[0]

def get_y_label(filename):
    """Determine y-axis label based on filename"""
    filename = filename.lower()
    if 'sal' in filename:
        return 'Salinity (PSU)'
    elif 'cond' in filename:
        return 'Conductivity (mS/cm)'
    elif 'dens' in filename:
        return 'Density (kg/m³)'
    return 'Value'

def should_invert_y_axis(filename):
    """Check if y-axis should be inverted (for density plots)"""
    return 'dens' in filename.lower()

def load_netcdf_data(filename):
    """Load netCDF file and convert to pandas DataFrame with multi-index columns"""
    try:
        ds = xr.open_dataset(filename)
        print(f"Loaded netCDF file: {filename}")
        print(f"  Variables: {len(ds.data_vars)}")
        print(f"  Time points: {len(ds.time)}")
        
        # Convert to DataFrame
        df = ds.to_dataframe()
        
        # Reconstruct multi-index columns from variable names
        # Variable names are in format: {type}_{serial_number}_{depth_label}
        reconstructed_data = pd.DataFrame(index=ds.time.to_index())
        
        for var_name in sorted(ds.data_vars):
            # Get attributes
            serial_number = ds[var_name].attrs.get('serial_number', 'unknown')
            depth_label = ds[var_name].attrs.get('depth_label', 'unknown')
            
            # Create multi-index column tuple (1, serial_number, depth_label)
            # The '1' matches the original pickle format structure
            col_tuple = (1, serial_number, depth_label)
            
            # Add to DataFrame
            reconstructed_data[col_tuple] = ds[var_name].values
        
        # Sort columns by depth label to ensure SSS/SSD appear first
        def depth_sort_key(col):
            depth = col[2]
            if depth.startswith('SS'):  # SSS, SSC, SSD
                return (0, depth)
            else:
                # Extract numeric part for ordering (S005 -> 5, D010 -> 10, etc.)
                import re
                match = re.search(r'\d+', depth)
                if match:
                    return (1, int(match.group()))
                return (2, depth)
        
        reconstructed_data = reconstructed_data[sorted(reconstructed_data.columns, key=depth_sort_key)]
        
        ds.close()
        
        return reconstructed_data
        
    except Exception as e:
        print(f"Error loading netCDF file: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def load_quality_flags(dep_id, data_type):
    """Load quality flags based on deployment ID and data type"""
    # First, try to load from CSV file in the current directory
    if 'sal' in data_type.lower():
        csv_filename = f"qual_dm_sz_{dep_id}.csv"
    elif 'dens' in data_type.lower():
        csv_filename = f"qual_dm_dz_{dep_id}.csv"
    else:
        csv_filename = None
    
    if csv_filename and os.path.exists(csv_filename):
        try:
            print(f"Loading quality flags from CSV file: {csv_filename}")
            # Read the CSV with multi-index columns
            df_qual = pd.read_csv(csv_filename, header=[0, 1, 2], index_col=0, parse_dates=True)
            print(f"Loaded {len(df_qual)} rows and {len(df_qual.columns)} columns of quality flags")
            return df_qual
        except Exception as e:
            print(f"Warning: Error loading CSV quality flags: {e}. Trying Deployment object.")
    
    # If CSV not found or failed, try loading from Deployment object
    try:
        from tao.flex.data import Deployment

        home = os.path.expanduser('~')
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
            print(f"Warning: Base directory not found: {base_path}. Skipping quality flags.")
            return None

        if not (os.path.exists(data_file) and os.path.exists(config_file)):
            print(f"Warning: Required files not found. Skipping quality flags.")
            print(f"Data file: {data_file}")
            print(f"Config file: {config_file}")
            return None

        dep = Deployment(
            data_file,
            metaSrc=config_file,
        )

        if 'sal' in data_type.lower():
            qual = dep.SZ.qual_dm
        elif 'dens' in data_type.lower():
            qual = dep.DZ.qual_dm
        else:
            return None

        # Process quality flags
        df_qual = qual.copy()
        return df_qual

    except ImportError:
        print("Warning: tao.flex.data module not available. Skipping quality flags.")
        return None
    except Exception as e:
        print(f"Warning: Error loading quality flags: {e}. Skipping quality flags.")
        return None

def mask_negative_quality_flags(data, quality_flags):
    """Mask data where quality flags are negative"""
    if quality_flags is None:
        return data

    masked_data = data.copy()

    try:
        # Drop instance level from quality flags
        quality_flags.columns = quality_flags.columns.droplevel('instance')

        # Track total flags applied
        total_flags_applied = 0
        
        # For each column in the data
        for col in masked_data.columns:
            serial = col[1]  # Get the serial number
            depth_label = col[2]  # Get the depth label (e.g., 'SSS', 'S010', 'SSD', 'D010')
            
            # Convert serial to string for matching (CSV has strings)
            serial_str = str(serial)
            
            # Find corresponding quality flag column - match BOTH serial AND depth
            matching_cols = [qf_col for qf_col in quality_flags.columns
                            if qf_col[0] == serial_str and qf_col[1] == depth_label]

            if matching_cols:
                qf_col = matching_cols[0]
                # Create boolean mask for negative quality flags
                mask = quality_flags[qf_col] < 0
                num_flagged = mask.sum()
                if num_flagged > 0:
                    print(f"  Masking {num_flagged} flagged points in {depth_label}")
                    total_flags_applied += num_flagged
                # Apply mask using numpy where
                masked_data[col] = np.where(mask, np.nan, masked_data[col])
            else:
                print(f"Warning: No quality flags found for {col} (serial: {serial_str}, depth: {depth_label})")
        
        if total_flags_applied > 0:
            print(f"Total: {total_flags_applied} flagged points masked")

        return masked_data
    except Exception as e:
        print(f"Warning: Error applying quality flags: {e}. Using unmasked data.")
        import traceback
        traceback.print_exc()
        return data

def create_plot(data, title, y_label, shared_x_range=None, invert_y=False):
    """Create an interactive Bokeh plot"""
    # Create figure with shared x_range if provided
    fig_kwargs = {
        'title': title,
        'x_axis_label': 'Date',
        'y_axis_label': y_label,
        'width': 1200,
        'height': 400,
        'x_axis_type': "datetime",
        'background_fill_color': "#f5f5f5",  # Very light gray, almost white
        'tools': 'pan,box_zoom,wheel_zoom,reset,save'
    }
    
    if shared_x_range is not None:
        fig_kwargs['x_range'] = shared_x_range
    
    p = figure(**fig_kwargs)

    if invert_y:
        p.y_range.flipped = True

    p.xaxis.formatter = DatetimeTickFormatter(
        hours="%Y-%m-%d %H:%M",
        days="%Y-%m-%d",
        months="%Y-%m-%d",
        years="%Y-%m-%d"
    )

    # Define high-contrast, easily distinguishable colors
    # Avoiding light/pastel colors that are hard to see
    # Dark blue first for surface data (SSS, SSD, SSC)
    distinct_colors = [
        '#00008b',  # Dark blue (for surface data)
        '#e41a1c',  # Red
        '#4daf4a',  # Green
        '#984ea3',  # Purple
        '#ff7f00',  # Orange
        '#a65628',  # Brown
        '#f781bf',  # Pink
        '#999999',  # Gray
        '#e31a1c',  # Bright red
        '#1f78b4',  # Blue
        '#33a02c',  # Dark green
        '#6a3d9a',  # Dark purple
        '#ff8c00',  # Dark orange
        '#8b4513',  # Saddle brown
        '#dc143c',  # Crimson
        '#377eb8',  # Light blue
        '#006400',  # Dark green
        '#8b008b',  # Dark magenta
        '#ff4500',  # Orange red
        '#2f4f4f',  # Dark slate gray
    ]
    
    num_colors = len(data.columns)
    colors = distinct_colors[:num_colors]

    # Plot each column
    for col, color in zip(data.columns, colors):
        # Get the data for this column
        y_data = data[col]

        # Create legend label
        if isinstance(col, tuple):
            legend_label = ' '.join(str(x) for x in col)
        else:
            legend_label = str(col)

        # Convert data to numpy arrays
        x_data = data.index.values
        y_values = y_data.values

        # Ensure y_values are float type
        try:
            y_values = y_values.astype(float)
        except ValueError:
            continue  # Skip this column if conversion fails

        # Find consecutive non-NaN segments
        mask = pd.notna(y_values)  # Use pandas na checking instead of numpy
        # Get indices where mask changes (transitions between valid and invalid data)
        mask_changes = np.diff(mask.astype(int))
        segment_starts = np.where(mask_changes == 1)[0] + 1
        segment_ends = np.where(mask_changes == -1)[0] + 1

        # Handle case where data starts with valid values
        if mask[0]:
            segment_starts = np.insert(segment_starts, 0, 0)
        # Handle case where data ends with valid values
        if mask[-1]:
            segment_ends = np.append(segment_ends, len(mask))

        # Plot each segment separately
        for start, end in zip(segment_starts, segment_ends):
            if end > start:  # Only plot if segment has points
                p.line(x_data[start:end],
                      y_values[start:end],
                      line_color=color,
                      legend_label=legend_label,
                      line_width=2)

    # Configure legend
    p.legend.click_policy="hide"
    p.legend.location = "top_right"

    # Add hover tool
    hover = HoverTool(
        tooltips=[
            ('date', '@x{%F %H:%M}'),
            ('value', '@y{0.0000}')
        ],
        formatters={
            '@x': 'datetime'
        }
    )
    p.add_tools(hover)
    
    # Set active tools (disable hover by default)
    p.toolbar.active_drag = 'auto'
    p.toolbar.active_scroll = 'auto'
    p.toolbar.active_inspect = []

    return p

def filter_data_by_depths(data, depths):
    """Filter data to include only specified column names (e.g., SSS, S010, S120)"""
    if depths is None:
        return data

    # Get all columns that match the specified column names
    filtered_cols = []
    for col in data.columns:
        # Extract the column identifier (third element if tuple with 3+ elements, otherwise the whole column name)
        if isinstance(col, tuple) and len(col) >= 3:
            col_name = str(col[2])
        elif isinstance(col, tuple):
            col_name = str(col[0])
        else:
            col_name = str(col)

        # Check if this column name matches any of the specified depths
        if col_name in depths:
            filtered_cols.append(col)

    if not filtered_cols:
        # Get list of available column names
        available = sorted(set([str(col[2]) if isinstance(col, tuple) and len(col) >= 3 else (str(col[0]) if isinstance(col, tuple) else str(col)) for col in data.columns]))
        print(f"Error: No columns found matching: {depths}")
        print(f"Available column names: {available}")
        sys.exit(1)

    print(f"Plotting {len(filtered_cols)} column(s) matching: {depths}")
    return data[filtered_cols]

def main():
    parser = argparse.ArgumentParser(
        description='Plot data from a netCDF file with optional quality control',
        epilog="""
Examples:
  python ncplot_flg.py pt005_sal_drift.nc
  python ncplot_flg.py pt005_sal_drift.nc -d SSS S010 S120
  python ncplot_flg.py pt005_sal_drift.nc --no-qc
        """
    )
    parser.add_argument('filename',
                       help='Path to the netCDF file to be plotted')
    parser.add_argument('-d', '--depths', nargs='+',
                       help='Specific column names to plot (e.g., -d SSS S010 S120). Default is all columns.')
    parser.add_argument('--no-qc', action='store_true',
                       help='Disable quality control flag processing')

    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.filename):
        print(f"Error: File '{args.filename}' not found")
        sys.exit(1)
    
    y_label = get_y_label(args.filename)

    try:
        # Load netCDF data
        data = load_netcdf_data(args.filename)
        
        print(f"\nLoaded {len(data.columns)} variables:")
        for col in data.columns:
            non_nan = data[col].notna().sum()
            print(f"  {col[2]:6} (serial {col[1]}) -> {non_nan} non-NaN values")

        # Apply quality flags if enabled
        if not args.no_qc:
            dep_id = extract_dep_id(os.path.basename(args.filename))
            quality_flags = load_quality_flags(dep_id, os.path.basename(args.filename))
            if quality_flags is not None:
                data = mask_negative_quality_flags(data, quality_flags)
            else:
                print("Proceeding with unmasked data")

        # Filter by specified depths
        if args.depths:
            data = filter_data_by_depths(data, args.depths)

        # Create daily averaged data
        print("\nCreating daily averages...")
        daily_data = data.resample('D').mean()

        # Create first plot without shared range
        print("Creating original data plot...")
        p1 = create_plot(data,
                        f"{os.path.basename(args.filename)} - Original Data",
                        y_label,
                        shared_x_range=None,
                        invert_y=should_invert_y_axis(args.filename))

        # Create second plot with shared x_range from first plot
        print("Creating daily averaged plot...")
        p2 = create_plot(daily_data,
                        f"{os.path.basename(args.filename)} - Daily Averaged",
                        y_label,
                        shared_x_range=p1.x_range,
                        invert_y=should_invert_y_axis(args.filename))

        # Set output file in current working directory
        output_filename = os.path.splitext(os.path.basename(args.filename))[0] + "_plot.html"
        output_path = os.path.join(os.getcwd(), output_filename)
        output_file(output_path)

        print(f"\nGenerating plot: {output_path}")
        # Show both plots in a column layout
        show(column(p1, p2))
        
        print(f"✓ Plot saved successfully!")

    except FileNotFoundError:
        print(f"Error: File '{args.filename}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
