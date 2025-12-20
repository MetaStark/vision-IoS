"""Diagnostic logging system."""
from typing import Dict, Any, List
from datetime import datetime
from meta_perception.models.diagnostic_models import DiagnosticLog
from meta_perception.utils.id_generation import generate_diagnostic_id

class DiagnosticLogger:
    """Diagnostic logger for perception computations."""
    
    def __init__(self, module: str, computation: str):
        self.module = module
        self.computation = computation
        self.inputs = {}
        self.output_value = None
        self.output_interpretation = ""
        self.computation_steps = []
        self.thresholds_used = {}
        self.comparisons = []
        self.contributing_factors = {}
    
    def log_step(self, step_num: int, description: str, inputs: Any, outputs: Any, explanation: str):
        """Log a computation step."""
        self.computation_steps.append({
            "step": step_num,
            "description": description,
            "inputs": inputs,
            "outputs": outputs,
            "explanation": explanation
        })
    
    def log_threshold(self, name: str, value: float):
        """Log a threshold."""
        self.thresholds_used[name] = value
    
    def log_comparison(self, comparison: str):
        """Log a comparison."""
        self.comparisons.append(comparison)
    
    def log_factor(self, factor: str, contribution: float):
        """Log a contributing factor."""
        self.contributing_factors[factor] = contribution
    
    def finalize(self) -> DiagnosticLog:
        """Finalize and return diagnostic log."""
        return DiagnosticLog(
            log_id=generate_diagnostic_id(self.module, self.computation, datetime.now()),
            timestamp=datetime.now(),
            module=self.module,
            computation=self.computation,
            inputs=self.inputs,
            output_value=self.output_value,
            output_interpretation=self.output_interpretation,
            computation_steps=self.computation_steps,
            thresholds_used=self.thresholds_used,
            comparisons=self.comparisons,
            contributing_factors=self.contributing_factors
        )
