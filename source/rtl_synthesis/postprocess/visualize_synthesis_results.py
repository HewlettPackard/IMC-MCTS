#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Synthesis Results Visualization

Creates comprehensive visualizations of the DC synthesis results
for the IMC-MCTS accelerator components.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# Set style for publication-quality plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

def load_synthesis_data():
    """Load the synthesis area and power data"""
    synthesis_results_dir = Path(__file__).resolve().parent.parent / "synthesis_results"

    # Load area data
    area_df = pd.read_csv(synthesis_results_dir / "DC_synthesis_area.txt")

    # Load power data
    power_df = pd.read_csv(synthesis_results_dir / "DC_synthesis_power.txt")

    return area_df, power_df

def create_scaling_plots(area_df, power_df):
    """Create scaling analysis plots"""

    # Board sizes
    board_sizes = [4, 9, 25, 81, 169, 361]  # 2x2, 3x3, 5x5, 9x9, 13x13, 19x19
    board_labels = ['2×2', '3×3', '5×5', '9×9', '13×13', '19×19']

    # Extract data for each component
    component_names_unique = area_df['Component Name'].unique()
    component_categories = area_df['Category'].unique()

    # Create figure with subplots
    figure, axes = plt.subplots(2, 3, figsize=(18, 12))
    figure.suptitle('IMC-MCTS Accelerator - Synthesis Scaling Analysis', fontsize=16, fontweight='bold')

    # 1. Total Area Scaling
    ax1 = axes[0, 0]
    total_area = area_df[['2x2 (4 squares)', '3x3 (9 squares)', '5x5 (25 squares)',
                         '9x9 (81 squares)', '13x13 (169 squares)', '19x19 (361 squares)']].sum()
    ax1.loglog(board_sizes, total_area.values, 'o-', linewidth=2, markersize=8, color='#2E86AB')
    ax1.set_xlabel('Board Size (positions)')
    ax1.set_ylabel('Total Area (μm²)')
    ax1.set_title('Total Area Scaling')
    ax1.grid(True, alpha=0.3)
    ax1.set_xticks(board_sizes)
    ax1.set_xticklabels(board_labels)

    # 2. Total Power Scaling
    ax2 = axes[0, 1]
    total_power = power_df[['2x2 (4 squares)', '3x3 (9 squares)', '5x5 (25 squares)',
                           '9x9 (81 squares)', '13x13 (169 squares)', '19x19 (361 squares)']].sum()
    ax2.loglog(board_sizes, total_power.values, 'o-', linewidth=2, markersize=8, color='#A23B72')
    ax2.set_xlabel('Board Size (positions)')
    ax2.set_ylabel('Total Power (mW)')
    ax2.set_title('Total Power Scaling')
    ax2.grid(True, alpha=0.3)
    ax2.set_xticks(board_sizes)
    ax2.set_xticklabels(board_labels)

    # 3. Area per Position
    ax3 = axes[0, 2]
    area_per_pos = total_area.values / np.array(board_sizes)
    ax3.semilogy(board_labels, area_per_pos, 'o-', linewidth=2, markersize=8, color='#F18F01')
    ax3.set_xlabel('Board Size')
    ax3.set_ylabel('Area per Position (μm²/pos)')
    ax3.set_title('Area Efficiency')
    ax3.grid(True, alpha=0.3)
    ax3.tick_params(axis='x', rotation=45)

    # 4. Power per Position
    ax4 = axes[1, 0]
    power_per_pos = total_power.values / np.array(board_sizes)
    ax4.semilogy(board_labels, power_per_pos, 'o-', linewidth=2, markersize=8, color='#C73E1D')
    ax4.set_xlabel('Board Size')
    ax4.set_ylabel('Power per Position (mW/pos)')
    ax4.set_title('Power Efficiency')
    ax4.grid(True, alpha=0.3)
    ax4.tick_params(axis='x', rotation=45)

    # 5. Component Area Breakdown (19x19)
    ax5 = axes[1, 1]
    area_19x19 = area_df['19x19 (361 squares)'].values
    component_names = area_df['Component Name'].values
    colors = plt.cm.Set3(np.linspace(0, 1, len(component_names)))

    component_bars = ax5.bar(range(len(component_names)), area_19x19, color=colors)
    ax5.set_xlabel('Components')
    ax5.set_ylabel('Area (μm²)')
    ax5.set_title('Component Area Breakdown (19×19)')
    ax5.set_xticks(range(len(component_names)))
    ax5.set_xticklabels(component_names, rotation=45, ha='right')
    ax5.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for component_bar, component_value in zip(component_bars, area_19x19):
        bar_height = component_bar.get_height()
        ax5.text(component_bar.get_x() + component_bar.get_width()/2., bar_height + bar_height*0.01,
                f'{component_value:.0f}', ha='center', va='bottom', fontsize=8)

    # 6. Component Power Breakdown (19x19)
    ax6 = axes[1, 2]
    power_19x19 = power_df['19x19 (361 squares)'].values

    component_bars = ax6.bar(range(len(component_names)), power_19x19, color=colors)
    ax6.set_xlabel('Components')
    ax6.set_ylabel('Power (mW)')
    ax6.set_title('Component Power Breakdown (19×19)')
    ax6.set_xticks(range(len(component_names)))
    ax6.set_xticklabels(component_names, rotation=45, ha='right')
    ax6.grid(True, alpha=0.3, axis='y')

    # Add value labels on bars
    for component_bar, component_value in zip(component_bars, power_19x19):
        bar_height = component_bar.get_height()
        ax6.text(component_bar.get_x() + component_bar.get_width()/2., bar_height + bar_height*0.01,
                f'{component_value:.2f}', ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig('synthesis_scaling_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_category_analysis(area_df, power_df):
    """Create category-wise analysis plots"""

    # Board sizes
    board_sizes = [4, 9, 25, 81, 169, 361]
    board_labels = ['2×2', '3×3', '5×5', '9×9', '13×13', '19×19']

    # Group by category
    area_by_category = area_df.groupby('Category')[['2x2 (4 squares)', '3x3 (9 squares)',
                                                   '5x5 (25 squares)', '9x9 (81 squares)',
                                                   '13x13 (169 squares)', '19x19 (361 squares)']].sum()

    power_by_category = power_df.groupby('Category')[['2x2 (4 squares)', '3x3 (9 squares)',
                                                     '5x5 (25 squares)', '9x9 (81 squares)',
                                                     '13x13 (169 squares)', '19x19 (361 squares)']].sum()

    # Create figure
    figure, axes = plt.subplots(2, 2, figsize=(16, 12))
    figure.suptitle('IMC-MCTS Accelerator - Category Analysis', fontsize=16, fontweight='bold')

    # 1. Area by Category (Stacked)
    ax1 = axes[0, 0]
    area_by_category.T.plot(kind='bar', stacked=True, ax=ax1, width=0.8)
    ax1.set_xlabel('Board Size')
    ax1.set_ylabel('Area (μm²)')
    ax1.set_title('Area by MCTS Category (Stacked)')
    ax1.set_xticklabels(board_labels, rotation=45)
    ax1.legend(title='Category', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(True, alpha=0.3, axis='y')

    # 2. Power by Category (Stacked)
    ax2 = axes[0, 1]
    power_by_category.T.plot(kind='bar', stacked=True, ax=ax2, width=0.8)
    ax2.set_xlabel('Board Size')
    ax2.set_ylabel('Power (mW)')
    ax2.set_title('Power by MCTS Category (Stacked)')
    ax2.set_xticklabels(board_labels, rotation=45)
    ax2.legend(title='Category', bbox_to_anchor=(1.05, 1), loc='upper left')
    ax2.grid(True, alpha=0.3, axis='y')

    # 3. Area by Category (Line plot)
    ax3 = axes[1, 0]
    for category in area_by_category.index:
        ax3.loglog(board_sizes, area_by_category.loc[category].values,
                  'o-', label=category, linewidth=2, markersize=6)
    ax3.set_xlabel('Board Size (positions)')
    ax3.set_ylabel('Area (μm²)')
    ax3.set_title('Area Scaling by Category (Log-Log)')
    ax3.set_xticks(board_sizes)
    ax3.set_xticklabels(board_labels)
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. Power by Category (Line plot)
    ax4 = axes[1, 1]
    for category in power_by_category.index:
        ax4.loglog(board_sizes, power_by_category.loc[category].values,
                  'o-', label=category, linewidth=2, markersize=6)
    ax4.set_xlabel('Board Size (positions)')
    ax4.set_ylabel('Power (mW)')
    ax4.set_title('Power Scaling by Category (Log-Log)')
    ax4.set_xticks(board_sizes)
    ax4.set_xticklabels(board_labels)
    ax4.legend()
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('synthesis_category_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_efficiency_analysis(area_df, power_df):
    """Create efficiency analysis plots"""

    board_sizes = [4, 9, 25, 81, 169, 361]
    board_labels = ['2×2', '3×3', '5×5', '9×9', '13×13', '19×19']

    # Calculate total area and power
    total_area = area_df[['2x2 (4 squares)', '3x3 (9 squares)', '5x5 (25 squares)',
                         '9x9 (81 squares)', '13x13 (169 squares)', '19x19 (361 squares)']].sum()
    total_power = power_df[['2x2 (4 squares)', '3x3 (9 squares)', '5x5 (25 squares)',
                           '9x9 (81 squares)', '13x13 (169 squares)', '19x19 (361 squares)']].sum()

    # Calculate efficiency metrics
    area_per_pos = total_area.values / np.array(board_sizes)
    power_per_pos = total_power.values / np.array(board_sizes)
    energy_per_pos = (total_power.values * 1000) / np.array(board_sizes)  # nJ per position

    # Create figure
    figure, axes = plt.subplots(2, 2, figsize=(16, 12))
    figure.suptitle('IMC-MCTS Accelerator - Efficiency Analysis', fontsize=16, fontweight='bold')

    # 1. Area per Position
    ax1 = axes[0, 0]
    ax1.semilogy(board_labels, area_per_pos, 'o-', linewidth=3, markersize=10, color='#2E86AB')
    ax1.set_xlabel('Board Size')
    ax1.set_ylabel('Area per Position (μm²/pos)')
    ax1.set_title('Area Efficiency vs Board Size')
    ax1.grid(True, alpha=0.3)
    ax1.tick_params(axis='x', rotation=45)

    # Add trend line
    trend_coefficients = np.polyfit(range(len(board_sizes)), np.log10(area_per_pos), 1)
    trend_polynomial = np.poly1d(trend_coefficients)
    ax1.plot(board_labels, 10**trend_polynomial(range(len(board_sizes))), '--', alpha=0.7, color='red', linewidth=2)

    # 2. Power per Position
    ax2 = axes[0, 1]
    ax2.semilogy(board_labels, power_per_pos, 'o-', linewidth=3, markersize=10, color='#A23B72')
    ax2.set_xlabel('Board Size')
    ax2.set_ylabel('Power per Position (mW/pos)')
    ax2.set_title('Power Efficiency vs Board Size')
    ax2.grid(True, alpha=0.3)
    ax2.tick_params(axis='x', rotation=45)

    # Add trend line
    trend_coefficients = np.polyfit(range(len(board_sizes)), np.log10(power_per_pos), 1)
    trend_polynomial = np.poly1d(trend_coefficients)
    ax2.plot(board_labels, 10**trend_polynomial(range(len(board_sizes))), '--', alpha=0.7, color='red', linewidth=2)

    # 3. Energy per Position
    ax3 = axes[1, 0]
    ax3.semilogy(board_labels, energy_per_pos, 'o-', linewidth=3, markersize=10, color='#F18F01')
    ax3.set_xlabel('Board Size')
    ax3.set_ylabel('Energy per Position (nJ/pos)')
    ax3.set_title('Energy Efficiency vs Board Size')
    ax3.grid(True, alpha=0.3)
    ax3.tick_params(axis='x', rotation=45)

    # Add trend line
    trend_coefficients = np.polyfit(range(len(board_sizes)), np.log10(energy_per_pos), 1)
    trend_polynomial = np.poly1d(trend_coefficients)
    ax3.plot(board_labels, 10**trend_polynomial(range(len(board_sizes))), '--', alpha=0.7, color='red', linewidth=2)

    # 4. Area vs Power Correlation
    ax4 = axes[1, 1]
    area_power_scatter = ax4.scatter(total_area.values, total_power.values,
                                     c=board_sizes, s=200, alpha=0.7, cmap='viridis')
    ax4.set_xlabel('Total Area (μm²)')
    ax4.set_ylabel('Total Power (mW)')
    ax4.set_title('Area vs Power Correlation')
    ax4.grid(True, alpha=0.3)

    # Add colorbar
    board_size_colorbar = plt.colorbar(area_power_scatter, ax=ax4)
    board_size_colorbar.set_label('Board Size (positions)')

    # Add correlation coefficient
    correlation = np.corrcoef(total_area.values, total_power.values)[0, 1]
    ax4.text(0.05, 0.95, f'R² = {correlation**2:.3f}',
             transform=ax4.transAxes, fontsize=12,
             bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    plt.savefig('synthesis_efficiency_analysis.png', dpi=300, bbox_inches='tight')
    plt.show()

def create_component_ranking(area_df, power_df):
    """Create component ranking and analysis"""

    # Get 19x19 data
    area_19x19 = area_df[['Component Name', 'Category', '19x19 (361 squares)']].copy()
    power_19x19 = power_df[['Component Name', 'Category', '19x19 (361 squares)']].copy()

    # Sort by area
    area_19x19 = area_19x19.sort_values('19x19 (361 squares)', ascending=False)

    # Sort by power
    power_19x19 = power_19x19.sort_values('19x19 (361 squares)', ascending=False)

    # Create figure
    figure, axes = plt.subplots(2, 2, figsize=(16, 12))
    figure.suptitle('IMC-MCTS Accelerator - Component Ranking (19×19)', fontsize=16, fontweight='bold')

    # 1. Top 10 Components by Area
    ax1 = axes[0, 0]
    top10_area = area_19x19.head(10)
    area_bars = ax1.barh(range(len(top10_area)), top10_area['19x19 (361 squares)'],
                         color=plt.cm.viridis(np.linspace(0, 1, len(top10_area))))
    ax1.set_yticks(range(len(top10_area)))
    ax1.set_yticklabels(top10_area['Component Name'])
    ax1.set_xlabel('Area (μm²)')
    ax1.set_title('Top 10 Components by Area')
    ax1.grid(True, alpha=0.3, axis='x')

    # Add value labels
    for component_index, (component_bar, component_value) in enumerate(zip(area_bars, top10_area['19x19 (361 squares)'])):
        ax1.text(component_value + component_value*0.01, component_index, f'{component_value:.0f}', va='center', ha='left', fontsize=9)

    # 2. Top 10 Components by Power
    ax2 = axes[0, 1]
    top10_power = power_19x19.head(10)
    power_bars = ax2.barh(range(len(top10_power)), top10_power['19x19 (361 squares)'],
                          color=plt.cm.plasma(np.linspace(0, 1, len(top10_power))))
    ax2.set_yticks(range(len(top10_power)))
    ax2.set_yticklabels(top10_power['Component Name'])
    ax2.set_xlabel('Power (mW)')
    ax2.set_title('Top 10 Components by Power')
    ax2.grid(True, alpha=0.3, axis='x')

    # Add value labels
    for component_index, (component_bar, component_value) in enumerate(zip(power_bars, top10_power['19x19 (361 squares)'])):
        ax2.text(component_value + component_value*0.01, component_index, f'{component_value:.2f}', va='center', ha='left', fontsize=9)

    # 3. Area by Category (Pie chart)
    ax3 = axes[1, 0]
    area_by_category = area_19x19.groupby('Category')['19x19 (361 squares)'].sum()
    category_colors = plt.cm.Set3(np.linspace(0, 1, len(area_by_category)))
    pie_wedges, pie_labels, pie_percentages = ax3.pie(area_by_category.values, labels=area_by_category.index,
                                                      autopct='%1.1f%%', colors=category_colors, startangle=90)
    ax3.set_title('Area Distribution by Category')

    # 4. Power by Category (Pie chart)
    ax4 = axes[1, 1]
    power_by_category = power_19x19.groupby('Category')['19x19 (361 squares)'].sum()
    category_colors = plt.cm.Set2(np.linspace(0, 1, len(power_by_category)))
    pie_wedges, pie_labels, pie_percentages = ax4.pie(power_by_category.values, labels=power_by_category.index,
                                                      autopct='%1.1f%%', colors=category_colors, startangle=90)
    ax4.set_title('Power Distribution by Category')

    plt.tight_layout()
    plt.savefig('synthesis_component_ranking.png', dpi=300, bbox_inches='tight')
    plt.show()

def main():
    """Main function to generate all visualizations"""
    print("=" * 60)
    print("IMC-MCTS Accelerator - Synthesis Results Visualization")
    print("=" * 60)
    print()

    # Load data
    print("Loading synthesis data...")
    area_df, power_df = load_synthesis_data()
    print(f"Loaded {len(area_df)} components with area data")
    print(f"Loaded {len(power_df)} components with power data")
    print()

    # Create visualizations
    print("Creating scaling analysis plots...")
    create_scaling_plots(area_df, power_df)

    print("Creating category analysis plots...")
    create_category_analysis(area_df, power_df)

    print("Creating efficiency analysis plots...")
    create_efficiency_analysis(area_df, power_df)

    print("Creating component ranking plots...")
    create_component_ranking(area_df, power_df)

    print()
    print("=" * 60)
    print("Visualization complete!")
    print("Generated plots:")
    print("  - synthesis_scaling_analysis.png")
    print("  - synthesis_category_analysis.png")
    print("  - synthesis_efficiency_analysis.png")
    print("  - synthesis_component_ranking.png")
    print("=" * 60)

if __name__ == "__main__":
    main()
