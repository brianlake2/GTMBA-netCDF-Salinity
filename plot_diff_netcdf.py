"""
Salinity Difference Interactive Plotting and Data Export

This script processes salinity data from GTMBA moorings and creates
interactive Bokeh plots for selecting adjustment points. It can work with
either original deployment data or adjusted salinity data from netCDF files.

Usage:
    python plot_diff_netcdf.py <deployment_id> <inst_col>
    python plot_diff_netcdf.py <deployment_id> <inst_col> --rcl <adjusted_file.nc>

Example:
    python plot_diff_netcdf.py pt005 SSS
    python plot_diff_netcdf.py pt005 SSS --rcl pt005_sal_drift.nc
"""

import argparse
import pandas as pd
import numpy as np
from tao.flex.data import Deployment
import os
import xarray as xr
from datetime import datetime
import sys
import warnings
from bokeh.plotting import figure
from bokeh.layouts import column as bokeh_column, row
from bokeh.models import ColumnDataSource, HoverTool, Button, Span, Div
from bokeh.server.server import Server
from bokeh.application import Application
from bokeh.application.handlers.function import FunctionHandler

# Suppress the timezone warning from Bokeh serialization
warnings.filterwarnings("ignore", message="no explicit representation of timezones available for np.datetime64", category=UserWarning, module="bokeh.util.serialization")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_depth_number(column):
    """
    Extract depth number from column name for sorting.
    
    Parameters:
    -----------
    column : str
        Column name (e.g., 'SSS', 'S010')
        
    Returns:
    --------
    int or float
        Depth number for sorting (-1 for SSS, inf for non-standard)
    """
    if column == 'SSS':
        return -1  # Put SSS first
    try:
        return int(column.replace('S', ''))
    except:
        return float('inf')  # Put non-standard names last


def generate_column_order(columns):
    """
    Generate ordered list of difference columns.
    
    Parameters:
    -----------
    columns : list
        List of all column names
        
    Returns:
    --------
    list
        Ordered list of difference column names
    """
    base_columns = sorted([col for col in columns if '-' not in col],
                        key=get_depth_number)

    ordered_combinations = []

    # First add SSS differences if they exist
    if 'SSS' in base_columns:
        for col in base_columns:
            if col != 'SSS' and f'{col}-SSS' in columns:
                ordered_combinations.append(f'{col}-SSS')

    # Then add depth-to-depth differences
    for i, col1 in enumerate(base_columns):
        for col2 in base_columns[i+1:]:
            if f'{col2}-{col1}' in columns and f'{col2}-{col1}' not in ordered_combinations:
                ordered_combinations.append(f'{col2}-{col1}')

    # Remove any duplicates while preserving order
    ordered_combinations = list(dict.fromkeys(ordered_combinations))
    return ordered_combinations


def load_salinity_data(args):
    """
    Load salinity data from either adjusted netCDF file or deployment data.
    
    Parameters:
    -----------
    args : argparse.Namespace
        Command-line arguments
        
    Returns:
    --------
    pd.DataFrame
        Salinity dataframe with difference columns
    """
    home = os.path.expanduser('~')
    
    if args.rcl:
        # Read adjusted salinity data from specified netCDF file
        adjusted_file = args.rcl
        try:
            # Read the netCDF file
            ds = xr.open_dataset(adjusted_file)
            print(f"Reading adjusted salinity data from: {adjusted_file}")
            
            # Convert dataset to dataframe
            # Extract only salinity variables (not salinity_diff variables)
            sal_vars = [var for var in ds.data_vars if var.startswith('salinity_') and 'diff' not in var]
            
            # Create dataframe from salinity variables
            saldf = pd.DataFrame(index=ds.time.values)
            
            for var in sal_vars:
                # Extract depth label from variable attributes or name
                if 'depth_label' in ds[var].attrs:
                    depth_label = ds[var].attrs['depth_label']
                else:
                    # Parse from variable name (e.g., 'salinity_SSS' -> 'SSS')
                    depth_label = var.replace('salinity_', '')
                
                saldf[depth_label] = ds[var].values

            # Create the difference columns if they don't exist
            base_columns = [col for col in saldf.columns if '-' not in col]
            for i in base_columns:
                for j in base_columns:
                    if i != j and f'{i}-{j}' not in saldf.columns:
                        saldf[f'{i}-{j}'] = saldf[i] - saldf[j]
            
            ds.close()

        except FileNotFoundError:
            print(f"Error: Adjusted salinity file '{adjusted_file}' not found")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading netCDF file: {str(e)}")
            sys.exit(1)
    else:
        # Original data loading code
        dep_path = home + "/data/flexram/" + args.dep_id + "/serialized/" + args.dep_id + "_flashfile-nparray-py3.bz2"
        meta_path = home + "/data/flexram/" + args.dep_id + "/config.xml"
        
        print(f"Loading deployment data from: {dep_path}")

        dep_id = Deployment(dep_path, metaSrc=meta_path)

        # Data processing
        sz = dep_id.SZ.data
        dfsz = sz.copy()
        dfsz.columns = dfsz.columns.droplevel(level=0)
        dfsz1 = dfsz.copy()
        dfsz1.columns = dfsz.columns.droplevel(level=0)

        saldf = dfsz1

        # Create difference columns
        base_columns = saldf.columns.values
        for i in base_columns:
            for j in base_columns:
                if i != j:
                    saldf[f'{i}-{j}'] = saldf[i] - saldf[j]
    
    return saldf


