"""
Apply Salinity Adjustments and Export to netCDF

This script reads adjustment inputs, applies them to salinity data from GTMBA moorings,
computes adjusted conductivity and density, and exports all results to netCDF files.

Usage:
    python adj_data_netcdf.py <deployment_id>
    python adj_data_netcdf.py <deployment_id> --rcl <adjusted_file.nc>

Example:
    python adj_data_netcdf.py pt005
    python adj_data_netcdf.py pt005 --rcl pt005_sal_drift.nc
"""

import pandas as pd
import numpy as np
import xarray as xr
from bokeh.plotting import figure, show, output_file
from bokeh.layouts import column
from bokeh.palettes import Spectral6
from bokeh.models import ColumnDataSource, DatetimeTickFormatter, HoverTool
from tao.flex.data import Deployment
import os
from pathlib import Path
import argparse
import sys
import gsw
from datetime import datetime


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def mask_invalid_data(data, mask):
    """
    Replace data values with NaN where mask is False.
    
    Parameters:
    -----------
    data : pd.Series or pd.DataFrame
        Data to mask
    mask : pd.Series or array-like
        Boolean mask
        
    Returns:
    --------
    pd.Series or pd.DataFrame
        Masked data
    """
    masked_data = data.copy()
    masked_data[~mask] = np.nan
    return masked_data


