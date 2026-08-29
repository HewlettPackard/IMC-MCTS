#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Tournament Results Visualization

Generates publication-quality plots from tournament results:
1. ELO vs Accuracy scatter plot
2. Win Rate Heatmap (4x4 matrix)
3. Score Distribution Analysis
"""

import json
import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Use one consistent visual style for every tournament figure.
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")


def load_results(results_file: str) -> dict:
    """Load tournament results from JSON."""
    with open(results_file, 'r') as results_handle:
        return json.load(results_handle)


def plot_elo_vs_accuracy(results: dict, output_dir: str):
    """
    Plot ELO rating vs Crossbar Accuracy.

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

    figure, axes = plt.subplots(figsize=(10, 6))

    axes.scatter(accuracies, elos, s=200, alpha=0.6,
                 edgecolors='black', linewidth=2)

    # Label every measured configuration directly.
    for config_index, name in enumerate(names):
        axes.annotate(name, (accuracies[config_index], elos[config_index]),
                      xytext=(5, 5), textcoords='offset points',
                      fontsize=10, fontweight='bold')

    # Fit ELO = slope * accuracy + intercept.
    z = np.polyfit(accuracies, elos, 1)
    p = np.poly1d(z)
    x_trend = np.linspace(min(accuracies), max(accuracies), 100)
    axes.plot(x_trend, p(x_trend), "r--", alpha=0.8, linewidth=2,
              label=f'Trend: y={z[0]:.1f}x+{z[1]:.1f}')

    # Report the Pearson correlation in the figure title.
    corr = np.corrcoef(accuracies, elos)[0, 1]

    axes.set_xlabel('Crossbar Neural Network Accuracy (%)', fontsize=14, fontweight='bold')
    axes.set_ylabel('MCTS Playing Strength (ELO Rating)', fontsize=14, fontweight='bold')
    axes.set_title('Crossbar Accuracy vs MCTS Playing Strength\n' +
                   f'Correlation: r={corr:.3f}', fontsize=16, fontweight='bold')
    axes.legend(fontsize=12)
    axes.grid(True, alpha=0.3)

    # Save raster and vector copies of the same figure.
    output_file = os.path.join(output_dir, 'elo_vs_accuracy.png')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_file}")

    # Also save PDF for paper
    plt.savefig(output_file.replace('.png', '.pdf'), bbox_inches='tight')
    print(f"Saved: {output_file.replace('.png', '.pdf')}")

    plt.close()


def plot_winrate_matrix(results: dict, output_dir: str):
    """
    Plot win rate heatmap showing head-to-head matchups.
    """
    configs = results['configurations']
    matchup_results = results['matchup_results']

    n = len(configs)
    config_names = [c['name'] for c in configs]

    # Build the row-player versus column-player win-rate matrix.
    win_matrix = np.zeros((n, n))

    for i, config1 in enumerate(configs):
        for j, config2 in enumerate(configs):
            if i == j:
                win_matrix[i, j] = 0.5  # Diagonal (no self-play)
                continue

            # Tournament results may store either matchup ordering.
            key1 = f"{config1['name']}_vs_{config2['name']}"
            key2 = f"{config2['name']}_vs_{config1['name']}"

            if key1 in matchup_results:
                data = matchup_results[key1]
                total_games = data['config1_wins'] + data['config2_wins'] + data['draws']
                win_rate = (data['config1_wins'] + 0.5 * data['draws']) / total_games
                win_matrix[i, j] = win_rate
            elif key2 in matchup_results:
                data = matchup_results[key2]
                total_games = data['config1_wins'] + data['config2_wins'] + data['draws']
                # Reverse the stored matchup into config1's perspective.
                win_rate = (data['config2_wins'] + 0.5 * data['draws']) / total_games
                win_matrix[i, j] = win_rate

    figure, axes = plt.subplots(figsize=(10, 8))

    sns.heatmap(win_matrix, annot=True, fmt='.2f', cmap='RdYlGn',
                vmin=0, vmax=1, center=0.5,
                xticklabels=[name.replace(' Accuracy', '') for name in config_names],
                yticklabels=[name.replace(' Accuracy', '') for name in config_names],
                cbar_kws={'label': 'Win Rate'},
                linewidths=0.5, linecolor='black',
                ax=axes)

    axes.set_title('Head-to-Head Win Rate Matrix\n(Row player vs Column player)',
                   fontsize=16, fontweight='bold')
    axes.set_xlabel('Opponent (White)', fontsize=14, fontweight='bold')
    axes.set_ylabel('Player (Black)', fontsize=14, fontweight='bold')

    # Save raster and vector copies of the same heatmap.
    output_file = os.path.join(output_dir, 'winrate_matrix.png')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_file}")

    plt.savefig(output_file.replace('.png', '.pdf'), bbox_inches='tight')
    print(f"Saved: {output_file.replace('.png', '.pdf')}")

    plt.close()