def create_bokeh_plot(df, column_name, plot_index):
    """
    Create an interactive Bokeh plot for a single salinity difference column.
    
    Parameters:
    -----------
    df : pd.DataFrame
        Salinity dataframe
    column_name : str
        Column name to plot
    plot_index : int
        Index of this plot in the sequence
        
    Returns:
    --------
    bokeh.plotting.figure
        Bokeh plot object
    """
    source = ColumnDataSource(data=dict(x=df.index, y=df[column_name]))
    selected_source = ColumnDataSource(data=dict(x=[], y=[]))
    line_source = ColumnDataSource(data=dict(x=[], y=[]))
    rubberband_source = ColumnDataSource(data=dict(x=[], y=[]))  # For the stretchy line

    p = figure(title=column_name, x_axis_type="datetime", width=1200, height=300)

    # Add light grey background
    p.background_fill_color = "#f5f5f5"
    p.background_fill_alpha = 0.5

    # Add dotted green line at y=0 spanning entire x-range
    p.add_layout(Span(location=0, dimension='width', line_color='green',
                     line_dash='dotted', line_width=1))

    # Original data line
    main_line = p.line('x', 'y', source=source)

    # Create hover tool and add to toolbar, but set to inactive by default
    hover = HoverTool(
        tooltips=[("Date", "@x{%F}"), ("Value", "@y")],
        formatters={"@x": "datetime"},
        renderers=[main_line],
        anchor="right",
        attachment="left"
    )
    
    # Add hover tool to plot
    p.add_tools(hover)
    
    # Set hover tool to inactive by default (but it will appear in toolbar)
    p.toolbar.active_inspect = []

    # Selected points with smaller circles and no hover
    p.scatter('x', 'y', source=selected_source, size=5, color='red', fill_color='red')

    # Dotted line connecting selected points
    p.line('x', 'y', source=line_source, line_dash='dotted', line_width=2, color='red')

    # Rubberband line (stretches from last point to cursor)
    p.line('x', 'y', source=rubberband_source, line_dash='dashed', line_width=2, 
           color='blue', alpha=0.6)

    # Define the tap callback
    def tap_callback(event):
        new_x, new_y = event.x, event.y
        selected_source.stream(dict(x=[new_x], y=[new_y]))
        all_points_source.stream(dict(x=[new_x], y=[new_y], plot=[plot_index]))

        x_data = selected_source.data['x']
        y_data = selected_source.data['y']
        sorted_indices = sorted(range(len(x_data)), key=lambda k: x_data[k])
        line_source.data = dict(x=[x_data[i] for i in sorted_indices],
                              y=[y_data[i] for i in sorted_indices])

    # Mouse move callback for rubberband
    def mouse_move_callback(event):
        # Only update rubberband if it's enabled
        if not rubberband_enabled['state']:
            return
            
        x_data = selected_source.data.get('x', [])
        y_data = selected_source.data.get('y', [])
        
        if len(x_data) > 0:
            # Get the last selected point
            last_x = x_data[-1]
            last_y = y_data[-1]
            
            # Update rubberband to show line from last point to current cursor position
            rubberband_source.data = dict(x=[last_x, event.x], y=[last_y, event.y])
        else:
            # Clear rubberband if no points selected
            rubberband_source.data = dict(x=[], y=[])

    # Add event handlers
    p.on_event('tap', tap_callback)
    p.on_event('mousemove', mouse_move_callback)

    # Store references
    plot_sources[plot_index] = {
        'selected': selected_source,
        'line': line_source,
        'rubberband': rubberband_source,
        'plot': p
    }

    return p


