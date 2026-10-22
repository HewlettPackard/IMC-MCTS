# CAM-Based MCTS Architecture Documentation

## Overview

This document describes the Content-Addressable Memory (CAM) architecture implemented in the IMC-MCTS accelerator. The CAM enables **transposition detection**: automatically recognizing when different move sequences reach the same board position.

---

## Why CAM for MCTS?

### Traditional MCTS Problem

Traditional MCTS uses pointer-based trees indexed by node IDs:
```
Node 100: (visits=5, value=3.0, parent=50, children=[101,102,103])
```

**Problem:** If two different move sequences reach the same board state, they create **separate nodes** with **separate statistics**, missing opportunities to share information.

### CAM Solution

CAM stores board states as **search keys**, not just data:
```
CAM Entry: board_state_hash → node_id
```

When a new position is reached, the CAM searches by **content** (board state) and detects if this exact position was already visited via a different path.

---

## Architecture Components

### 1. Board State Encoder (`board_state_encoder.py`)

**Purpose:** Convert 2D board positions into searchable hash keys

**Key Features:**
- **2-bit per cell encoding:** `00`=empty, `01`=black, `10`=white
- **Zobrist hashing:** Fast O(1) hash computation with incremental updates
- **Canonical states:** Optional symmetry detection (rotations, reflections)

**Example:**
```python
encoder = BoardStateEncoder(board_size=5)

board = [[1, 0, 2, 0, 0],
         [0, 1, 0, 2, 0],
         ...]

# Compute hash for CAM lookup
hash_value = encoder.zobrist_hash(board)
# → 0xD4D7DFF113BF3178
```

**Incremental Updates (Critical for Performance):**
```python
# During rollout, update hash incrementally (O(1))
new_hash = encoder.incremental_hash_update(
    current_hash=0xD4D7DFF113BF3178,
    row=2, col=2,
    old_piece=0,  # Empty
    new_piece=1   # Black
)
# Much faster than recomputing entire board hash!
```

---

### 2. CAM Storage Structure (`base_components.py`)

**Three-Level Storage Hierarchy:**

```python
class SelectionUnitBase:
    # Level 1: Node metadata (SRAM)
    node_storage = {}  # node_id → (visits, value, parent_id, children)

    # Level 2: Board states
    board_state_storage = {}  # node_id → board (2D list)

    # Level 3: CAM lookup (content-addressable)
    state_hash_to_node = {}  # state_hash → node_id
```

**CAM Lookup Flow:**
1. Compute board state hash: `hash = encoder.zobrist_hash(board)`
2. CAM search: `node_id = state_hash_to_node.get(hash)`
3. If found: **Transposition detected!**
4. If not found: Insert new entry

---

### 3. CAM Operations

#### A. `cam_lookup_by_state(board_state)` → node_id or None

Searches CAM by board state **content** (not by node ID).

```python
def cam_lookup_by_state(self, board_state: List[List[int]]) -> Optional[int]:
    # Compute Zobrist hash
    state_hash = self.encoder.zobrist_hash(board_state)

    # CAM search (parallel in hardware, O(1) hash table in software)
    if state_hash in self.state_hash_to_node:
        self.cam_hits += 1
        return self.state_hash_to_node[state_hash]
    else:
        self.cam_misses += 1
        return None
```

**Hardware Implementation:**
In actual CAM hardware, this would be **parallel comparison** across all entries simultaneously (true O(1) search).

---

#### B. `cam_insert_state(node_id, board_state)` → bool

Inserts new board state into CAM.

```python
def cam_insert_state(self, node_id: int, board_state: List[List[int]]) -> bool:
    state_hash = self.encoder.zobrist_hash(board_state)

    # Check for transposition
    if state_hash in self.state_hash_to_node:
        self.transpositions_detected += 1
        return False  # Transposition detected

    # Insert into CAM
    self.state_hash_to_node[state_hash] = node_id
    self.board_state_storage[node_id] = board_state
    self.unique_states += 1

    return True  # New unique state
```

---

#### C. `merge_transposition_nodes(existing_id, new_id)` → merged_id

Merges statistics when transposition is detected.

```python
def merge_transposition_nodes(self, existing_node_id: int, new_node_id: int) -> int:
    # Get stats from both nodes
    existing_visits, existing_value, _, existing_children = self.node_storage[existing_node_id]
    new_visits, new_value, _, new_children = self.node_storage[new_node_id]

    # Merge statistics
    merged_visits = existing_visits + new_visits
    merged_value = existing_value + new_value
    merged_children = list(set(existing_children + new_children))

    # Update existing node
    self.node_storage[existing_node_id] = (
        merged_visits,
        merged_value,
        existing_parent,
        merged_children
    )

    return existing_node_id
```

---

## Usage Example: Transposition Detection

### Scenario

Two different move sequences that reach the same board position:

**Path 1:** Black (2,2) → White (1,1) → Black (3,3)
**Path 2:** White (1,1) → Black (2,2) → Black (3,3)

**Final board state is identical!**

### Without CAM (Traditional MCTS)

```
Node 100: Black (2,2) → White (1,1) → Black (3,3)
  visits=5, value=3.0

Node 200: White (1,1) → Black (2,2) → Black (3,3)
  visits=3, value=2.0

→ Two separate nodes, statistics NOT shared
→ Wasted memory, slower convergence
```

### With CAM (Transposition Detection)

```
Path 1 arrives:
  board_hash = 0xD4D7DFF113BF3178
  CAM search: Not found
  Insert as Node 100 (visits=5, value=3.0)

Path 2 arrives:
  board_hash = 0xD4D7DFF113BF3178  ← SAME HASH!
  CAM search: Found Node 100
  ✓ TRANSPOSITION DETECTED!
  Merge: Node 100 (visits=5+3=8, value=3.0+2.0=5.0)

→ Single node with combined statistics
→ Better value estimates, faster convergence
```

