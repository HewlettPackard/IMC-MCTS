# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Universal Scientific Plotting Library
====================================

A simple, flexible plotting library for creating publication-quality scientific figures.
Works with any data - just load and plot!

Usage:
    from plotstyle import plot, scatter, line, bar, save_fig

    # Quick scatter plot
    scatter(x, y, labels=['Point 1', 'Point 2'], colors=['red', 'blue'])

    # Quick line plot
    line(x, y, title='My Data', xlabel='Time', ylabel='Value')

    # Save as SVG
    save_fig('my_plot.svg')
"""

import matplotlib.pyplot as plt
import numpy as np
from typing import Union, List, Optional, Tuple, Dict, Any
import pandas as pd

# Global style settings
plt.rcParams['font.family'] = 'serif'
plt.rcParams['font.serif'] = ['Times New Roman'] + plt.rcParams['font.serif']
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 300
plt.rcParams['savefig.bbox'] = 'tight'
plt.rcParams['savefig.pad_inches'] = 0.1
plt.rcParams['lines.linewidth'] = 2.0
plt.rcParams['axes.linewidth'] = 1.2
plt.rcParams['grid.alpha'] = 0.7
plt.rcParams['grid.linewidth'] = 0.5

# Default color palette (professional, accessible colors)
DEFAULT_COLORS = [
    '#1f77b4',  # Blue
    '#ff7f0e',  # Orange
    '#2ca02c',  # Green
    '#d62728',  # Red
    '#9467bd',  # Purple
    '#8c564b',  # Brown
    '#e377c2',  # Pink
    '#7f7f7f',  # Gray
    '#bcbd22',  # Olive
    '#17becf',  # Cyan
]

# Font sizes
FONT_SIZES = {
    'small': 10,
    'medium': 12,
    'large': 15,
    'xlarge': 18,
    'xxlarge': 22,
    'title': 24
}

# Background colors
BACKGROUNDS = {
    'white': '#ffffff',
    'light': '#f7fcff',  # Your original light blue
    'gray': '#f5f5f5',
    'none': 'none'
}

def _setup_figure(figsize: Tuple[float, float] = (10, 6),
                 background: str = 'white',
                 grid: bool = True) -> Tuple[plt.Figure, plt.Axes]:
    """Create a styled figure with axes."""
    figure, axes = plt.subplots(figsize=figsize)

    if background != 'none':
        axes.set_facecolor(BACKGROUNDS[background])

    if grid:
        axes.grid(True, alpha=0.7, linewidth=0.5)

    return figure, axes

def _style_axes(ax: plt.Axes,
               title: Optional[str] = None,
               xlabel: Optional[str] = None,
               ylabel: Optional[str] = None,
               xlim: Optional[Tuple[float, float]] = None,
               ylim: Optional[Tuple[float, float]] = None,
               xscale: str = 'linear',
               yscale: str = 'linear',
               fontsize: str = 'large') -> None:
    """Apply consistent styling to axes."""
    if title:
        ax.set_title(title, fontsize=FONT_SIZES['title'], pad=20)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=FONT_SIZES[fontsize])
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=FONT_SIZES[fontsize])

    if xlim:
        ax.set_xlim(xlim)
    if ylim:
        ax.set_ylim(ylim)

    if xscale == 'log':
        ax.set_xscale('log')
    if yscale == 'log':
        ax.set_yscale('log')

    ax.tick_params(axis='both', which='major', labelsize=FONT_SIZES[fontsize])
    ax.tick_params(axis='both', which='minor', labelsize=FONT_SIZES['medium'])

def _get_colors(n_colors: int, colors: Optional[List[str]] = None) -> List[str]:
    """Get a list of colors for plotting."""
    if colors is None:
        return DEFAULT_COLORS[:n_colors]
    elif len(colors) >= n_colors:
        return colors[:n_colors]
    else:
        # Extend colors if needed
        extended_colors = colors.copy()
        while len(extended_colors) < n_colors:
            extended_colors.extend(DEFAULT_COLORS)
        return extended_colors[:n_colors]

def scatter(x: Union[np.ndarray, List],
           y: Union[np.ndarray, List],
           labels: Optional[List[str]] = None,
           colors: Optional[List[str]] = None,
           sizes: Optional[Union[int, List[int]]] = None,
           alpha: float = 0.8,
           figsize: Tuple[float, float] = (10, 6),
           title: Optional[str] = None,
           xlabel: Optional[str] = None,
           ylabel: Optional[str] = None,
           xlim: Optional[Tuple[float, float]] = None,
           ylim: Optional[Tuple[float, float]] = None,
           xscale: str = 'linear',
           yscale: str = 'linear',
           background: str = 'white',
           grid: bool = True,
           legend: bool = True,
           **kwargs) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a scatter plot with your scientific style.

    Args:
        x, y: Data arrays
        labels: Labels for each data series
        colors: Colors for each data series
        sizes: Marker sizes (single value or list)
        alpha: Transparency
        figsize: Figure size
        title: Plot title
        xlabel, ylabel: Axis labels
        xlim, ylim: Axis limits
        xscale, yscale: Axis scales ('linear' or 'log')
        background: Background color ('white', 'light', 'gray', 'none')
        grid: Show grid
        legend: Show legend
        **kwargs: Additional arguments passed to scatter

    Returns:
        (figure, axes) tuple
    """
    # Convert to numpy arrays
    x = np.asarray(x)
    y = np.asarray(y)

    # Handle multiple data series
    if x.ndim > 1 or y.ndim > 1:
        series_count = max(x.shape[0] if x.ndim > 1 else 1,
                           y.shape[0] if y.ndim > 1 else 1)
    else:
        series_count = 1

    figure, axes = _setup_figure(figsize, background, grid)
    colors = _get_colors(series_count, colors)

    if sizes is None:
        sizes = [100] * series_count
    elif isinstance(sizes, (int, float)):
        sizes = [sizes] * series_count

    # Plot data
    if series_count == 1:
        axes.scatter(x, y, c=colors[0], s=sizes[0], alpha=alpha, **kwargs)
    else:
        for series_index in range(series_count):
            series_x = x[series_index] if x.ndim > 1 else x
            series_y = y[series_index] if y.ndim > 1 else y
            series_label = labels[series_index] if labels and series_index < len(labels) else f'Series {series_index+1}'
            axes.scatter(series_x, series_y, c=colors[series_index], s=sizes[series_index],
                         alpha=alpha, label=series_label, **kwargs)

    # Style axes
    _style_axes(axes, title, xlabel, ylabel, xlim, ylim, xscale, yscale)

    # Add legend if multiple series
    if legend and series_count > 1 and labels:
        axes.legend(fontsize=FONT_SIZES['medium'])

    return figure, axes