def plot_score_distribution(results: dict, output_dir: str):
    """
    Plot distribution of final scores to show game diversity.
    """
    all_games = results['all_games']

    # Group signed final scores by game outcome.
    black_wins = [g['final_score'] for g in all_games if g['winner'] == 'Black']
    white_wins = [-g['final_score'] for g in all_games if g['winner'] == 'White']  # Flip for symmetry
    draws = [g['final_score'] for g in all_games if g['winner'] == 'Draw']

    figure, axes = plt.subplots(figsize=(12, 6))

    # Plot all outcomes over one shared score axis.
    bins = np.linspace(-10, 10, 40)
    axes.hist(white_wins, bins=bins, alpha=0.6, label='White Wins', color='lightcoral')
    axes.hist(draws, bins=bins, alpha=0.6, label='Draws', color='gold')
    axes.hist(black_wins, bins=bins, alpha=0.6, label='Black Wins', color='lightblue')

    # Mark the white-win, draw, and black-win score boundaries.
    axes.axvline(-1.5, color='red', linestyle='--', linewidth=2, alpha=0.7, label='White Win Threshold')
    axes.axvline(1.5, color='blue', linestyle='--', linewidth=2, alpha=0.7, label='Black Win Threshold')
    axes.axvline(0, color='gray', linestyle='-', linewidth=1, alpha=0.5)

    axes.set_xlabel('Final Score (Material + 0.5×Territory + 0.1×Liberties)', fontsize=12, fontweight='bold')
    axes.set_ylabel('Number of Games', fontsize=12, fontweight='bold')
    axes.set_title('Distribution of Final Game Scores', fontsize=16, fontweight='bold')
    axes.legend(fontsize=11)
    axes.grid(True, alpha=0.3)

    # Save raster and vector copies of the same histogram.
    output_file = os.path.join(output_dir, 'score_distribution.png')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_file}")

    plt.savefig(output_file.replace('.png', '.pdf'), bbox_inches='tight')
    print(f"Saved: {output_file.replace('.png', '.pdf')}")

    plt.close()


def plot_elo_evolution(results: dict, output_dir: str):
    """
    Plot ELO rating evolution over the tournament.
    """
    elo_data = results['elo_ratings']['rankings']

    figure, axes = plt.subplots(figsize=(12, 6))

    for player in elo_data:
        name = player['player_id']
        history = player['rating_history']

        games = [h[0] for h in history]
        ratings = [h[1] for h in history]

        axes.plot(games, ratings, marker='o', linewidth=2, label=name, markersize=3)

    axes.set_xlabel('Games Played', fontsize=12, fontweight='bold')
    axes.set_ylabel('ELO Rating', fontsize=12, fontweight='bold')
    axes.set_title('ELO Rating Evolution Throughout Tournament', fontsize=16, fontweight='bold')
    axes.legend(fontsize=11)
    axes.grid(True, alpha=0.3)
    axes.axhline(1500, color='gray', linestyle='--', alpha=0.5, label='Starting Rating')

    # Save raster and vector copies of the same ELO history.
    output_file = os.path.join(output_dir, 'elo_evolution.png')
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Saved: {output_file}")

    plt.savefig(output_file.replace('.png', '.pdf'), bbox_inches='tight')
    print(f"Saved: {output_file.replace('.png', '.pdf')}")

    plt.close()


