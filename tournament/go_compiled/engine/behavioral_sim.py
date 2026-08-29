# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Behavioral RTL Simulator for IMC-MCTS Crossbar Neural Network.

Models the exact hardware pipeline:
  DAC -> Crossbar MVM -> ADC -> ReLU -> Crossbar MVM -> ADC -> Softmax

Architecture: 163 inputs -> 96 hidden (ReLU) -> 3 outputs (softmax)
  Input: 2 channels per cell (black/white presence) + turn bit for 9x9 board
  Output: [P(White), P(Draw), P(Black)]

Key: Differential-pair normalization W_eff = (G - 50) / 50
  G in [0.1, 99.9] nS conductance range
"""

import numpy as np
import pickle
from typing import Tuple, Optional


class BehavioralSimulator:
    """
    Behavioral model of the IMC-MCTS crossbar NN hardware.

    Mirrors the RTL pipeline: DAC -> Crossbar -> ADC -> ReLU -> Crossbar -> ADC -> Softmax
    """

    def __init__(
        self,
        weights_file: str,
        board_size: int = 9,
        adc_bits: int = 0,
        conductance_noise_std: float = 0.0,
    ):
        """
        Load trained weights and configure hardware non-idealities.

        Args:
            weights_file: Path to pickle file with conductance weights
            board_size: Go board dimension (default 9)
            adc_bits: ADC resolution (0 = ideal, 8 typical)
            conductance_noise_std: Multiplicative Gaussian noise std
                (0.0 = ideal, 0.10 = +/-10% variation)
        """
        self.board_size = board_size
        self.input_size = board_size * board_size * 2 + 1  # 163 for 9x9 (+ turn bit)
        self.adc_bits = adc_bits
        self.conductance_noise_std = conductance_noise_std

        with open(weights_file, 'rb') as weights_handle:
            model = pickle.load(weights_handle)

        self.weights1 = np.array(model['weights1'], dtype=np.float64)
        self.weights2 = np.array(model['weights2'], dtype=np.float64)
        self.accuracy = model.get('accuracy', 0.0)

        # Reject conductance matrices built for a different input encoding.
        assert self.weights1.shape[0] == self.input_size, \
            f"Weight1 input dim {self.weights1.shape[0]} != expected {self.input_size}"

        self.hidden_size = self.weights1.shape[1]
        self.output_size = self.weights2.shape[1]

        # Cache W_eff = (G - 50) / 50 for the ideal hardware path.
        if self.conductance_noise_std == 0.0:
            self._w_eff1 = (self.weights1 - 50.0) / 50.0
            self._w_eff2 = (self.weights2 - 50.0) / 50.0
        else:
            self._w_eff1 = None
            self._w_eff2 = None

    # ------------------------------------------------------------------
    # DAC: Board state -> voltage inputs
    # ------------------------------------------------------------------

    def board_to_voltages(self, board: np.ndarray, current_player: int = 1) -> np.ndarray:
        """
        DAC conversion: board state -> voltage vector (vectorized).

        2-channel encoding (matches position_to_voltage_dacs.sv):
          Black stone: [V_high, V_low]
          White stone: [V_low, V_high]
          Empty:       [V_low, V_low]
        Plus turn bit: 1.0 = Black to play, 0.0 = White to play

        Args:
            board: (N, N) array with 1=Black, -1=White, 0=Empty
            current_player: 1=Black, -1=White

        Returns:
            Voltage vector of length 2*N^2 + 1 (163 for 9x9)
        """
        flat_board = board.ravel()
        voltages = np.zeros(self.input_size, dtype=np.float64)
        voltages[0::2][:len(flat_board)] = (flat_board == 1).astype(np.float64)   # Black channel
        voltages[1::2][:len(flat_board)] = (flat_board == -1).astype(np.float64)   # White channel
        # Encode the side to move in the final DAC input.
        voltages[-1] = 1.0 if current_player == 1 else 0.0
        return voltages

    # ------------------------------------------------------------------
    # Crossbar MVM: V x G = I (analog parallel multiply-accumulate)
    # ------------------------------------------------------------------

    def crossbar_mvm(self, voltages: np.ndarray, conductances: np.ndarray,
                     w_eff_cached: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Crossbar matrix-vector multiplication with differential-pair normalization.

        Models the physical analog computation:
          I = V x G_eff
        where G_eff = (G - 50) / 50 (differential-pair encoding)

        Args:
            voltages: Input voltage vector from DAC
            conductances: Conductance matrix in [0.1, 99.9] nS
            w_eff_cached: Pre-normalized weights (skips normalization if provided)

        Returns:
            Output current vector
        """
        if w_eff_cached is not None:
            return voltages @ w_eff_cached

        noisy_conductances = conductances.copy()

        # Apply multiplicative device variation before differential decoding.
        if self.conductance_noise_std > 0.0:
            noise = np.random.normal(0, self.conductance_noise_std, noisy_conductances.shape)
            noisy_conductances = noisy_conductances * (1.0 + noise)
            noisy_conductances = np.clip(noisy_conductances, 0.1, 99.9)

        # Differential-pair decoding: W_eff = (G - 50) / 50.
        effective_weights = (noisy_conductances - 50.0) / 50.0

        # Analog crossbar MVM: I = V @ W_eff.
        return voltages @ effective_weights

    # ------------------------------------------------------------------
    # ADC: Analog currents -> digital values
    # ------------------------------------------------------------------

    def adc_quantize(self, currents: np.ndarray) -> np.ndarray:
        """
        ADC conversion: analog currents -> digital values.

        If adc_bits == 0, pass through (ideal).
        Otherwise, quantize to 2^adc_bits levels.

        Args:
            currents: Analog current vector

        Returns:
            Digitized values (or pass-through if ideal)
        """
        if self.adc_bits == 0:
            return currents

        # Normalize the current range before uniform quantization.
        current_min, current_max = currents.min(), currents.max()
        if current_max == current_min:
            return currents

        num_levels = 2 ** self.adc_bits
        normalized = (currents - current_min) / (current_max - current_min)
        quantized = np.round(normalized * (num_levels - 1)) / (num_levels - 1)
        return quantized * (current_max - current_min) + current_min

    # ------------------------------------------------------------------
    # Activation functions
    # ------------------------------------------------------------------

    @staticmethod
    def relu(x: np.ndarray) -> np.ndarray:
        """ReLU activation."""
        return np.maximum(0, x)

    @staticmethod
    def softmax(logits: np.ndarray) -> np.ndarray:
        """Numerically stable softmax."""
        stable_logits = logits - np.max(logits)
        exp_logits = np.exp(stable_logits)
        return exp_logits / np.sum(exp_logits)

    # ------------------------------------------------------------------
    # Full forward pass (RTL pipeline)
    # ------------------------------------------------------------------

    def forward(self, board: np.ndarray, current_player: int = 1) -> Tuple[float, np.ndarray]:
        """
        Complete forward pass through the behavioral RTL pipeline.

        Pipeline:
          1. DAC: board -> voltages (163)
          2. Crossbar 1: voltages x G1 = currents1 (96)
          3. ADC: quantize currents1
          4. ReLU: activation
          5. Crossbar 2: hidden x G2 = currents2 (3)
          6. ADC: quantize currents2
          7. Softmax: [P(White), P(Draw), P(Black)]
          8. Value: P(Black)*1.0 + P(Draw)*0.5

        Args:
            board: (N, N) board array (1=Black, -1=White, 0=Empty)
            current_player: 1=Black, -1=White

        Returns:
            (value, probs) where:
              value: float in [0, 1] from Black's perspective
              probs: array [P(White), P(Draw), P(Black)]
        """
        # 1. DAC: encode board stones and the turn bit as voltages.
        voltages = self.board_to_voltages(board, current_player)

        # 2. Hidden crossbar: I_hidden = V @ W_eff1.
        hidden_currents = self.crossbar_mvm(voltages, self.weights1, self._w_eff1)

        # 3. Hidden ADC quantization.
        hidden_digital = self.adc_quantize(hidden_currents)

        # 4. ReLU activation.
        hidden_activated = self.relu(hidden_digital)

        # 5. Output crossbar: I_output = h @ W_eff2.
        output_currents = self.crossbar_mvm(hidden_activated, self.weights2, self._w_eff2)

        # 6. Output ADC quantization.
        output_digital = self.adc_quantize(output_currents)

        # 7. Convert logits to [P(White), P(Draw), P(Black)].
        probabilities = self.softmax(output_digital)

        # 8. Expected outcome from Black's perspective.
        value = probabilities[2] * 1.0 + probabilities[1] * 0.5 + probabilities[0] * 0.0

        return value, probabilities

    def evaluate(self, board: np.ndarray, current_player: int = 1) -> float:
        """Convenience: return just the value from Black's perspective."""
        value, _ = self.forward(board, current_player)
        return value