def modify_doc(doc):
    """
    Modify Bokeh document to add plots and interactive controls.
    
    Parameters:
    -----------
    doc : bokeh.document.Document
        Bokeh document object
    """
    plots = []
    for i, column_name in enumerate(desired_order):
        if column_name in saldf.columns:
            plots.append(create_bokeh_plot(saldf, column_name, i))

    # Double-click event handler for toggling rubberband
    def doubleclick_callback(event):
        toggle_rubberband()
    
    # Add double-click event handler to all plots
    for p in plots:
        p.on_event('doubletap', doubleclick_callback)

    def save_points():
        """Save selected points to adjustment input file."""
        df = pd.DataFrame({
            'x': all_points_source.data['x'],
            'y': all_points_source.data['y'],
            'plot': all_points_source.data['plot']
        })
        df['DT'] = pd.to_datetime(df['x'], unit='ms')
        final = df[['DT', 'y', 'plot']].sort_values('DT')

        output_filename = f'adj_{dep_name}.inputs'

        file_exists = os.path.isfile(output_filename)

        with open(output_filename, 'a' if file_exists else 'w') as f:
            if not file_exists:
                # Write header with column names
                f.write(f"# StartDate, EndDate, {'StartVal':>10}, {'EndVal':>10}, ColName, InstCol\n")
                f.write("# " + "="*85 + "\n")

            f.write("#\n")

            for i in range(len(final) - 1):
                start_date = f"{final.iloc[i]['DT']:%Y-%m-%d %H:%M}"
                end_date = f"{final.iloc[i+1]['DT']:%Y-%m-%d %H:%M}"
                start_val = final.iloc[i]['y']
                end_val = final.iloc[i+1]['y']
                col_name = desired_order[int(final.iloc[i]['plot'])]

                f.write(f"{start_date}, "                # StartDate
                       f"{end_date}, "                   # EndDate
                       f"{start_val:10.6f}, "            # StartValue (right-aligned, 10 chars)
                       f"{end_val:10.6f}, "              # EndValue (right-aligned, 10 chars)
                       f"{col_name}, "                   # ColumnName
                       f"{inst_col}\n")                  # InstCol

            f.write("#\n")

        print(f"Output {'appended to' if file_exists else 'written to'} {output_filename}")
        print(f"Number of points saved: {len(final)}")

    def clear_points():
        """Clear all selected points."""
        all_points_source.data = dict(x=[], y=[], plot=[])
        for sources in plot_sources.values():
            sources['selected'].data = dict(x=[], y=[])
            sources['line'].data = dict(x=[], y=[])
            sources['rubberband'].data = dict(x=[], y=[])
        print("All points cleared")

    def clear_last_point():
        """Clear the most recently selected point."""
        # Check if there are any points to clear
        if len(all_points_source.data['x']) == 0:
            print("No points to clear")
            return

        # Get the last point's plot index
        last_plot_index = all_points_source.data['plot'][-1]

        # Remove the last point from the global source
        all_points_source.data = {
            'x': all_points_source.data['x'][:-1],
            'y': all_points_source.data['y'][:-1],
            'plot': all_points_source.data['plot'][:-1]
        }

        # Remove the last point from the specific plot's selected source
        if last_plot_index in plot_sources:
            selected_source = plot_sources[last_plot_index]['selected']
            line_source = plot_sources[last_plot_index]['line']
            rubberband_source = plot_sources[last_plot_index]['rubberband']

            if len(selected_source.data['x']) > 0:
                selected_source.data = {
                    'x': selected_source.data['x'][:-1],
                    'y': selected_source.data['y'][:-1]
                }

                # Update the connecting line
                x_data = selected_source.data['x']
                y_data = selected_source.data['y']
                if len(x_data) > 0:
                    sorted_indices = sorted(range(len(x_data)), key=lambda k: x_data[k])
                    line_source.data = dict(x=[x_data[i] for i in sorted_indices],
                                          y=[y_data[i] for i in sorted_indices])
                else:
                    line_source.data = dict(x=[], y=[])
                    rubberband_source.data = dict(x=[], y=[])

        print("Last point cleared")

    def toggle_rubberband():
        """Toggle rubberband on/off."""
        rubberband_enabled['state'] = not rubberband_enabled['state']
        
        if not rubberband_enabled['state']:
            # Clear all rubberband lines when disabling
            for sources in plot_sources.values():
                sources['rubberband'].data = dict(x=[], y=[])
            toggle_button_top.label = "Enable Rubberband"
            toggle_button_bottom.label = "Enable Rubberband"
            toggle_button_top.button_type = "success"
            toggle_button_bottom.button_type = "success"
            print("Rubberband disabled (double-click or button to re-enable)")
        else:
            toggle_button_top.label = "Disable Rubberband"
            toggle_button_bottom.label = "Disable Rubberband"
            toggle_button_top.button_type = "default"
            toggle_button_bottom.button_type = "default"
            print("Rubberband enabled (double-click or button to disable)")
    
    def exit_program():
        """Exit the program."""
        print("Exiting the program...")
        global server
        from tornado.ioloop import IOLoop

        # Stop server and exit immediately
        def shutdown():
            server.stop()
            IOLoop.current().stop()
            sys.exit(0)

        IOLoop.current().add_callback(shutdown)

    # Create buttons for top
    toggle_button_top = Button(label="Disable Rubberband", button_type="default")
    toggle_button_top.on_click(toggle_rubberband)

    save_button_top = Button(label="Save Points", button_type="success")
    save_button_top.on_click(save_points)

    clear_button_top = Button(label="Clear All Points", button_type="warning")
    clear_button_top.on_click(clear_points)

    clear_last_button_top = Button(label="Clear Last Selection", button_type="warning")
    clear_last_button_top.on_click(clear_last_point)

    exit_button_top = Button(label="Exit", button_type="danger")
    exit_button_top.on_click(exit_program)

    # Create buttons for bottom
    toggle_button_bottom = Button(label="Disable Rubberband", button_type="default")
    toggle_button_bottom.on_click(toggle_rubberband)

    save_button_bottom = Button(label="Save Points", button_type="success")
    save_button_bottom.on_click(save_points)

    clear_button_bottom = Button(label="Clear All Points", button_type="warning")
    clear_button_bottom.on_click(clear_points)

    clear_last_button_bottom = Button(label="Clear Last Selection", button_type="warning")
    clear_last_button_bottom.on_click(clear_last_point)

    exit_button_bottom = Button(label="Exit", button_type="danger")
    exit_button_bottom.on_click(exit_program)

    # Info text for shortcuts
    info_div = Div(text="<p style='font-size: 12px; color: #666;'><b>Tips:</b> <b>Double-click</b> on any plot or use the toggle button to turn rubberband stretchy line on/off | Click the hover icon in the toolbar to enable hover tooltips</p>")

    # Button rows
    top_button_row = row(toggle_button_top, save_button_top, clear_button_top, clear_last_button_top, exit_button_top)
    bottom_button_row = row(toggle_button_bottom, save_button_bottom, clear_button_bottom, clear_last_button_bottom, exit_button_bottom)

    # Create layout
    layout = bokeh_column(info_div, top_button_row, *plots, bottom_button_row)
    doc.add_root(layout)


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Interactive salinity difference plotting for GTMBA data'
    )
    parser.add_argument('dep_id', help='Deployment ID')
    parser.add_argument(
        'inst_col',
        help='Instrument column name (e.g., SSS, S010)'
    )
    parser.add_argument(
        '--rcl',
        metavar='FILENAME',
        help='Read adjusted salinity data from specified netCDF file'
    )
    args = parser.parse_args()

    dep_name = args.dep_id
    inst_col = args.inst_col

    # Load salinity data
    saldf = load_salinity_data(args)

    # Generate the desired order dynamically
    available_columns = saldf.columns.tolist()
    desired_order = generate_column_order(available_columns)

    # Global source for all selected points
    all_points_source = ColumnDataSource(data=dict(x=[], y=[], plot=[]))

    # Global dictionary to store ColumnDataSources for each plot
    plot_sources = {}

    # Global state to track rubberband enabled/disabled
    rubberband_enabled = {'state': True}  # Use dict so it's mutable across closures

    # Set up the Bokeh server
    server = Server({'/': Application(FunctionHandler(modify_doc))})
    server.start()

    print('Opening Bokeh application on http://localhost:5006/')

    server.io_loop.add_callback(server.show, "/")
    server.io_loop.start()