def compute_adjustments(saldf, deployment):
    """
    Compute adjusted conductivity and density based on adjusted salinity.
    
    Parameters:
    -----------
    saldf : pd.DataFrame
        Adjusted salinity dataframe
    deployment : Deployment
        GTMBA deployment object
        
    Returns:
    --------
    tuple
        (cond_adjusted, dens_adjusted) DataFrames
    """
    # Get temperature data
    tz = deployment.TZ.data
    dftz = tz.copy()
    dftz.columns = dftz.columns.droplevel(level=0)
    dftz.columns = dftz.columns.droplevel(level=0)

    # Ensure temperature data has the same timezone handling as salinity data
    dftz.index = dftz.index.tz_localize(None)

    # Dynamically create a mapping between salinity and temperature columns
    def get_temp_col_name(sal_col_name):
        """Convert salinity column name to corresponding temperature column name"""
        if sal_col_name == 'SSS':
            return 'SST'
        elif sal_col_name.startswith('S'):
            # Replace 'S' prefix with 'T' prefix (e.g., S005 -> T005, S100 -> T100)
            return 'T' + sal_col_name[1:]
        else:
            return None

    # Create temperature DataFrame with matching columns and index
    t1 = pd.DataFrame(index=saldf.index, columns=saldf.columns)
    for sal_col in saldf.columns:
        if isinstance(sal_col, tuple):
            col_name = sal_col[-1]
        else:
            col_name = sal_col

        temp_col = get_temp_col_name(col_name)
        if temp_col is not None:
            if temp_col in dftz.columns:
                # Reindex temperature data to match salinity data
                t1[sal_col] = dftz[temp_col].reindex(index=saldf.index, method='nearest')
                print(f"Successfully mapped {col_name} to {temp_col}")
            else:
                print(f"Warning: Temperature column {temp_col} not found for salinity {col_name}")
                t1[sal_col] = np.nan
        else:
            print(f"Warning: Could not determine temperature column for {col_name}")
            t1[sal_col] = np.nan

    # Convert temperature data to float64
    t1 = t1.astype('float64')

    # Create pressure DataFrame
    p1 = pd.DataFrame(index=saldf.index, columns=saldf.columns)
    for i in saldf.columns:
        try:
            if isinstance(i, tuple):
                col_name = i[-1]
            else:
                col_name = i

            if col_name.startswith('S'):
                if col_name == 'SSS':
                    p1[i] = 0.0
                else:
                    depth_str = col_name.replace('S', '')
                    if depth_str:
                        depth = int(depth_str)
                        p1[i] = float(depth)
                    else:
                        p1[i] = 0.0
            else:
                p1[i] = 0.0
        except ValueError as e:
            print(f"Warning: Could not parse depth from column {i}, using surface pressure")
            p1[i] = 0.0

    # Convert pressure data to float64
    p1 = p1.astype('float64')

    # Create lat/lon DataFrames
    lat = pd.DataFrame(deployment.latitude, index=saldf.index, columns=saldf.columns).astype('float64')
    lon = pd.DataFrame(deployment.longitude, index=saldf.index, columns=saldf.columns).astype('float64')

    # Create SA DataFrame
    SA_df = pd.DataFrame(index=saldf.index, columns=saldf.columns)

    # Print diagnostic information
    print("Index information:")
    print(f"Salinity index range: {saldf.index.min()} to {saldf.index.max()}")
    print(f"Number of salinity records: {len(saldf)}")

    # Ensure saldf is float64
    saldf = saldf.astype('float64')

    # Compute SA for each column
    for col in saldf.columns:
        try:
            SP = saldf[col].values
            p = p1[col].values
            lon_array = lon[col].values
            lat_array = lat[col].values

            # Convert arrays to float64
            SP = SP.astype('float64')
            p = p.astype('float64')
            lon_array = lon_array.astype('float64')
            lat_array = lat_array.astype('float64')

            # Remove any NaN values
            valid_mask = ~(np.isnan(SP) | np.isnan(p) | np.isnan(lon_array) | np.isnan(lat_array))
            if not np.any(valid_mask):
                print(f"Warning: No valid data for SA computation in column {col}")
                continue

            SA = gsw.SA_from_SP(SP[valid_mask], p[valid_mask], lon_array[valid_mask], lat_array[valid_mask])
            SA_df.loc[saldf.index[valid_mask], col] = SA
            print(f"Successfully computed SA for column {col}")
        except Exception as e:
            print(f"Error computing SA for column {col}: {str(e)}")

    # Compute adjusted conductivity and density
    cond_adjusted = pd.DataFrame(index=saldf.index, columns=saldf.columns)
    CT = pd.DataFrame(index=saldf.index, columns=saldf.columns)
    dens_adjusted = pd.DataFrame(index=saldf.index, columns=saldf.columns)

    for col in saldf.columns:
        try:
            SA_col = SA_df[col].values.astype('float64')
            t_col = t1[col].values.astype('float64')
            p_col = p1[col].values.astype('float64')

            valid_mask = ~(np.isnan(SA_col) | np.isnan(t_col) | np.isnan(p_col))
            if not np.any(valid_mask):
                print(f"Warning: No valid data for column {col}")
                continue

            valid_index = saldf.index[valid_mask]
            SA_col = SA_col[valid_mask]
            t_col = t_col[valid_mask]
            p_col = p_col[valid_mask]

            cond_adjusted.loc[valid_index, col] = gsw.C_from_SP(SA_col, t_col, p_col)
            CT_col = gsw.CT_from_t(SA_col, t_col, p_col)
            CT.loc[valid_index, col] = CT_col
            dens_adjusted.loc[valid_index, col] = gsw.density.sigma0(SA_col, CT_col)

            print(f"Successfully computed adjustments for column {col}")

        except Exception as e:
            print(f"Error computing values for column {col}: {str(e)}")

    return cond_adjusted, dens_adjusted