def test_behavioral_sim():
    """Verify forward pass produces valid output."""
    import tempfile, os

    # Create dummy weights in conductance range
    np.random.seed(42)
    w1 = np.random.uniform(10, 90, (163, 96))
    w2 = np.random.uniform(10, 90, (96, 3))

    model = {'weights1': w1.tolist(), 'weights2': w2.tolist(), 'accuracy': 0.5}
    tmp = tempfile.NamedTemporaryFile(suffix='.pkl', delete=False)
    with open(tmp.name, 'wb') as f:
        pickle.dump(model, f)

    try:
        sim = BehavioralSimulator(tmp.name, board_size=9)
        board = np.zeros((9, 9), dtype=np.int8)
        board[4, 4] = 1   # Black center
        board[3, 3] = -1  # White

        value, probs = sim.forward(board)
        assert 0.0 <= value <= 1.0, f"Value {value} out of range"
        assert abs(sum(probs) - 1.0) < 1e-6, f"Probs don't sum to 1: {probs}"
        assert len(probs) == 3

        # Test with noise
        sim_noisy = BehavioralSimulator(tmp.name, board_size=9,
                                         conductance_noise_std=0.10)
        v2, p2 = sim_noisy.forward(board)
        assert 0.0 <= v2 <= 1.0

        # Test with ADC
        sim_adc = BehavioralSimulator(tmp.name, board_size=9, adc_bits=8)
        v3, p3 = sim_adc.forward(board)
        assert 0.0 <= v3 <= 1.0

        print("Behavioral simulator tests passed!")
        print(f"  Ideal: value={value:.4f}, probs={probs}")
        print(f"  Noisy: value={v2:.4f}")
        print(f"  ADC-8: value={v3:.4f}")
    finally:
        os.unlink(tmp.name)


if __name__ == "__main__":
    test_behavioral_sim()