---

## Performance Metrics

The implementation tracks CAM performance:

### Statistics Collected

```python
# CAM hit/miss rates
self.cam_hits          # Successful CAM lookups
self.cam_misses        # CAM lookups that failed

# Transposition detection
self.transpositions_detected  # Number of transpositions found
self.unique_states            # Number of unique board states

# Rates
cam_hit_rate = cam_hits / (cam_hits + cam_misses) * 100
transposition_rate = transpositions_detected / unique_states * 100
```

### Expected Performance

**Small boards (5×5):**
- Transposition rate: 5-15%
- CAM hit rate: 60-80%

**Large boards (19×19):**
- Transposition rate: 1-5% (fewer transpositions)
- CAM hit rate: 40-60%

**Complex games (Chess, Go):**
- Higher transposition rates due to tactical patterns
- CAM becomes more valuable

---

## Hardware Implementation Details

### CAM Entry Format (64-bit)

```
Bits [63:48]: State hash (16-bit truncated)
Bits [47:32]: Node ID (16-bit)
Bits [31:16]: SRAM address (16-bit)
Bits [15:0]:  Valid + flags (16-bit)
```

### CAM Search Operation (Hardware)

```
CYCLE 0: Input board state pattern
CYCLE 1: Parallel comparison across ALL CAM entries
         → match_lines[0..255] = comparison results
CYCLE 2: Priority encoder selects first match
         → Output: node_id

Total latency: 3 cycles (true O(1) lookup!)
```

### Software Model vs. Hardware

| Aspect | Software (Python dict) | Hardware (CAM) |
|--------|----------------------|----------------|
| Search | Hash table O(log n) | Parallel comparison O(1) |
| Latency | Variable (hash collisions) | Fixed 1-3 cycles |
| Power | Negligible | 0.48 fJ/bit |
| Area | N/A | 0.093 μm²/cell @ 22nm |

---

## Integration with MCTS Phases

### Selection Phase

```python
def selection_with_transposition_detection(current_board):
    # CAM lookup: Have we seen this exact position before?
    existing_node = cam_lookup_by_state(current_board)

    if existing_node:
        # Transposition! Reuse existing node
        return existing_node
    else:
        # New position: continue normal selection
        return select_best_child_ucb1(...)
```

### Expansion Phase

```python
def expansion_with_cam_insert(parent_node, move):
    # Generate child board state
    child_board = apply_move(parent_board, move)

    # Check if this state already exists (transposition)
    existing_node = cam_lookup_by_state(child_board)

    if existing_node:
        # Transposition: link parent to existing node
        parent.children.append(existing_node)
        transpositions_detected += 1
    else:
        # New state: create new node and insert into CAM
        new_node_id = allocate_node()
        cam_insert_state(new_node_id, child_board)
        parent.children.append(new_node_id)
```

---

## Configuration Parameters

```python
# Enable/disable transposition detection
enable_transposition_detection = True  # Default: enabled

# Use canonical states (detect symmetric positions)
use_canonical_states = False  # Default: disabled (expensive)

# CAM size (number of entries)
cam_entries = 256  # For 5x5 boards
cam_entries = 512  # For 9x9 boards
cam_entries = 2048  # For 19x19 boards
```

---

## Benefits Summary

### 1. Automatic Transposition Detection
- Recognizes same board state via different move sequences
- No manual tracking required

### 2. Improved Statistics
- Merges visit counts and values from all paths to same position
- Better UCB1 estimates, faster convergence

### 3. Memory Efficiency
- Stores each unique board state only once
- Saves memory for games with high transposition rates

### 4. Hardware-Friendly
- Zobrist hashing: O(1) incremental updates
- CAM search: O(1) parallel lookup in hardware
- Predictable latency for real-time systems

---

## Testing and Validation

### Run CAM Tests

```bash
cd py_sst_cpp/components/common
python3 test_cam_functionality.py
```

### Expected Output

```
✓ TRANSPOSITION DETECTED!
✓ Merged statistics: visits=5+3=8, value=3.0+2.0=5.0
✓ CAM correctly detected transposition and merged statistics!
✓ Incremental hash matches full rehash!
```

---

## Future Enhancements

### 1. Hardware CAM RTL Module

Implement true parallel CAM in SystemVerilog:
```systemverilog
module cam_selection_unit #(
    parameter NUM_ENTRIES = 256,
    parameter STATE_WIDTH = 50  // 5x5 board
)(
    input logic [STATE_WIDTH-1:0] search_pattern,
    output logic [NUM_ENTRIES-1:0] match_lines  // Parallel matches
);
```

### 2. LRU Eviction

When CAM is full, evict least-recently-used entries:
```python
def cam_insert_with_lru_eviction(node_id, board_state):
    if len(state_hash_to_node) >= cam_entries:
        # Find and evict LRU entry
        lru_node_id = find_lru_node()
        evict_from_cam(lru_node_id)

    cam_insert_state(node_id, board_state)
```

### 3. Canonical State Detection

Enable symmetry-aware transposition detection:
```python
canonical_board, transform = encoder.canonicalize_state(board)
state_hash = encoder.zobrist_hash(canonical_board)
# Now rotations/reflections of same position share one CAM entry
```

---

## References

- **Zobrist Hashing:** Zobrist, A. L. (1970). "A new hashing method with application for game playing"
- **MCTS Transposition Tables:** Chaslot et al. (2008). "Monte-Carlo Tree Search: A New Framework for Game AI"
- **CAM Architectures:** Pagiamtzis, K. & Sheikholeslami, A. (2006). "Content-addressable memory (CAM) circuits and architectures"

---