def extract_depth_from_label(label):
    """
    Extract numeric depth from a depth label.
    
    Parameters:
    -----------
    label : str
        Depth label (e.g., 'S010', 'S020', 'SSS')
    
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


def dataframe_to_dataset(df, variable_name, units, long_name, deployment_id, lat, lon, processing_note=None):
    """
    Convert a pandas DataFrame to an xarray Dataset.
    
    Parameters:
    -----------
    df : pd.DataFrame
        DataFrame with data
    variable_name : str
        Name for the data variable (e.g., 'salinity', 'conductivity', 'density')
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
    processing_note : str, optional
        Additional processing information
    
    Returns:
    --------
    xr.Dataset
    """
    data_vars = {}
    
    # Mapping from salinity to density/conductivity depth labels
    depth_mapping = {
        'SSS': {'density': 'SSD', 'conductivity': 'SSC'},
        'S001': {'density': 'D001', 'conductivity': 'C001'},
        'S005': {'density': 'D005', 'conductivity': 'C005'},
        'S010': {'density': 'D010', 'conductivity': 'C010'},
        'S015': {'density': 'D015', 'conductivity': 'C015'},
        'S020': {'density': 'D020', 'conductivity': 'C020'},
        'S025': {'density': 'D025', 'conductivity': 'C025'},
        'S040': {'density': 'D040', 'conductivity': 'C040'},
        'S060': {'density': 'D060', 'conductivity': 'C060'},
        'S080': {'density': 'D080', 'conductivity': 'C080'},
        'S100': {'density': 'D100', 'conductivity': 'C100'},
        'S120': {'density': 'D120', 'conductivity': 'C120'},
        'S140': {'density': 'D140', 'conductivity': 'C140'},
        'S180': {'density': 'D180', 'conductivity': 'C180'},
        'S250': {'density': 'D250', 'conductivity': 'C250'},
        'S300': {'density': 'D300', 'conductivity': 'C300'},
        'S500': {'density': 'D500', 'conductivity': 'C500'},
    }
    
    for col in df.columns:
        # Extract serial number and column name from tuple
        if isinstance(col, tuple):
            # Tuple format: (instance, serial, depth_label)
            serial_number = str(col[1])
            col_name = col[-1]
        else:
            serial_number = 'unknown'
            col_name = col
        
        # Convert depth label for density/conductivity if needed
        output_depth_label = col_name
        if variable_name == 'density' and col_name in depth_mapping:
            output_depth_label = depth_mapping[col_name]['density']
        elif variable_name == 'conductivity' and col_name in depth_mapping:
            output_depth_label = depth_mapping[col_name]['conductivity']
        
        depth = extract_depth_from_label(col_name)  # Use original for depth extraction
        var_name = f"{variable_name}_{output_depth_label}"
        
        data_vars[var_name] = (
            ['time'],
            df[col].values,
            {
                'units': units,
                'long_name': f"{long_name} at {output_depth_label}",
                'serial_number': serial_number,
                'depth_label': output_depth_label,
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
    
    if processing_note:
        ds.attrs['processing'] = processing_note
    
    # Add time attributes
    ds.time.attrs['standard_name'] = 'time'
    ds.time.attrs['long_name'] = 'time'
    
    return ds


def process_data(dep_id, input_file=None, rcl_file=None):
    """
    Process adjustment data and create netCDF output files.
    
    Parameters:
    -----------
    dep_id : str
        Deployment ID
    input_file : str, optional
        Path to adjustment input file
    rcl_file : str, optional
        Path to netCDF file with adjusted salinity data
        
    Returns:
    --------
    tuple
        (saldf_adjusted, cond_adjusted, dens_adjusted) DataFrames
    """
    home = os.path.expanduser('~')

    # Define the base path for deployment data
    base_path = (
        home
        + "/data/flexram/"
        + dep_id
        + "-proc"
        + "/data/subsurface/"
    )

    # Load the deployment data
    data_file_path = base_path + dep_id + "-sbe-data.bz2"
    config_file_path = base_path + "config.xml"

    print(f"Loading data from: {data_file_path}")
    print(f"Loading config from: {config_file_path}")

    deployment = Deployment(
        data_file_path,
        metaSrc=config_file_path,
    )

    if rcl_file:
        print(f"Reading data from netCDF file: {rcl_file}")
        try:
            # Read the netCDF file
            ds = xr.open_dataset(rcl_file)
            
            # Extract salinity variables
            sal_vars = [var for var in ds.data_vars if var.startswith('salinity_') and 'diff' not in var]
            
            # Create dataframe with multi-index columns from netCDF attributes
            time_index = ds.time.values
            data_dict = {}
            columns = []
            
            for var in sal_vars:
                # Extract metadata from netCDF attributes
                serial_number = ds[var].attrs.get('serial_number', 'unknown')
                depth_label = ds[var].attrs.get('depth_label', '')
                
                if not depth_label:
                    # Fallback: parse from variable name
                    depth_label = var.replace('salinity_', '').split('_')[-1]
                
                # Create tuple column (instance, serial, depth_label)
                col = (1, serial_number, depth_label)
                columns.append(col)
                data_dict[col] = ds[var].values
            
            # Create DataFrame with multi-index columns
            original_saldf = pd.DataFrame(data_dict, index=time_index)
            
            ds.close()
            
            if original_saldf.index.tz is not None:
                original_saldf.index = original_saldf.index.tz_localize(None)
            
            print(f"Loaded {len(columns)} variables with multi-index columns from netCDF")
                
        except Exception as e:
            print(f"Error reading netCDF file: {str(e)}")
            raise
    else:
        sz = deployment.SZ.data
        original_saldf = sz.copy()
        original_saldf.index = original_saldf.index.tz_localize(None)

    original_saldf = original_saldf.astype('float64')
    
    # Load quality flags from netCDF if available
    nc_flag_file = f"qual_dm_sz_{dep_id}.nc"
    qual_dm = None
    
    if os.path.exists(nc_flag_file):
        try:
            print(f"Loading quality flags from netCDF file: {nc_flag_file}")
            flag_ds = xr.open_dataset(nc_flag_file)
            
            # Get time coordinate from netCDF and normalize timezone
            time_index = pd.DatetimeIndex(flag_ds.time.values)
            
            # Remove timezone if present to match salinity data
            if time_index.tz is not None:
                time_index = time_index.tz_localize(None)
            
            # Create DataFrame with flag time index first
            qual_dm_orig = pd.DataFrame(index=time_index)
            
            for var in flag_ds.data_vars:
                if 'salinity_flags_' in var:
                    # Extract serial and depth from variable name
                    serial = flag_ds[var].attrs.get('serial_number', '')
                    depth_label = flag_ds[var].attrs.get('depth_label', '')
                    
                    # Match with original_saldf columns structure
                    for col in original_saldf.columns:
                        if isinstance(col, tuple) and col[1] == serial and col[2] == depth_label:
                            qual_dm_orig[col] = flag_ds[var].values
                            break
            
            flag_ds.close()
            
            # Normalize salinity data index timezone too
            sal_index = original_saldf.index
            if hasattr(sal_index, 'tz') and sal_index.tz is not None:
                sal_index = sal_index.tz_localize(None)
            
            # Reindex to match original_saldf - use nearest neighbor with tolerance
            qual_dm = qual_dm_orig.reindex(sal_index, method='nearest', tolerance=pd.Timedelta('1min'))
            
            # Restore original salinity index (with timezone if present)
            qual_dm.index = original_saldf.index
            
            print(f"Loaded quality flags from netCDF: {len(qual_dm.columns)} columns")
            print(f"Reindexed quality flags to match salinity data index")
            
        except Exception as e:
            print(f"Warning: Error loading netCDF quality flags: {e}. Proceeding without flags.")
            import traceback
            traceback.print_exc()
            qual_dm = None

    # Store the multi-index columns
    multi_index_columns = original_saldf.columns
    print("\nMultiIndex Information:")
    print(f"Number of levels: {multi_index_columns.nlevels}")
    print(f"Level names: {multi_index_columns.names}")
    print(f"Sample column: {multi_index_columns[0]}")

    # Get the actual column names
    actual_columns = [col[-1] if isinstance(col, tuple) else col for col in original_saldf.columns]
    print(f"Available columns in the data: {actual_columns}")

    # Create working copy with simplified column names
    saldf = original_saldf.copy()
    saldf.columns = actual_columns

    if input_file is None:
        input_file = f"adj_{dep_id}.inputs"
    print(f"Using input file: {input_file}")

    df = pd.read_csv(input_file, header=None, comment='#', skip_blank_lines=True)
    df.columns=['starttime','endtime','a1','a2', 'col', 'inst_col']

    # Clean up whitespace in the inst_col column
    df['inst_col'] = df['inst_col'].str.strip()

    unique_inst_cols = df['inst_col'].unique()
    saldf_adjusted = saldf.copy()

    # Collect all plots
    plots = []

    for inst_col in unique_inst_cols:
        column_name = inst_col

        if column_name not in actual_columns:
            raise ValueError(f"Specified column name '{column_name}' not found in data. Available columns: {actual_columns}")

        print(f"Working with column: {column_name}")

        df_filtered = df[df['inst_col'] == inst_col]
        new_dataframes = []

        for index, row in df_filtered.iterrows():
            mask = (saldf.index > pd.to_datetime(row['starttime'])) & (saldf.index <= pd.to_datetime(row['endtime']))
            segment_index = saldf.loc[mask].index

            if len(segment_index) == 0:
                print(f"Warning: No data points found between {row['starttime']} and {row['endtime']}")
                continue

            new_df = pd.DataFrame(index=segment_index, columns=[column_name])
            new_df.iloc[0] = row['a1']
            new_df.iloc[-1] = row['a2']
            new_df = new_df.astype(float)
            new_df = new_df.interpolate()
            new_dataframes.append(new_df)

        if new_dataframes:
            for i, new_df in enumerate(new_dataframes):
                mask = (saldf_adjusted.index > pd.to_datetime(df_filtered.iloc[i]['starttime'])) & (saldf_adjusted.index <= pd.to_datetime(df_filtered.iloc[i]['endtime']))

                # Determine if we need to add or subtract the adjustment
                col_name = df_filtered.iloc[i]['col'].strip()

                if '-' in col_name:
                    # Split the difference column name
                    parts = col_name.split('-')
                    minuend = parts[0].strip()

                    if column_name == minuend:
                        # Subtract the adjustment
                        print(f"Subtracting adjustment for {column_name} (minuend in {col_name})")
                        saldf_adjusted.loc[mask, column_name] -= new_df[column_name]
                    else:
                        # Add the adjustment
                        print(f"Adding adjustment for {column_name} (subtrahend in {col_name})")
                        saldf_adjusted.loc[mask, column_name] += new_df[column_name]
                else:
                    # Not a difference column, just add
                    saldf_adjusted.loc[mask, column_name] += new_df[column_name]

            # Apply quality flags if available
            if qual_dm is not None:
                # Find the corresponding quality column
                qual_col = None
                for col in qual_dm.columns:
                    if isinstance(col, tuple) and col[-1] == column_name:
                        qual_col = qual_dm[col]
                        break
                
                if qual_col is not None:
                    # Mask data where flags are negative (bad data)
                    quality_mask = qual_col >= 0
                    
                    # Use .where() to align indices automatically
                    valid_original = saldf[column_name].where(quality_mask)
                    valid_adjusted = saldf_adjusted[column_name].where(quality_mask)
                    
                    masked_count = (~quality_mask).sum()
                    if masked_count > 0:
                        print(f"Applied quality flags to {column_name}: {masked_count} points masked")
                else:
                    valid_original = saldf[column_name]
                    valid_adjusted = saldf_adjusted[column_name]
            else:
                valid_original = saldf[column_name]
                valid_adjusted = saldf_adjusted[column_name]

            y_min = min(valid_original.min(), valid_adjusted.min())
            y_max = max(valid_original.max(), valid_adjusted.max())
            y_range = y_max - y_min
            y_buffer = y_range * 0.1

            # Create Bokeh figure
            p = figure(width=1200, height=400,
                      x_axis_type='datetime',
                      y_range=(y_min - y_buffer, y_max + y_buffer),
                      title=f'Original vs Adjusted Data - {column_name}')

            # Add HoverTool
            hover = HoverTool(
                tooltips=[
                    ('Date', '@time{%F %T}'),
                    ('Original', '@original{0.000}'),
                    ('Adjusted', '@adjusted{0.000}')
                ],
                formatters={'@time': 'datetime'},
                mode='vline'
            )
            p.add_tools(hover)
            
            # Disable hover by default
            p.toolbar.active_inspect = []

            # Create ColumnDataSource with masked data
            source = ColumnDataSource({
                'time': original_saldf.index,
                'original': valid_original,
                'adjusted': valid_adjusted
            })

            # Add shaded regions for adjustment segments
            for i, row in df_filtered.iterrows():
                start_time = pd.to_datetime(row['starttime'])
                end_time = pd.to_datetime(row['endtime'])

                p.varea(x=[start_time, end_time],
                       y1=[y_min - y_buffer] * 2,
                       y2=[y_max + y_buffer] * 2,
                       fill_color=Spectral6[i % len(Spectral6)],
                       fill_alpha=0.2)

            # Plot original and adjusted data
            orig_line = p.line('time', 'original', line_color='blue', line_alpha=0.7,
                             legend_label='Original', source=source, line_width=2)
            adj_line = p.line('time', 'adjusted', line_color='red', line_alpha=0.7,
                             legend_label='Adjusted', source=source, line_width=2)

            # Customize the plot
            p.xaxis.formatter = DatetimeTickFormatter(
                hours="%Y-%m-%d %H:%M",
                days="%Y-%m-%d",
                months="%Y-%m-%d",
                years="%Y-%m-%d"
            )
            p.xaxis.axis_label = 'Date'
            p.yaxis.axis_label = 'Salinity (PSU)'
            p.legend.click_policy = "hide"
            p.legend.location = "top_right"
            p.xgrid.grid_line_color = None
            p.ygrid.grid_line_color = None
            p.xaxis.axis_label_text_font_size = "10pt"
            p.yaxis.axis_label_text_font_size = "10pt"
            p.title.text_font_size = "12pt"

            # Rotate x-axis labels
            p.xaxis.major_label_orientation = 0.7

            # Add tools
            p.toolbar.autohide = False

            # Add plot to collection
            plots.append(p)
        else:
            print(f"Warning: No valid data segments found for column {column_name}")

    # Show all plots as subplots
    if plots:
        print(f"\nCreating combined plot with {len(plots)} subplots...")

        # Create layout with all plots in a column
        layout = column(plots)

        # Set output file and show all plots together
        output_file(f"{dep_id}_adjustment_plots.html")
        show(layout)
        print(f"Plots saved to {dep_id}_adjustment_plots.html")
    else:
        print("No plots were created.")

    saldf_adjusted = saldf_adjusted.astype('float64')
    
    # Restore multi-index columns before saving
    # saldf_adjusted currently has simplified column names, need to map back to original tuples
    print("\nRestoring multi-index column structure...")
    
    # Create a mapping from simplified names to original tuples
    col_mapping = {}
    for orig_col in multi_index_columns:
        simple_name = orig_col[-1] if isinstance(orig_col, tuple) else orig_col
        col_mapping[simple_name] = orig_col
    
    # Rename columns back to tuples
    saldf_adjusted_with_tuples = saldf_adjusted.copy()
    saldf_adjusted_with_tuples.columns = [col_mapping.get(col, col) for col in saldf_adjusted.columns]
    
    print("\nComputing conductivity and density adjustments...")
    cond_adjusted, dens_adjusted = compute_adjustments(saldf_adjusted, deployment)
    
    # Also restore multi-index for conductivity and density
    cond_adjusted_with_tuples = cond_adjusted.copy()
    dens_adjusted_with_tuples = dens_adjusted.copy()
    
    if len(cond_adjusted.columns) > 0:
        cond_adjusted_with_tuples.columns = [col_mapping.get(col, col) for col in cond_adjusted.columns]
    if len(dens_adjusted.columns) > 0:
        dens_adjusted_with_tuples.columns = [col_mapping.get(col, col) for col in dens_adjusted.columns]

    print("\nSaving adjusted data to netCDF files...")
    
    # Save salinity
    sal_filename = f"{dep_id}_sal_adjusted.nc"
    sal_ds = dataframe_to_dataset(
        saldf_adjusted_with_tuples,
        variable_name='salinity',
        units='PSU',
        long_name='Practical salinity (adjusted)',
        deployment_id=dep_id,
        lat=deployment.latitude,
        lon=deployment.longitude,
        processing_note='Adjusted based on difference analysis and manual corrections'
    )
    sal_ds.attrs['standard_name'] = 'sea_water_practical_salinity'
    sal_ds.to_netcdf(sal_filename, format='NETCDF4', engine='netcdf4')
    print(f"✓ Saved adjusted salinity to {sal_filename}")
    
    # Save conductivity
    cond_filename = f"{dep_id}_cond_adjusted.nc"
    cond_ds = dataframe_to_dataset(
        cond_adjusted_with_tuples,
        variable_name='conductivity',
        units='mS/cm',
        long_name='Conductivity (adjusted)',
        deployment_id=dep_id,
        lat=deployment.latitude,
        lon=deployment.longitude,
        processing_note='Calculated from adjusted salinity using GSW toolbox'
    )
    cond_ds.to_netcdf(cond_filename, format='NETCDF4', engine='netcdf4')
    print(f"✓ Saved adjusted conductivity to {cond_filename}")
    
    # Save density
    dens_filename = f"{dep_id}_dens_adjusted.nc"
    dens_ds = dataframe_to_dataset(
        dens_adjusted_with_tuples,
        variable_name='density',
        units='kg/m^3',
        long_name='Potential density anomaly (sigma0, adjusted)',
        deployment_id=dep_id,
        lat=deployment.latitude,
        lon=deployment.longitude,
        processing_note='Calculated from adjusted salinity using GSW toolbox'
    )
    dens_ds.attrs['reference_pressure'] = '0 dbar'
    dens_ds.to_netcdf(dens_filename, format='NETCDF4', engine='netcdf4')
    print(f"✓ Saved adjusted density to {dens_filename}")

    return saldf_adjusted, cond_adjusted, dens_adjusted


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Apply salinity adjustments and export to netCDF for GTMBA data'
    )
    parser.add_argument("dep_id", help="Deployment ID (e.g., pt005)")
    parser.add_argument("--rcl", help="Read adjusted salinity data from specified netCDF file")

    if any('ipykernel' in arg for arg in sys.argv):
        ipython_args = sys.argv[1:]
        args = parser.parse_args(ipython_args)
    else:
        args = parser.parse_args()

    input_file = f"adj_{args.dep_id}.inputs"

    try:
        print("\nStarting data processing...")
        sal_result, cond_result, dens_result = process_data(args.dep_id, input_file=input_file, rcl_file=args.rcl)

        print("\n" + "="*80)
        print("ADJUSTMENT PROCESSING COMPLETE")
        print("="*80)
        print(f"Deployment ID: {args.dep_id}")
        print(f"\nSaved adjusted data files:")
        print(f"  - Salinity:     {args.dep_id}_sal_adjusted.nc")
        print(f"  - Conductivity: {args.dep_id}_cond_adjusted.nc")
        print(f"  - Density:      {args.dep_id}_dens_adjusted.nc")
        print(f"  - Plots:        {args.dep_id}_adjustment_plots.html")
        print("="*80 + "\n")
    except Exception as e:
        print(f"\nError during processing: {str(e)}")
        raise
