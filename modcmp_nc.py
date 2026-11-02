from tao.flex.data import Deployment
import os
from pathlib import Path
import argparse
from bokeh.plotting import figure, show
from bokeh.layouts import column as bokeh_column, row
from bokeh.models import ColumnDataSource, HoverTool, CustomJS, DatetimeTickFormatter, Range1d, LinearAxis
from bokeh.palettes import Category10
import pandas as pd
import numpy as np
import glob

parser = argparse.ArgumentParser()
parser.add_argument("dep_id", help="Enter Deployment ID, ex: pt006")
parser.add_argument("dep_id2", help="Enter Deployment ID, ex: pt006")
args = parser.parse_args()

home = os.path.expanduser('~')
data_dir = Path(home + "/data/flexram/")

# Define base paths using the new structure
base_path1 = data_dir / (args.dep_id + "-proc") / "data" / "subsurface"
base_path2 = data_dir / (args.dep_id2 + "-proc") / "data" / "subsurface"

# Define file paths using the new structure
file_path1 = base_path1 / (args.dep_id + "-sbe-data.bz2")
file_path2 = base_path2 / (args.dep_id2 + "-sbe-data.bz2")

# Define config paths
config_path1 = base_path1 / "config.xml"
config_path2 = base_path2 / "config.xml"

did = args.dep_id
did2 = args.dep_id2

print(f"Loading data from: {file_path1}")
print(f"Loading data from: {file_path2}")

# Load deployments with new paths
dep1 = Deployment(str(file_path1), metaSrc=str(config_path1))
dep2 = Deployment(str(file_path2), metaSrc=str(config_path2))

# Process first deployment with quality flag masking
# Get quality flags for salinity
sz_qual1 = dep1.SZ.qual_dm
dfsz_qual1 = sz_qual1.copy()
dfsz_qual1.columns = dfsz_qual1.columns.droplevel(level=0)
dfsz_qual1.columns = dfsz_qual1.columns.droplevel(level=0)

# Get salinity data
sz1 = dep1.SZ.data
saldf = sz1.copy()
saldf.columns = saldf.columns.droplevel(level=0)
saldf.columns = saldf.columns.droplevel(level=0)
saldf.index = pd.to_datetime(saldf.index).tz_localize(None)
saldf = saldf.astype('float64')
saldf = saldf.round(4)

# Debug: Print column information
print(f"Salinity columns: {list(saldf.columns)}")
print(f"Quality flag columns: {list(dfsz_qual1.columns)}")

# Mask values where quality flags are negative using numpy arrays
for col in saldf.columns:
    if col in dfsz_qual1.columns:
        try:
            # Convert to numpy arrays and make a copy to avoid read-only issues
            qual_array = dfsz_qual1[col].values
            sal_array = saldf[col].values.copy()  # Make a copy to allow modification
            # Apply mask where quality flags are negative
            sal_array[qual_array < 0] = np.nan
            # Assign back to dataframe
            saldf[col] = sal_array
        except Exception as e:
            print(f"Warning: Could not apply quality mask for column {col}: {e}")
            print(f"Skipping quality flag masking for this column")
    else:
        print(f"No quality flag found for column {col}, skipping masking")

saldf_plot = saldf.copy()

# Process second deployment with quality flag masking
# Get quality flags for salinity
sz_qual2 = dep2.SZ.qual_dm
dfsz_qual2 = sz_qual2.copy()
dfsz_qual2.columns = dfsz_qual2.columns.droplevel(level=0)
dfsz_qual2.columns = dfsz_qual2.columns.droplevel(level=0)

# Get salinity data
sz2 = dep2.SZ.data
saldf2 = sz2.copy()
saldf2.columns = saldf2.columns.droplevel(level=0)
saldf2.columns = saldf2.columns.droplevel(level=0)
saldf2.index = pd.to_datetime(saldf2.index).tz_localize(None)
saldf2 = saldf2.astype('float64')
saldf2 = saldf2.round(4)

# Mask values where quality flags are negative using numpy arrays
for col in saldf2.columns:
    if col in dfsz_qual2.columns:
        try:
            # Convert to numpy arrays and make a copy to avoid read-only issues
            qual_array = dfsz_qual2[col].values
            sal_array = saldf2[col].values.copy()  # Make a copy to allow modification
            # Apply mask where quality flags are negative
            sal_array[qual_array < 0] = np.nan
            # Assign back to dataframe
            saldf2[col] = sal_array
        except Exception as e:
            print(f"Warning: Could not apply quality mask for column {col} in dataset 2: {e}")
            print(f"Skipping quality flag masking for this column")
    else:
        print(f"No quality flag found for column {col} in dataset 2, skipping masking")

saldf2_plot = saldf2.copy()

# Calculate y-range for both datasets
y_min = min(saldf_plot.min().min(), saldf2_plot.min().min())
y_max = max(saldf_plot.max().max(), saldf2_plot.max().max())
y_range = (y_min - 0.1, y_max + 0.1)  # Add a small buffer

