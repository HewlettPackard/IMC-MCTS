#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
🎯 POSITION EVALUATION DATA GENERATOR (PROPER GO RULES)

Generates training data for position evaluation (who is winning?)
- Creates random/realistic Go positions
- Applies PROPER Go rules: captures, suicide detection, group liberties
- Evaluates them using proper Go heuristics
- Output: positions → game outcomes (-1, 0, +1)

Key differences from simplified version:
✓ Stone captures applied after each move
✓ Suicide moves prevented (unless they capture)
✓ Group connectivity tracking
✓ 4-neighbor orthogonal territory (not 8-neighbor diagonal)
✓ Compatible with KataGo and other Go engines
"""

import json
import numpy as np
import random
from datetime import datetime
from typing import List, Tuple, Dict

class PositionEvaluationDataGenerator:
    """Generate labeled Go positions with captures, liberties, and territory."""
    
    def __init__(self, board_size: int = 5):
        self.board_size = board_size
        self.board_size_sq = board_size * board_size
        
        print("🎯 POSITION EVALUATION DATA GENERATOR")
        print("=" * 50)
        print(f"📊 Task: Generate position → outcome data")
        print(f"🎯 Board size: {board_size}x{board_size}")
        print(f"⚡ Output: Board positions with game outcomes")
        print()
    
    def generate_dataset(self, num_positions: int = 50000, output_file: str = None) -> Dict:
        """Generate position evaluation dataset"""
        
        print(f"🚀 Generating {num_positions:,} position evaluations...")
        
        position_features = []
        game_outcomes = []
        position_metadata = []

        # Stage 1: sample a position family and build a legal board.
        for position_idx in range(num_positions):
            if position_idx % 1000 == 0:
                print(f"   📊 Generated {position_idx:,}/{num_positions:,} positions...")
            
            # Choose position type
            position_type = random.choice([
                'random',           # Random stone placement
                'endgame',          # Near-finished games
                'midgame',          # Partially filled boards
                'opening',          # Early game positions
                'territorial',      # Territory-focused positions
                'fighting'          # Fighting/tactical positions
            ])
            
            position, outcome, metadata = self._generate_position_by_type(position_type)

            # Stage 2: encode each cell as [Black, White].
            feature_vector = []
            flattened_position = position.flatten()
            for cell_value in flattened_position:
                if cell_value == 1:  # Black stone
                    feature_vector.extend([1.0, 0.0])
                elif cell_value == -1: # White stone
                    feature_vector.extend([0.0, 1.0])
                else: # Empty cell
                    feature_vector.extend([0.0, 0.0])
            
            # Final feature: 1.0 for P1's turn, 0.0 for P2's turn.
            p1_count = int(np.sum(position == 1))
            p2_count = int(np.sum(position == -1))
            feature_vector.append(1.0 if p1_count <= p2_count else 0.0)

            position_features.append(feature_vector)
            game_outcomes.append(float(outcome))
            position_metadata.append({
                key: float(value) if isinstance(value, (np.integer, np.floating)) else value
                for key, value in metadata.items()
            })
        
        # Stage 3: package the arrays in the trainer's JSON schema.
        dataset = {
            'positions': position_features,
            'game_outcomes': game_outcomes,
            'metadata': {
                'dataset_type': 'position_evaluation',
                'board_size': self.board_size,
                'num_positions': num_positions,
                'generation_date': datetime.now().isoformat(),
                'description': 'Go position evaluation training data',
                'label_format': 'game_outcomes: 0.0=White wins, 0.5=Draw, 1.0=Black wins',
                'feature_vector_format': '50 features (2 per cell): [Black_cell1, White_cell1, Black_cell2, White_cell2, ...]'
            },
            'position_metadata': position_metadata
        }
        
        # Stage 4: save the dataset when an output path is provided.
        if output_file:
            with open(output_file, 'w') as f:
                json.dump(dataset, f, indent=2)
            print(f"💾 Saved dataset to: {output_file}")
        
        # Stage 5: report the label balance.
        outcomes_array = np.array(game_outcomes)
        print(f"\n📊 Dataset Statistics:")
        print(f"   Total positions: {len(position_features):,}")
        print(f"   Black wins (1.0): {np.sum(outcomes_array == 1.0):,} ({np.mean(outcomes_array == 1.0):.1%})")
        print(f"   White wins (0.0): {np.sum(outcomes_array == 0.0):,} ({np.mean(outcomes_array == 0.0):.1%})")
        print(f"   Draws (0.5): {np.sum(outcomes_array == 0.5):,} ({np.mean(outcomes_array == 0.5):.1%})")
        print(f"   Average outcome: {np.mean(outcomes_array):.3f}")
        
        return dataset
    
    def _generate_position_by_type(self, position_type: str) -> Tuple[np.ndarray, int, Dict]:
        """Dispatch one explicit position family."""
        
        if position_type == 'random':
            return self._generate_random_position()
        elif position_type == 'endgame':
            return self._generate_endgame_position()
        elif position_type == 'midgame':
            return self._generate_midgame_position()
        elif position_type == 'opening':
            return self._generate_opening_position()
        elif position_type == 'territorial':
            return self._generate_territorial_position()
        elif position_type == 'fighting':
            return self._generate_fighting_position()
        else:
            return self._generate_random_position()
    
    def _generate_random_position(self) -> Tuple[np.ndarray, int, Dict]:
        """Generate completely random position with proper Go rules"""
        board = np.zeros((self.board_size, self.board_size))

        # Random number of stones (10-80% filled)
        num_stones = random.randint(self.board_size_sq // 10, int(self.board_size_sq * 0.8))

        # Place random stones with proper Go rules
        stones_placed = 0
        attempts = 0
        max_attempts = num_stones * 20  # Safety limit

        while stones_placed < num_stones and attempts < max_attempts:
            attempts += 1
            i, j = random.randint(0, self.board_size-1), random.randint(0, self.board_size-1)

            if board[i, j] == 0:
                color = random.choice([1, -1])

                # Check if move is valid (not suicide)
                if not self._is_suicide_move(board, i, j, color):
                    board[i, j] = color
                    # Apply captures
                    self._apply_go_rules(board, (i, j), color)
                    stones_placed += 1

        # Evaluate position
        outcome = self._evaluate_position(board)

        metadata = {
            'type': 'random',
            'stones_placed': int(np.sum(board != 0)),
            'fill_ratio': float(np.sum(board != 0) / self.board_size_sq)
        }

        return board, outcome, metadata
    
    def _generate_endgame_position(self) -> Tuple[np.ndarray, int, Dict]:
        """Generate endgame position (mostly filled) with proper Go rules"""
        board = np.zeros((self.board_size, self.board_size))

        # Fill 70-90% of board
        num_stones = random.randint(int(self.board_size_sq * 0.7), int(self.board_size_sq * 0.9))

        # Create territorial regions
        black_territory = random.choice([(0, 0), (self.board_size-1, self.board_size-1)])
        white_territory = (self.board_size-1, 0) if black_territory == (0, 0) else (0, self.board_size-1)

        stones_placed = 0
        attempts = 0
        max_attempts = num_stones * 20

        while stones_placed < num_stones and attempts < max_attempts:
            attempts += 1
            i, j = random.randint(0, self.board_size-1), random.randint(0, self.board_size-1)

            if board[i, j] == 0:
                # Bias towards territorial control
                black_dist = abs(i - black_territory[0]) + abs(j - black_territory[1])
                white_dist = abs(i - white_territory[0]) + abs(j - white_territory[1])

                if black_dist < white_dist:
                    color = 1 if random.random() < 0.7 else -1
                else:
                    color = -1 if random.random() < 0.7 else 1

                # Check if move is valid
                if not self._is_suicide_move(board, i, j, color):
                    board[i, j] = color
                    self._apply_go_rules(board, (i, j), color)
                    stones_placed += 1

        outcome = self._evaluate_position(board)

        metadata = {
            'type': 'endgame',
            'stones_placed': int(stones_placed),
            'fill_ratio': float(stones_placed / self.board_size_sq)
        }

        return board, outcome, metadata
    
    def _generate_midgame_position(self) -> Tuple[np.ndarray, int, Dict]:
        """Generate midgame position with proper Go rules"""
        board = np.zeros((self.board_size, self.board_size))

        # Fill 30-60% of board
        num_stones = random.randint(int(self.board_size_sq * 0.3), int(self.board_size_sq * 0.6))

        # Create some groups and fighting
        stones_placed = 0
        current_color = 1  # Start with black
        group_attempts = 0
        max_group_attempts = num_stones * 10  # Safety limit

        while stones_placed < num_stones and group_attempts < max_group_attempts:
            group_attempts += 1
            # Pick a random starting point
            start_i = random.randint(0, self.board_size-1)
            start_j = random.randint(0, self.board_size-1)

            # Create a small group (2-4 stones)
            group_size = random.randint(2, 4)
            for _ in range(group_size):
                if stones_placed >= num_stones:
                    break

                # Try to place near the starting point
                for attempt in range(10):
                    i = start_i + random.randint(-1, 1)
                    j = start_j + random.randint(-1, 1)
                    i = max(0, min(self.board_size-1, i))
                    j = max(0, min(self.board_size-1, j))

                    if board[i, j] == 0:
                        # Check if move is valid
                        if not self._is_suicide_move(board, i, j, current_color):
                            board[i, j] = current_color
                            self._apply_go_rules(board, (i, j), current_color)
                            stones_placed += 1
                            break

            # Switch colors
            current_color = -current_color

        outcome = self._evaluate_position(board)

        metadata = {
            'type': 'midgame',
            'stones_placed': int(stones_placed),
            'fill_ratio': float(stones_placed / self.board_size_sq)
        }

        return board, outcome, metadata
    
    def _generate_opening_position(self) -> Tuple[np.ndarray, int, Dict]:
        """Generate opening position (sparse) with proper Go rules"""
        board = np.zeros((self.board_size, self.board_size))

        # Place 2-8 stones (but not more than board size)
        max_stones = min(8, self.board_size_sq - 1)
        num_stones = random.randint(2, max(2, max_stones))

        # Start with corners and center areas
        good_positions = [
            (0, 0), (0, self.board_size-1), (self.board_size-1, 0), (self.board_size-1, self.board_size-1),  # Corners
            (self.board_size//2, self.board_size//2)  # Center
        ]

        stones_placed = 0
        current_color = 1
        attempts = 0
        max_attempts = num_stones * 100  # Safety limit

        while stones_placed < num_stones and attempts < max_attempts:
            attempts += 1
            if stones_placed < len(good_positions) and random.random() < 0.6:
                # Use good position
                i, j = good_positions[stones_placed % len(good_positions)]
                if board[i, j] == 0:
                    if not self._is_suicide_move(board, i, j, current_color):
                        board[i, j] = current_color
                        self._apply_go_rules(board, (i, j), current_color)
                        stones_placed += 1
                        current_color = -current_color
            else:
                # Random position
                i, j = random.randint(0, self.board_size-1), random.randint(0, self.board_size-1)
                if board[i, j] == 0:
                    if not self._is_suicide_move(board, i, j, current_color):
                        board[i, j] = current_color
                        self._apply_go_rules(board, (i, j), current_color)
                        stones_placed += 1
                        current_color = -current_color

        outcome = self._evaluate_position(board)

        metadata = {
            'type': 'opening',
            'stones_placed': int(stones_placed),
            'fill_ratio': float(stones_placed / self.board_size_sq)
        }

        return board, outcome, metadata
    
    def _generate_territorial_position(self) -> Tuple[np.ndarray, int, Dict]:
        """Generate position focused on territory with proper Go rules"""
        board = np.zeros((self.board_size, self.board_size))

        # Create clear territorial boundaries
        mid = self.board_size // 2

        # Black controls one side, White controls the other
        if random.random() < 0.5:
            # Vertical split
            for i in range(self.board_size):
                for j in range(mid):
                    if random.random() < 0.4:  # 40% chance to place stone
                        color = 1  # Black territory
                        if not self._is_suicide_move(board, i, j, color):
                            board[i, j] = color
                            self._apply_go_rules(board, (i, j), color)

                for j in range(mid+1, self.board_size):
                    if random.random() < 0.4:
                        color = -1  # White territory
                        if not self._is_suicide_move(board, i, j, color):
                            board[i, j] = color
                            self._apply_go_rules(board, (i, j), color)

            # Add boundary stones
            for i in range(self.board_size):
                if random.random() < 0.6 and board[i, mid] == 0:
                    color = random.choice([1, -1])
                    if not self._is_suicide_move(board, i, mid, color):
                        board[i, mid] = color
                        self._apply_go_rules(board, (i, mid), color)
        else:
            # Horizontal split
            for i in range(mid):
                for j in range(self.board_size):
                    if random.random() < 0.4:
                        color = 1  # Black territory
                        if not self._is_suicide_move(board, i, j, color):
                            board[i, j] = color
                            self._apply_go_rules(board, (i, j), color)

            for i in range(mid+1, self.board_size):
                for j in range(self.board_size):
                    if random.random() < 0.4:
                        color = -1  # White territory
                        if not self._is_suicide_move(board, i, j, color):
                            board[i, j] = color
                            self._apply_go_rules(board, (i, j), color)

            # Add boundary stones
            for j in range(self.board_size):
                if random.random() < 0.6 and board[mid, j] == 0:
                    color = random.choice([1, -1])
                    if not self._is_suicide_move(board, mid, j, color):
                        board[mid, j] = color
                        self._apply_go_rules(board, (mid, j), color)

        outcome = self._evaluate_position(board)

        metadata = {
            'type': 'territorial',
            'stones_placed': int(np.sum(board != 0)),
            'fill_ratio': float(np.sum(board != 0) / self.board_size_sq)
        }

        return board, outcome, metadata
    
    def _generate_fighting_position(self) -> Tuple[np.ndarray, int, Dict]:
        """Generate position with fighting/tactical elements with proper Go rules"""
        board = np.zeros((self.board_size, self.board_size))

        # Create fighting scenario in center
        center = self.board_size // 2

        # Place alternating colors in fighting formation
        fighting_positions = [
            (center, center),
            (center-1, center), (center+1, center),
            (center, center-1), (center, center+1),
            (center-1, center-1), (center+1, center+1),
            (center-1, center+1), (center+1, center-1)
        ]

        color = 1
        for pos in fighting_positions:
            i, j = pos
            if 0 <= i < self.board_size and 0 <= j < self.board_size:
                if random.random() < 0.7:  # Not all positions filled
                    if board[i, j] == 0 and not self._is_suicide_move(board, i, j, color):
                        board[i, j] = color
                        self._apply_go_rules(board, (i, j), color)
                        color = -color

        # Add some random stones elsewhere
        for _ in range(random.randint(3, 8)):
            i, j = random.randint(0, self.board_size-1), random.randint(0, self.board_size-1)
            if board[i, j] == 0:
                color = random.choice([1, -1])
                if not self._is_suicide_move(board, i, j, color):
                    board[i, j] = color
                    self._apply_go_rules(board, (i, j), color)

        outcome = self._evaluate_position(board)

        metadata = {
            'type': 'fighting',
            'stones_placed': int(np.sum(board != 0)),
            'fill_ratio': float(np.sum(board != 0) / self.board_size_sq)
        }

        return board, outcome, metadata
    
    def _evaluate_position(self, board: np.ndarray) -> int:
        """Evaluate who is winning in this position"""
        
        # Count material
        black_stones = np.sum(board == 1)
        white_stones = np.sum(board == -1)
        material_diff = black_stones - white_stones
        
        # Count territory (simple version)
        black_territory, white_territory = self._count_territory(board)
        territory_diff = black_territory - white_territory
        
        # Count liberties
        black_liberties = self._count_liberties(board, 1)
        white_liberties = self._count_liberties(board, -1)
        liberty_diff = black_liberties - white_liberties
        
        # Combined score
        total_score = material_diff + territory_diff * 0.5 + liberty_diff * 0.1
        
        # Convert to game outcome (0.0-0.5-1.0 scale)
        if total_score > 1.5:
            return 1.0    # Black wins
        elif total_score < -1.5:
            return 0.0    # White wins
        else:
            return 0.5    # Draw/close game
    
    def _count_territory(self, board: np.ndarray) -> Tuple[int, int]:
        """
        Count territory controlled by each color.
        Uses 4-neighbor orthogonal adjacency (proper Go rules, not 8-neighbor diagonal).
        """
        black_territory = 0
        white_territory = 0

        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i, j] == 0:  # Empty point
                    # Check only 4 orthogonal neighbors (not diagonals)
                    nearby_black = 0
                    nearby_white = 0

                    for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ni, nj = i + di, j + dj
                        if 0 <= ni < self.board_size and 0 <= nj < self.board_size:
                            if board[ni, nj] == 1:
                                nearby_black += 1
                            elif board[ni, nj] == -1:
                                nearby_white += 1

                    if nearby_black > nearby_white:
                        black_territory += 1
                    elif nearby_white > nearby_black:
                        white_territory += 1

        return black_territory, white_territory
    
    def _count_liberties(self, board: np.ndarray, color: int) -> int:
        """Count total liberties for a color"""
        total_liberties = 0

        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i, j] == color:
                    # Count adjacent empty spaces
                    for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        ni, nj = i + di, j + dj
                        if 0 <= ni < self.board_size and 0 <= nj < self.board_size:
                            if board[ni, nj] == 0:
                                total_liberties += 1

        return total_liberties

    def _find_group(self, board: np.ndarray, i: int, j: int, visited: np.ndarray) -> List[Tuple[int, int]]:
        """
        Find all stones connected to position (i, j) using flood-fill.
        Returns list of (row, col) positions in the group.
        """
        if visited[i, j]:
            return []

        color = board[i, j]
        if color == 0:  # Empty cell has no group
            return []

        group = []
        stack = [(i, j)]

        while stack:
            r, c = stack.pop()

            if visited[r, c]:
                continue

            visited[r, c] = True
            group.append((r, c))

            # Check 4 orthogonal neighbors
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if (0 <= nr < self.board_size and 0 <= nc < self.board_size
                    and not visited[nr, nc] and board[nr, nc] == color):
                    stack.append((nr, nc))

        return group

    def _get_group_liberties(self, board: np.ndarray, group: List[Tuple[int, int]]) -> int:
        """
        Count liberties (empty adjacent points) for a group of stones.
        Each empty point is counted once even if adjacent to multiple group stones.
        """
        liberties = set()

        for i, j in group:
            for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                ni, nj = i + di, j + dj
                if (0 <= ni < self.board_size and 0 <= nj < self.board_size
                    and board[ni, nj] == 0):
                    liberties.add((ni, nj))

        return len(liberties)

    def _capture_groups(self, board: np.ndarray, opponent_color: int) -> int:
        """
        Remove all opponent groups with zero liberties (captured).
        Returns number of stones captured.
        """
        captured_count = 0
        visited = np.zeros((self.board_size, self.board_size), dtype=bool)

        for i in range(self.board_size):
            for j in range(self.board_size):
                if board[i, j] == opponent_color and not visited[i, j]:
                    group = self._find_group(board, i, j, visited)

                    if group:
                        liberties = self._get_group_liberties(board, group)

                        if liberties == 0:
                            # Capture this group
                            for r, c in group:
                                board[r, c] = 0
                            captured_count += len(group)

        return captured_count

    def _is_suicide_move(self, board: np.ndarray, i: int, j: int, color: int) -> bool:
        """
        Check if placing a stone at (i, j) would be suicide (self-capture).
        A move is suicide if it creates a group with zero liberties AND doesn't capture anything.
        """
        if board[i, j] != 0:
            return True  # Position already occupied

        # Temporarily place the stone
        board[i, j] = color

        # Check if this move captures any opponent groups
        opponent_color = -color
        opponent_captured = False

        for di, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ni, nj = i + di, j + dj
            if (0 <= ni < self.board_size and 0 <= nj < self.board_size
                and board[ni, nj] == opponent_color):
                visited = np.zeros((self.board_size, self.board_size), dtype=bool)
                opponent_group = self._find_group(board, ni, nj, visited)
                if opponent_group and self._get_group_liberties(board, opponent_group) == 0:
                    opponent_captured = True
                    break

        # Check if our own group has liberties
        visited = np.zeros((self.board_size, self.board_size), dtype=bool)
        our_group = self._find_group(board, i, j, visited)
        our_liberties = self._get_group_liberties(board, our_group)

        # Remove temporary stone
        board[i, j] = 0

        # Suicide if: we have no liberties AND we don't capture anything
        return (our_liberties == 0 and not opponent_captured)

    def _apply_go_rules(self, board: np.ndarray, last_move: Tuple[int, int], last_color: int):
        """
        Apply proper Go rules after a move:
        1. Capture opponent groups with zero liberties
        2. Enforce no-suicide rule (already checked before placement)
        """
        if last_move == (-1, -1) or last_move is None:
            return  # No move to process

        opponent_color = -last_color

        # Capture opponent groups that have zero liberties
        self._capture_groups(board, opponent_color)

def main():
    """Generate position evaluation dataset"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate Position Evaluation Dataset")
    parser.add_argument('--num_positions', type=int, default=50000,
                       help='Number of positions to generate')
    parser.add_argument('--board_size', type=int, default=5,
                       help='Go board size')
    parser.add_argument('--output', type=str, default='position_evaluation_dataset.json',
                       help='Output file path')
    
    args = parser.parse_args()
    
    # Create generator
    generator = PositionEvaluationDataGenerator(board_size=args.board_size)
    
    # Generate dataset
    dataset = generator.generate_dataset(
        num_positions=args.num_positions,
        output_file=args.output
    )
    
    print(f"\n✅ Position evaluation dataset generated!")
    print(f"💾 File: {args.output}")
    print(f"📊 Ready for training with position_evaluator.py")

if __name__ == "__main__":
    main()