def generate_summary_stats(results: dict, output_dir: str):
    """Generate text summary of key statistics."""

    summary_file = os.path.join(output_dir, 'tournament_summary.txt')

    with open(summary_file, 'w') as summary_handle:
        summary_handle.write("="*80 + "\n")
        summary_handle.write("TOURNAMENT SUMMARY STATISTICS\n")
        summary_handle.write("="*80 + "\n\n")

        # Configuration
        config = results['configuration']
        summary_handle.write(f"Board Size: {config['board_size']}x{config['board_size']}\n")
        summary_handle.write(f"Games per Matchup: {config['games_per_matchup']}\n")
        summary_handle.write(f"Total Games: {config['total_games']}\n")
        summary_handle.write(f"Iterations per Move: {config['iterations_per_move']}\n")
        summary_handle.write(f"Max Moves: {config['max_moves']}\n\n")

        # ELO Rankings
        summary_handle.write("FINAL ELO RANKINGS\n")
        summary_handle.write("-"*80 + "\n")

        elo_data = results['elo_ratings']['rankings']
        for rank, player in enumerate(elo_data, 1):
            summary_handle.write(f"{rank}. {player['player_id']:<30} "
                                 f"Rating: {player['rating']:.1f}  "
                                 f"W/L/D: {player['wins']}/{player['losses']}/{player['draws']}  "
                                 f"Win%: {player['win_rate']*100:.1f}%\n")

        summary_handle.write("\n")

        # Accuracy vs ELO correlation
        configs = results['configurations']
        accuracies = [c['accuracy'] for c in configs]
        elos = [p['rating'] for p in elo_data]

        corr = np.corrcoef(accuracies, elos)[0, 1]
        summary_handle.write(f"Accuracy-ELO Correlation: r = {corr:.3f}\n\n")

        # ELO per accuracy point
        z = np.polyfit([a*100 for a in accuracies], elos, 1)
        summary_handle.write(f"Linear Fit: ELO = {z[0]:.2f} × Accuracy(%) + {z[1]:.2f}\n")
        summary_handle.write(f"ELO gain per 10% accuracy: ~{z[0]*10:.1f} points\n\n")

        # Game outcome distribution
        all_games = results['all_games']
        black_wins = sum(1 for g in all_games if g['winner'] == 'Black')
        white_wins = sum(1 for g in all_games if g['winner'] == 'White')
        draws = sum(1 for g in all_games if g['winner'] == 'Draw')

        summary_handle.write("GAME OUTCOMES\n")
        summary_handle.write("-"*80 + "\n")
        summary_handle.write(f"Black Wins: {black_wins} ({black_wins/len(all_games)*100:.1f}%)\n")
        summary_handle.write(f"White Wins: {white_wins} ({white_wins/len(all_games)*100:.1f}%)\n")
        summary_handle.write(f"Draws: {draws} ({draws/len(all_games)*100:.1f}%)\n\n")

        # Average score components
        avg_material = np.mean([g['score_details']['material_diff'] for g in all_games])
        avg_territory = np.mean([g['score_details']['territory_diff'] for g in all_games])
        avg_liberties = np.mean([g['score_details']['liberty_diff'] for g in all_games])

        summary_handle.write("AVERAGE SCORE COMPONENTS (from Black's perspective)\n")
        summary_handle.write("-"*80 + "\n")
        summary_handle.write(f"Material: {avg_material:+.2f}\n")
        summary_handle.write(f"Territory: {avg_territory:+.2f}\n")
        summary_handle.write(f"Liberties: {avg_liberties:+.2f}\n\n")

        summary_handle.write("="*80 + "\n")

    print(f"Saved: {summary_file}")


def main():
    """Main visualization function."""
    if len(sys.argv) < 2:
        print("Usage: python plot_results.py <tournament_results.json>")
        sys.exit(1)

    results_file = sys.argv[1]

    if not os.path.exists(results_file):
        print(f"Error: File not found: {results_file}")
        sys.exit(1)

    print(f"Loading results from: {results_file}")
    results = load_results(results_file)

    # Keep all standard plots beside the tournament result file.
    output_dir = os.path.join(os.path.dirname(results_file), 'plots')
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nGenerating plots...")
    print("="*80)

    # Generate each publication artifact in a fixed order.
    plot_elo_vs_accuracy(results, output_dir)
    plot_winrate_matrix(results, output_dir)
    plot_score_distribution(results, output_dir)
    plot_elo_evolution(results, output_dir)
    generate_summary_stats(results, output_dir)

    print("="*80)
    print(f"\nAll plots saved to: {output_dir}/")
    print("\nGenerated files:")
    print("  - elo_vs_accuracy.png (and .pdf)")
    print("  - winrate_matrix.png (and .pdf)")
    print("  - score_distribution.png (and .pdf)")
    print("  - elo_evolution.png (and .pdf)")
    print("  - tournament_summary.txt")


if __name__ == "__main__":
    main()
