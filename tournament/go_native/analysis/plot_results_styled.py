#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Tournament Results Visualization with plotstyle

Generate publication-quality plots from tournament results using plotstyle formatting.
"""

import json
import sys
import os
from pathlib import Path
import numpy as np
from scipy import stats

# Load the shared publication-plotting utilities.
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "paper" / "figure"))
import plotstyle
import matplotlib.pyplot as plt


def load_results(results_file: str) -> dict:
    """Load tournament results from JSON."""
    with open(results_file, 'r') as results_handle:
        return json.load(results_handle)


def plot_elo_vs_accuracy(results: dict, output_dir: str):
    """
    Plot ELO rating vs Crossbar Accuracy using plotstyle.

    This is the main result figure showing the relationship.
    """
    # Match each crossbar accuracy to its final ELO rating.
    configs = results['configurations']
    elo_data = results['elo_ratings']['rankings']

    accuracies = []
    elos = []
    names = []

    for config in configs:
        # Find the ELO entry for this crossbar configuration.
        for player in elo_data:
            if player['player_id'] == config['name']:
                accuracies.append(config['accuracy'] * 100)  # Convert to percentage
                elos.append(player['rating'])
                names.append(config['name'])
                break

    accuracies = np.array(accuracies)
    elos = np.array(elos)

    # Fit ELO = slope * accuracy + intercept.
    correlation, p_value = stats.pearsonr(accuracies, elos)
    slope, intercept, r_value, p_val, std_err = stats.linregress(accuracies, elos)

    # Give each crossbar configuration a distinct marker.
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']

    figure, axes = plotstyle._setup_figure(figsize=(7, 4), background='white', grid=True)

    # Plot each measured configuration as one point.
    for config_index, (accuracy, elo) in enumerate(zip(accuracies, elos)):
        axes.scatter(accuracy, elo, marker=markers[config_index], s=200, color='#e57373',
                     alpha=0.7, edgecolors='black', linewidths=0.5, zorder=3)

    # Draw the fitted ELO trend over the measured accuracy range.
    x_fit = np.linspace(accuracies.min() - 2, accuracies.max() + 2, 100)
    y_fit = slope * x_fit + intercept
    axes.plot(x_fit, y_fit, '--', color='#d32f2f', linewidth=2.5, zorder=1)

    # Apply the shared paper formatting.
    plotstyle._style_axes(
        axes,
        title=None,
        xlabel='Crossbar Neural Network Accuracy (%)',
        ylabel='MCTS Playing Strength\n(ELO Rating)',
        fontsize='large'
    )

    # Place each label relative to the fitted trend line.
    for config_index, (accuracy, elo, name) in enumerate(zip(accuracies, elos, names)):
        expected_elo = slope * accuracy + intercept

        # Keep labels above high points and beside low points.
        if elo > expected_elo:
            axes.annotate(name, (accuracy, elo), textcoords="offset points",
                          xytext=(0,10), ha='center', fontsize=plotstyle.FONT_SIZES['small'], alpha=0.9)
        else:
            axes.annotate(name, (accuracy, elo), textcoords="offset points",
                          xytext=(8,5), ha='left', fontsize=plotstyle.FONT_SIZES['small'], alpha=0.9)

    # Save
    output_path = os.path.join(output_dir, 'elo_vs_accuracy.png')
    output_path_pdf = os.path.join(output_dir, 'elo_vs_accuracy.pdf')

    plt.tight_layout()
    plotstyle.save_fig(figure, output_path, format='png', dpi=300)
    plotstyle.save_fig(figure, output_path_pdf, format='pdf', dpi=300)
    plt.close()

    print(f"Saved: {output_path}")
    print(f"Saved: {output_path_pdf}")

    return correlation, slope, intercept


def plot_winrate_matrix(results: dict, output_dir: str):
    """
    Plot win rate matrix using plotstyle styling.
    """
    import seaborn as sns

    configs = results['configurations']
    matchup_results = results['matchup_results']

    n_players = len(configs)
    player_names = [c['name'] for c in configs]

    # Build the row-player versus column-player win-rate matrix.
    winrate_matrix = np.zeros((n_players, n_players))

    for i, config1 in enumerate(configs):
        for j, config2 in enumerate(configs):
            if i == j:
                winrate_matrix[i, j] = 0.5  # Diagonal
                continue

            # Tournament results may store either matchup ordering.
            key1 = f"{config1['name']}_vs_{config2['name']}"
            key2 = f"{config2['name']}_vs_{config1['name']}"

            if key1 in matchup_results:
                matchup = matchup_results[key1]
                total_games = matchup['config1_wins'] + matchup['config2_wins'] + matchup['draws']
                wins = matchup['config1_wins']
                winrate_matrix[i, j] = wins / total_games if total_games > 0 else 0.5
            elif key2 in matchup_results:
                matchup = matchup_results[key2]
                total_games = matchup['config1_wins'] + matchup['config2_wins'] + matchup['draws']
                wins = matchup['config2_wins']
                winrate_matrix[i, j] = wins / total_games if total_games > 0 else 0.5
            else:
                winrate_matrix[i, j] = 0.5

    figure, axes = plotstyle._setup_figure(figsize=(8, 7), background='white', grid=False)

    image = axes.imshow(winrate_matrix, cmap='RdYlGn', vmin=0.0, vmax=1.0, aspect='auto')

    colorbar = plt.colorbar(image, ax=axes)
    colorbar.set_label('Win Rate', fontsize=plotstyle.FONT_SIZES['large'])

    # Label both player axes in tournament order.
    axes.set_xticks(np.arange(n_players))
    axes.set_yticks(np.arange(n_players))
    axes.set_xticklabels(player_names, rotation=45, ha='right', fontsize=plotstyle.FONT_SIZES['medium'])
    axes.set_yticklabels(player_names, fontsize=plotstyle.FONT_SIZES['medium'])

    # Print the numerical win rate inside every matrix cell.
    for row_index in range(n_players):
        for column_index in range(n_players):
            text = axes.text(column_index, row_index,
                             f'{winrate_matrix[row_index, column_index]:.2f}',
                             ha="center", va="center", color="black", fontsize=8)

    plotstyle._style_axes(
        axes,
        title=None,
        xlabel='Opponent (White)',
        ylabel='Player (Black)',
        fontsize='large'
    )

    # Save
    output_path = os.path.join(output_dir, 'winrate_matrix.png')
    output_path_pdf = os.path.join(output_dir, 'winrate_matrix.pdf')

    plotstyle.save_fig(figure, output_path, format='png', dpi=300)
    plotstyle.save_fig(figure, output_path_pdf, format='pdf', dpi=300)
    plt.close()

    print(f"Saved: {output_path}")
    print(f"Saved: {output_path_pdf}")


def plot_elo_evolution(results: dict, output_dir: str):
    """
    Plot ELO rating evolution over tournament using plotstyle.
    """
    elo_data = results['elo_ratings']['rankings']

    # Reuse the scatter-plot markers for each ELO trajectory.
    markers = ['o', 's', '^', 'D', 'v', '<', '>', 'p', '*', 'h']

    figure, axes = plotstyle._setup_figure(figsize=(7, 5), background='white', grid=True)

    colors = plotstyle.DEFAULT_COLORS

    for player_index, player in enumerate(elo_data):
        history = np.array(player['rating_history'])
        games = history[:, 0]
        ratings = history[:, 1]

        color = colors[player_index % len(colors)]
        # Mark the final rating so each trajectory is visible in the legend.
        axes.plot(games, ratings, '-', linewidth=2.5, label=player['player_id'],
                  color=color, alpha=0.8, marker=markers[player_index], markevery=[len(games)-1],
                  markersize=10, markeredgecolor='black', markeredgewidth=0.5)

    # Keep the common 1500 starting rating visible as a reference.
    axes.axhline(y=1500, color='gray', linestyle='--', linewidth=1.5,
                 alpha=0.5, label='Initial Rating')

    plotstyle._style_axes(
        axes,
        title=None,
        xlabel='Games Played',
        ylabel='ELO Rating',
        fontsize='large'
    )

    # Place legend at the top, outside the plot area
    axes.legend(loc='upper center', bbox_to_anchor=(0.45, 1.35),
                fontsize=plotstyle.FONT_SIZES['medium'], framealpha=0.9, ncol=3)

    # Save with tight layout to accommodate top legend
    output_path = os.path.join(output_dir, 'elo_evolution.png')
    output_path_pdf = os.path.join(output_dir, 'elo_evolution.pdf')

    plt.tight_layout()
    plt.subplots_adjust(top=0.82)  # Make room for legend at top
    plotstyle.save_fig(figure, output_path, format='png', dpi=300)
    plotstyle.save_fig(figure, output_path_pdf, format='pdf', dpi=300)
    plt.close()

    print(f"Saved: {output_path}")
    print(f"Saved: {output_path_pdf}")


def plot_score_distribution(results: dict, output_dir: str):
    """
    Plot distribution of final game scores using plotstyle.
    """
    all_games = results['all_games']

    final_scores = [game['final_score'] for game in all_games]
    winners = [game['winner'] for game in all_games]

    # Count the three tournament outcomes.
    black_wins = sum(1 for winner in winners if winner == 'Black')
    white_wins = sum(1 for winner in winners if winner == 'White')
    draws = sum(1 for winner in winners if winner == 'Draw')

    figure, axes = plotstyle._setup_figure(figsize=(7, 4.5), background='white', grid=True)

    # Create histogram
    bins = np.linspace(-10, 10, 30)

    # Separate final scores by game outcome.
    black_scores = [score for score, winner in zip(final_scores, winners) if winner == 'Black']
    white_scores = [score for score, winner in zip(final_scores, winners) if winner == 'White']
    draw_scores = [score for score, winner in zip(final_scores, winners) if winner == 'Draw']

    axes.hist(white_scores, bins=bins, alpha=0.6, color='#ffcccc',
              label=f'White Wins ({white_wins})', edgecolor='black', linewidth=0.5)
    axes.hist(draw_scores, bins=bins, alpha=0.6, color='#ffffcc',
              label=f'Draws ({draws})', edgecolor='black', linewidth=0.5)
    axes.hist(black_scores, bins=bins, alpha=0.6, color='#ccccff',
              label=f'Black Wins ({black_wins})', edgecolor='black', linewidth=0.5)

    # Add threshold lines
    axes.axvline(x=1.5, color='blue', linestyle='--', linewidth=2,
                 label='Black Win Threshold (+1.5)', alpha=0.7)
    axes.axvline(x=-1.5, color='red', linestyle='--', linewidth=2,
                 label='White Win Threshold (-1.5)', alpha=0.7)
    axes.axvline(x=0, color='gray', linestyle='-', linewidth=1.5, alpha=0.5)

    plotstyle._style_axes(
        axes,
        title=None,
        xlabel='Final Score (Material + 0.5×Territory + 0.1×Liberties)',
        ylabel='Number of Games',
        fontsize='large'
    )

    axes.legend(loc='upper right', fontsize=plotstyle.FONT_SIZES['medium'], framealpha=0.9)

    # Save
    output_path = os.path.join(output_dir, 'score_distribution.png')
    output_path_pdf = os.path.join(output_dir, 'score_distribution.pdf')

    plotstyle.save_fig(figure, output_path, format='png', dpi=300)
    plotstyle.save_fig(figure, output_path_pdf, format='pdf', dpi=300)
    plt.close()

    print(f"Saved: {output_path}")
    print(f"Saved: {output_path_pdf}")

    return black_wins, white_wins, draws


def generate_summary(results: dict, correlation: float, slope: float,
                        intercept: float, black_wins: int, white_wins: int,
                        draws: int, output_dir: str):
    """Generate tournament summary text file."""
    configs = results['configurations']
    elo_data = results['elo_ratings']['rankings']
    config_info = results['configuration']

    summary_path = os.path.join(output_dir, 'tournament_summary.txt')

    with open(summary_path, 'w') as summary_handle:
        summary_handle.write("=" * 80 + "\n")
        summary_handle.write("TOURNAMENT SUMMARY STATISTICS (plotstyle formatted)\n")
        summary_handle.write("=" * 80 + "\n\n")

        summary_handle.write(f"Board Size: {config_info['board_size']}x{config_info['board_size']}\n")
        summary_handle.write(f"Games per Matchup: {config_info['games_per_matchup']}\n")
        summary_handle.write(f"Total Games: {config_info['total_games']}\n")
        summary_handle.write(f"Iterations per Move: {config_info['iterations_per_move']}\n")
        summary_handle.write(f"Max Moves: {config_info['max_moves']}\n\n")

        summary_handle.write("FINAL ELO RANKINGS\n")
        summary_handle.write("-" * 80 + "\n")
        for player in elo_data:
            name = player['player_id']
            rating = player['rating']
            wins = player['wins']
            losses = player['losses']
            draws_p = player['draws']
            win_rate = player['win_rate']

            summary_handle.write(f"{player['rank']}. {name:30} Rating: {rating:7.1f}  "
                                 f"W/L/D: {wins}/{losses}/{draws_p}  Win%: {win_rate*100:.1f}%\n")

        summary_handle.write(f"\nAccuracy-ELO Correlation: r = {correlation:.3f}\n\n")
        summary_handle.write(f"Linear Fit: ELO = {slope:.2f} × Accuracy(%) + {intercept:.2f}\n")
        summary_handle.write(f"ELO gain per 10% accuracy: ~{slope * 10:.1f} points\n\n")

        summary_handle.write("GAME OUTCOMES\n")
        summary_handle.write("-" * 80 + "\n")
        total = black_wins + white_wins + draws
        summary_handle.write(f"Black Wins: {black_wins} ({black_wins/total*100:.1f}%)\n")
        summary_handle.write(f"White Wins: {white_wins} ({white_wins/total*100:.1f}%)\n")
        summary_handle.write(f"Draws: {draws} ({draws/total*100:.1f}%)\n\n")

        # Calculate average score components
        all_games = results['all_games']
        avg_material = np.mean([g.get('material_diff', 0) for g in all_games])
        avg_territory = np.mean([g.get('territory_diff', 0) for g in all_games])
        avg_liberties = np.mean([g.get('liberty_diff', 0) for g in all_games])

        summary_handle.write("AVERAGE SCORE COMPONENTS (from Black's perspective)\n")
        summary_handle.write("-" * 80 + "\n")
        summary_handle.write(f"Material: {avg_material:+.2f}\n")
        summary_handle.write(f"Territory: {avg_territory:+.2f}\n")
        summary_handle.write(f"Liberties: {avg_liberties:+.2f}\n\n")

        summary_handle.write("=" * 80 + "\n")

    print(f"Saved: {summary_path}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python plot_results.py <tournament_results.json>")
        sys.exit(1)

    results_file = sys.argv[1]

    if not os.path.exists(results_file):
        print(f"Error: Results file not found: {results_file}")
        sys.exit(1)

    print(f"Loading results from: {results_file}\n")
    results = load_results(results_file)

    # Keep plotstyle artifacts beside the tournament result file.
    results_dir = os.path.dirname(results_file)
    output_dir = os.path.join(results_dir, 'plots_styled')
    os.makedirs(output_dir, exist_ok=True)

    print("Generating plots with plotstyle...")
    print("=" * 80)

    # Generate each publication artifact in a fixed order.
    correlation, slope, intercept = plot_elo_vs_accuracy(results, output_dir)
    plot_winrate_matrix(results, output_dir)
    plot_elo_evolution(results, output_dir)
    black_wins, white_wins, draws = plot_score_distribution(results, output_dir)
    generate_summary(results, correlation, slope, intercept,
                        black_wins, white_wins, draws, output_dir)

    print("=" * 80)
    print(f"\nAll plots saved to: {output_dir}/\n")
    print("Generated files:")
    print("  - elo_vs_accuracy.png (and .pdf)")
    print("  - winrate_matrix.png (and .pdf)")
    print("  - score_distribution.png (and .pdf)")
    print("  - elo_evolution.png (and .pdf)")
    print("  - tournament_summary.txt")


if __name__ == "__main__":
    main()
