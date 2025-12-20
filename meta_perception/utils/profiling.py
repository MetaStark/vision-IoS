"""Performance profiling for Meta-Perception Layer."""

import time
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ProfileEntry:
    """Single profiling entry."""
    name: str
    start_time: float
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    metadata: Dict = field(default_factory=dict)


class PerformanceProfiler:
    """
    Performance profiler for tracking computation times.

    Usage:
        profiler = PerformanceProfiler()

        with profiler.profile("entropy_computation"):
            result = compute_entropy(...)

        print(profiler.get_summary())
    """

    def __init__(self, enabled: bool = True):
        """
        Initialize profiler.

        Args:
            enabled: Whether profiling is enabled
        """
        self.enabled = enabled
        self.entries: List[ProfileEntry] = []
        self._active_entry: Optional[ProfileEntry] = None

    def profile(self, name: str, **metadata):
        """
        Context manager for profiling a block of code.

        Args:
            name: Name of the code block
            **metadata: Additional metadata

        Returns:
            Context manager
        """
        return _ProfileContext(self, name, metadata)

    def start(self, name: str, **metadata) -> None:
        """Start profiling a named section."""
        if not self.enabled:
            return

        entry = ProfileEntry(
            name=name,
            start_time=time.perf_counter(),
            metadata=metadata
        )
        self.entries.append(entry)
        self._active_entry = entry

    def stop(self) -> Optional[float]:
        """
        Stop profiling current section.

        Returns:
            Duration in milliseconds, or None if not profiling
        """
        if not self.enabled or self._active_entry is None:
            return None

        end_time = time.perf_counter()
        self._active_entry.end_time = end_time
        self._active_entry.duration_ms = (end_time - self._active_entry.start_time) * 1000

        duration = self._active_entry.duration_ms
        self._active_entry = None

        return duration

    def get_total_time_ms(self) -> float:
        """Get total profiled time in milliseconds."""
        return sum(e.duration_ms for e in self.entries if e.duration_ms is not None)

    def get_summary(self) -> Dict[str, float]:
        """
        Get summary of profiling results.

        Returns:
            Dictionary of {name: duration_ms}
        """
        summary = {}
        for entry in self.entries:
            if entry.duration_ms is not None:
                if entry.name in summary:
                    summary[entry.name] += entry.duration_ms
                else:
                    summary[entry.name] = entry.duration_ms

        return summary

    def get_detailed_report(self) -> List[Dict]:
        """Get detailed report of all entries."""
        return [
            {
                "name": e.name,
                "duration_ms": e.duration_ms,
                "metadata": e.metadata
            }
            for e in self.entries
            if e.duration_ms is not None
        ]

    def reset(self) -> None:
        """Reset profiler state."""
        self.entries = []
        self._active_entry = None

    def check_performance_gate(self, max_time_ms: float) -> bool:
        """
        Check if total time is within performance gate.

        Args:
            max_time_ms: Maximum allowed time in milliseconds

        Returns:
            True if within gate, False otherwise
        """
        return self.get_total_time_ms() <= max_time_ms


class _ProfileContext:
    """Context manager for profiling."""

    def __init__(self, profiler: PerformanceProfiler, name: str, metadata: Dict):
        self.profiler = profiler
        self.name = name
        self.metadata = metadata

    def __enter__(self):
        self.profiler.start(self.name, **self.metadata)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.profiler.stop()
        return False