def line(x: Union[np.ndarray, List],
         y: Union[np.ndarray, List],
         labels: Optional[List[str]] = None,
         colors: Optional[List[str]] = None,
         linewidths: Optional[Union[float, List[float]]] = None,
         linestyles: Optional[Union[str, List[str]]] = None,
         markers: Optional[Union[str, List[str]]] = None,
         figsize: Tuple[float, float] = (10, 6),
         title: Optional[str] = None,
         xlabel: Optional[str] = None,
         ylabel: Optional[str] = None,
         xlim: Optional[Tuple[float, float]] = None,
         ylim: Optional[Tuple[float, float]] = None,
         xscale: str = 'linear',
         yscale: str = 'linear',
         background: str = 'white',
         grid: bool = True,
         legend: bool = True,
         **kwargs) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a line plot with your scientific style.

    Args:
        x, y: Data arrays
        labels: Labels for each data series
        colors: Colors for each data series
        linewidths: Line widths (single value or list)
        linestyles: Line styles ('-', '--', '-.', ':')
        markers: Marker styles ('o', 's', '^', etc.)
        figsize: Figure size
        title: Plot title
        xlabel, ylabel: Axis labels
        xlim, ylim: Axis limits
        xscale, yscale: Axis scales ('linear' or 'log')
        background: Background color
        grid: Show grid
        legend: Show legend
        **kwargs: Additional arguments passed to plot

    Returns:
        (figure, axes) tuple
    """
    # Convert to numpy arrays
    x = np.asarray(x)
    y = np.asarray(y)

    # Handle multiple data series
    if x.ndim > 1 or y.ndim > 1:
        series_count = max(x.shape[0] if x.ndim > 1 else 1,
                           y.shape[0] if y.ndim > 1 else 1)
    else:
        series_count = 1

    figure, axes = _setup_figure(figsize, background, grid)
    colors = _get_colors(series_count, colors)

    # Set defaults
    if linewidths is None:
        linewidths = [2.0] * series_count
    elif isinstance(linewidths, (int, float)):
        linewidths = [linewidths] * series_count

    if linestyles is None:
        linestyles = ['-'] * series_count
    elif isinstance(linestyles, str):
        linestyles = [linestyles] * series_count

    if markers is None:
        markers = [''] * series_count
    elif isinstance(markers, str):
        markers = [markers] * series_count

    # Plot data
    if series_count == 1:
        axes.plot(x, y, color=colors[0], linewidth=linewidths[0],
                  linestyle=linestyles[0], marker=markers[0], **kwargs)
    else:
        for series_index in range(series_count):
            series_x = x[series_index] if x.ndim > 1 else x
            series_y = y[series_index] if y.ndim > 1 else y
            series_label = labels[series_index] if labels and series_index < len(labels) else f'Series {series_index+1}'
            axes.plot(series_x, series_y, color=colors[series_index], linewidth=linewidths[series_index],
                      linestyle=linestyles[series_index], marker=markers[series_index], label=series_label, **kwargs)

    # Style axes
    _style_axes(axes, title, xlabel, ylabel, xlim, ylim, xscale, yscale)

    # Add legend if multiple series
    if legend and series_count > 1 and labels:
        axes.legend(fontsize=FONT_SIZES['medium'])

    return figure, axes

def bar(x: Union[np.ndarray, List],
        heights: Union[np.ndarray, List],
        labels: Optional[List[str]] = None,
        colors: Optional[List[str]] = None,
        width: float = 0.8,
        figsize: Tuple[float, float] = (10, 6),
        title: Optional[str] = None,
        xlabel: Optional[str] = None,
        ylabel: Optional[str] = None,
        xlim: Optional[Tuple[float, float]] = None,
        ylim: Optional[Tuple[float, float]] = None,
        xscale: str = 'linear',
        yscale: str = 'linear',
        background: str = 'white',
        grid: bool = True,
        **kwargs) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a bar plot with your scientific style.

    Args:
        x: X positions or labels
        heights: Bar heights
        labels: Labels for each bar (if x is positions)
        colors: Colors for each bar
        width: Bar width
        figsize: Figure size
        title: Plot title
        xlabel, ylabel: Axis labels
        xlim, ylim: Axis limits
        xscale, yscale: Axis scales
        background: Background color
        grid: Show grid
        **kwargs: Additional arguments passed to bar

    Returns:
        (figure, axes) tuple
    """
    x = np.asarray(x)
    heights = np.asarray(heights)

    figure, axes = _setup_figure(figsize, background, grid)
    colors = _get_colors(len(heights), colors)

    # Plot bars
    axes.bar(x, heights, width=width, color=colors, **kwargs)

    # Style axes
    _style_axes(axes, title, xlabel, ylabel, xlim, ylim, xscale, yscale)

    return figure, axes

