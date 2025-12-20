"""Override logging."""
import json
from pathlib import Path
from meta_perception.models.override_models import UncertaintyOverride

def log_uncertainty_override(override: UncertaintyOverride, log_path: str = "artifacts_output/logs/uncertainty_override_log.jsonl"):
    """Log override to JSONL file."""
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'a') as f:
        f.write(json.dumps(override.model_dump(mode="json"), default=str) + "\n")