# Calculate x-range for both datasets
x_range1 = (saldf_plot.index.min(), saldf_plot.index.max())
x_range2 = (saldf2_plot.index.min(), saldf2_plot.index.max())

# Create Bokeh figures with increased width and height
p1 = figure(title=did, x_axis_label='Date', y_axis_label='Salinity', x_range=x_range1, y_range=y_range,
           width=800, height=600, x_axis_type="datetime", toolbar_location="left", background_fill_color="lightgrey")
p2 = figure(title=did2, x_axis_label='Date', y_axis_label='Salinity', x_range=x_range2, y_range=y_range,
           width=800, height=600, x_axis_type="datetime", background_fill_color="lightgrey")

# Link the y-ranges of both plots
p1.y_range = p2.y_range

# Set x-axis formatter to ISO format
date_formatter = DatetimeTickFormatter(
    hours="%Y-%m-%d %H:%M",
    days="%Y-%m-%d",
    months="%Y-%m-%d",
    years="%Y-%m-%d"
)
p1.xaxis.formatter = date_formatter
p2.xaxis.formatter = date_formatter

# Generate color palettes using Category10
num_colors = max(len(saldf_plot.columns), len(saldf2_plot.columns))
colors = Category10[10] * (num_colors // 10 + 1)  # Repeat the palette if needed
colors = colors[:num_colors]  # Trim to the required number of colors

# Store all glyph renderers
renderers1 = []
renderers2 = []

# Add lines to the first plot
for column, color in zip(saldf_plot.columns, colors):
    source = ColumnDataSource(data=dict(
        x=saldf_plot.index,
        y=saldf_plot[column]
    ))
    renderer = p1.line('x', 'y', source=source, color=color, name=str(column))
    renderers1.append(renderer)

# Add lines to the second plot
for column, color in zip(saldf2_plot.columns, colors):
    source = ColumnDataSource(data=dict(
        x=saldf2_plot.index,
        y=saldf2_plot[column]
    ))
    renderer = p2.line('x', 'y', source=source, color=color, legend_label=str(column), name=str(column))
    renderers2.append(renderer)

# Add hover tool
hover = HoverTool(
    tooltips=[('Date', '@x{%F %T}'), ('Salinity', '@y')],
    formatters={'@x': 'datetime'}
)
p1.add_tools(hover)
p2.add_tools(hover)

# Disable hover by default
p1.toolbar.active_inspect = []
p2.toolbar.active_inspect = []

# Customize the plots
p2.legend.location = "right"
p2.legend.click_policy = "hide"

# Create a custom JavaScript callback for syncing zooming and panning
sync_callback = CustomJS(args=dict(p1=p1, p2=p2), code="""
    const y_range = p2.y_range;
    p1.y_range.start = y_range.start;
    p1.y_range.end = y_range.end;
""")

# Attach the callback to p2's y-range
p2.y_range.js_on_change('start', sync_callback)
p2.y_range.js_on_change('end', sync_callback)

# Create a custom JavaScript callback for toggling visibility
visibility_code = """
    const renderers1 = Bokeh.documents[0].get_model_by_name('plot1').renderers;
    const renderers2 = Bokeh.documents[0].get_model_by_name('plot2').renderers;

    for (let i = 0; i < renderers1.length; i++) {
        if (renderers1[i].name === this.name) {
            renderers1[i].visible = this.visible;
        }
    }

    for (let i = 0; i < renderers2.length; i++) {
        if (renderers2[i].name === this.name) {
            renderers2[i].visible = this.visible;
        }
    }
"""

# Attach the visibility callback to each renderer in the second plot
for renderer in renderers2:
    renderer.js_on_change('visible', CustomJS(code=visibility_code))

# Set names for the plots
p1.name = 'plot1'
p2.name = 'plot2'

# Calculate differences between last non-NaN value in saldf and first non-NaN value in saldf2
differences = {}
for column in saldf_plot.columns:
    if column in saldf2_plot.columns:
        last_value_saldf = saldf_plot[column].dropna().iloc[-1] if not saldf_plot[column].dropna().empty else None
        first_value_saldf2 = saldf2_plot[column].dropna().iloc[0] if not saldf2_plot[column].dropna().empty else None

        if last_value_saldf is not None and first_value_saldf2 is not None:
            difference = last_value_saldf - first_value_saldf2
            differences[column] = difference

# Find any existing *_Salnotes.txt file in current directory
existing_files = glob.glob("*_Salnotes.txt")

if existing_files:
    # Use the first found *_Salnotes.txt file
    output_path = Path(existing_files[0])

    # Write or append the differences to the existing file
    with open(output_path, 'a') as f:
        f.write(f"\nDifferences between {did} and {did2}\n")
        f.write(f"Last non-NaN in {did} - First non-NaN in {did2}:\n")
        f.write("-" * 50 + "\n")
        for column, diff in differences.items():
            f.write(f"Column {column}: {diff:.6f}\n")
        f.write("-" * 50 + "\n\n")
else:
    print("No existing *_Salnotes.txt file found in current directory.")

# Show the plots side by side
show(row(p1, p2))
