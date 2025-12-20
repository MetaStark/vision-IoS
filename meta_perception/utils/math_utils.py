"""Mathematical utilities for Meta-Perception Layer."""

import numpy as np
from typing import List, Dict
from scipy.stats import entropy as scipy_entropy


def compute_entropy(values: List[float], n_bins: int = 50, base: float = 2.0) -> float:
    """
    Compute Shannon entropy of a distribution.

    H(X) = -Σ p(x) log p(x)

    Args:
        values: Data values
        n_bins: Number of bins for discretization
        base: Logarithm base (2 for bits, e for nats)

    Returns:
        Entropy in bits (if base=2)
    """
    if len(values) == 0:
        return 0.0

    # Convert to numpy array
    arr = np.array(values)

    # Remove NaN values
    arr = arr[~np.isnan(arr)]

    if len(arr) == 0:
        return 0.0

    # Discretize into bins
    hist, _ = np.histogram(arr, bins=n_bins)

    # Normalize to get probabilities
    hist = hist + 1e-10  # Avoid log(0)
    probabilities = hist / hist.sum()

    # Compute entropy
    return float(scipy_entropy(probabilities, base=base))


def compute_correlation(x: List[float], y: List[float]) -> float:
    """
    Compute Pearson correlation coefficient.

    Args:
        x: First variable
        y: Second variable

    Returns:
        Correlation coefficient [-1, 1]
    """
    if len(x) != len(y) or len(x) == 0:
        return 0.0

    x_arr = np.array(x)
    y_arr = np.array(y)

    # Remove NaN pairs
    mask = ~(np.isnan(x_arr) | np.isnan(y_arr))
    x_arr = x_arr[mask]
    y_arr = y_arr[mask]

    if len(x_arr) < 2:
        return 0.0

    # Compute correlation
    corr_matrix = np.corrcoef(x_arr, y_arr)
    return float(corr_matrix[0, 1])


def normalize_vector(vec: np.ndarray) -> np.ndarray:
    """
    Normalize vector to [0, 1] range.

    Args:
        vec: Input vector

    Returns:
        Normalized vector
    """
    if len(vec) == 0:
        return vec

    min_val = np.min(vec)
    max_val = np.max(vec)

    if max_val == min_val:
        return np.ones_like(vec) * 0.5

    return (vec - min_val) / (max_val - min_val)


def softmax(logits: np.ndarray) -> np.ndarray:
    """
    Compute softmax function.

    softmax(x)_i = exp(x_i) / Σ exp(x_j)

    Args:
        logits: Input logits

    Returns:
        Probabilities (sum to 1)
    """
    # Numerical stability: subtract max
    exp_logits = np.exp(logits - np.max(logits))
    return exp_logits / exp_logits.sum()


def sigmoid(x: float) -> float:
    """
    Compute sigmoid function.

    σ(x) = 1 / (1 + exp(-x))

    Args:
        x: Input value

    Returns:
        Sigmoid output [0, 1]
    """
    return 1.0 / (1.0 + np.exp(-x))


def compute_rolling_mean(values: List[float], window: int) -> List[float]:
    """Compute rolling mean."""
    if len(values) < window:
        return [np.mean(values)] * len(values)

    arr = np.array(values)
    result = np.convolve(arr, np.ones(window) / window, mode='valid')

    # Pad to original length
    padding = len(values) - len(result)
    return np.pad(result, (padding, 0), mode='edge').tolist()


def compute_rolling_std(values: List[float], window: int) -> List[float]:
    """Compute rolling standard deviation."""
    if len(values) < window:
        return [np.std(values)] * len(values)

    result = []
    arr = np.array(values)

    for i in range(len(arr)):
        start = max(0, i - window + 1)
        result.append(np.std(arr[start:i+1]))

    return result


def detect_outliers(values: List[float], threshold_std: float = 3.0) -> List[int]:
    """
    Detect outliers using z-score method.

    Args:
        values: Data values
        threshold_std: Threshold in standard deviations

    Returns:
        List of indices of outliers
    """
    if len(values) < 2:
        return []

    arr = np.array(values)
    mean = np.mean(arr)
    std = np.std(arr)

    if std == 0:
        return []

    z_scores = np.abs((arr - mean) / std)
    outliers = np.where(z_scores > threshold_std)[0]

    return outliers.tolist()


def compute_percentile_rank(value: float, distribution: List[float]) -> float:
    """
    Compute percentile rank of value in distribution.

    Args:
        value: Value to rank
        distribution: Reference distribution

    Returns:
        Percentile rank [0, 1]
    """
    if len(distribution) == 0:
        return 0.5

    arr = np.array(distribution)
    rank = np.sum(arr <= value) / len(arr)

    return float(rank)