def hist(data: Union[np.ndarray, List],
         bins: int = 30,
         color: str = DEFAULT_COLORS[0],
         alpha: float = 0.7,
         figsize: Tuple[float, float] = (10, 6),
         title: Optional[str] = None,
         xlabel: Optional[str] = None,
         ylabel: Optional[str] = None,
         xlim: Optional[Tuple[float, float]] = None,
         ylim: Optional[Tuple[float, float]] = None,
         xscale: str = 'linear',
         yscale: str = 'linear',
         background: str = 'white',
         grid: bool = True,
         **kwargs) -> Tuple[plt.Figure, plt.Axes]:
    """
    Create a histogram with your scientific style.

    Args:
        data: Data to histogram
        bins: Number of bins
        color: Bar color
        alpha: Transparency
        figsize: Figure size
        title: Plot title
        xlabel, ylabel: Axis labels
        xlim, ylim: Axis limits
        xscale, yscale: Axis scales
        background: Background color
        grid: Show grid
        **kwargs: Additional arguments passed to hist

    Returns:
        (figure, axes) tuple
    """
    data = np.asarray(data)

    figure, axes = _setup_figure(figsize, background, grid)

    # Plot histogram
    axes.hist(data, bins=bins, color=color, alpha=alpha, **kwargs)

    # Style axes
    _style_axes(axes, title, xlabel, ylabel, xlim, ylim, xscale, yscale)

    return figure, axes

def save_fig(fig: plt.Figure,
             filename: str,
             format: str = 'svg',
             dpi: int = 300,
             bbox_inches: str = 'tight',
             pad_inches: float = 0.1) -> None:
    """
    Save figure with high quality settings.

    Args:
        fig: Matplotlib figure
        filename: Output filename
        format: File format ('svg', 'png', 'pdf', 'eps')
        dpi: Resolution for raster formats
        bbox_inches: Bounding box setting
        pad_inches: Padding in inches
    """
    fig.savefig(filename, format=format, dpi=dpi,
               bbox_inches=bbox_inches, pad_inches=pad_inches,
               facecolor='white')

def quick_plot(x: Union[np.ndarray, List],
               y: Union[np.ndarray, List],
               plot_type: str = 'line',
               title: Optional[str] = None,
               xlabel: Optional[str] = None,
               ylabel: Optional[str] = None,
               save: Optional[str] = None,
               **kwargs) -> Tuple[plt.Figure, plt.Axes]:
    """
    Quick plotting function - just give it data and it creates a styled plot.

    Args:
        x, y: Data arrays
        plot_type: 'line', 'scatter', 'bar', 'hist'
        title: Plot title
        xlabel, ylabel: Axis labels
        save: Filename to save (default: 'plot.svg')
        **kwargs: Additional arguments passed to the plot function

    Returns:
        (figure, axes) tuple
    """
    if plot_type == 'line':
        figure, axes = line(x, y, title=title, xlabel=xlabel, ylabel=ylabel, **kwargs)
    elif plot_type == 'scatter':
        figure, axes = scatter(x, y, title=title, xlabel=xlabel, ylabel=ylabel, **kwargs)
    elif plot_type == 'bar':
        figure, axes = bar(x, y, title=title, xlabel=xlabel, ylabel=ylabel, **kwargs)
    elif plot_type == 'hist':
        figure, axes = hist(y, title=title, xlabel=xlabel, ylabel=ylabel, **kwargs)
    else:
        raise ValueError(f"Unknown plot_type: {plot_type}")

    if save:
        save_fig(figure, save)

    return figure, axes

# Convenience function for the most common use case
def plot(*args, **kwargs) -> Tuple[plt.Figure, plt.Axes]:
    """
    Universal plotting function. Automatically detects data and creates appropriate plot.

    Usage:
        plot(x, y)                    # Line plot
        plot(x, y, 'scatter')         # Scatter plot
        plot(x, y, 'bar')             # Bar plot
        plot(data, 'hist')            # Histogram
    """
    if len(args) == 2:
        x_data, y_data = args
        return quick_plot(x_data, y_data, **kwargs)
    elif len(args) == 3:
        x_data, y_data, plot_type = args
        return quick_plot(x_data, y_data, plot_type=plot_type, **kwargs)
    else:
        raise ValueError("plot() expects 2 or 3 arguments")

# Export the most commonly used functions
__all__ = ['plot', 'scatter', 'line', 'bar', 'hist', 'save_fig', 'quick_plot']
