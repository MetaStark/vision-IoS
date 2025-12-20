"""STIG adapter API - minimal read-only interface."""
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import json
from meta_perception.models.perception_state import PerceptionSnapshot
from meta_perception.models.importance_models import FeatureImportance
from meta_perception.models.override_models import UncertaintyOverride
from meta_perception.artifacts.serializers import load_artifact

class STIGAdapterAPI:
    """Minimal API for STIG integration."""
    
    @staticmethod
    def get_latest_perception_snapshot() -> Optional[PerceptionSnapshot]:
        """Get most recent perception snapshot."""
        snapshot_dir = Path("artifacts_output/perception_snapshots")
        if not snapshot_dir.exists():
            return None
        
        files = list(snapshot_dir.glob("*.json"))
        if not files:
            return None
        
        latest = max(files, key=lambda p: p.stat().st_mtime)
        return load_artifact(str(latest), PerceptionSnapshot)
    
    @staticmethod
    def get_perception_snapshot_by_id(snapshot_id: str) -> Optional[PerceptionSnapshot]:
        """Get specific snapshot by ID."""
        path = Path(f"artifacts_output/perception_snapshots/{snapshot_id}.json")
        if not path.exists():
            return None
        return load_artifact(str(path), PerceptionSnapshot)
    
    @staticmethod
    def get_uncertainty_overrides(
        start_time: datetime,
        end_time: datetime
    ) -> List[UncertaintyOverride]:
        """Get uncertainty override logs."""
        path = Path("artifacts_output/logs/uncertainty_override_log.jsonl")
        if not path.exists():
            return []
        
        overrides = []
        with open(path, 'r') as f:
            for line in f:
                data = json.loads(line)
                override = UncertaintyOverride(**data)
                if start_time <= override.timestamp <= end_time:
                    overrides.append(override)
        
        return overrides
    
    @staticmethod
    def get_system_health() -> Dict[str, Any]:
        """Get system health metrics."""
        snapshot = STIGAdapterAPI.get_latest_perception_snapshot()
        if not snapshot:
            return {"status": "down", "last_update": None}
        
        return {
            "status": "healthy" if snapshot.computation_time_ms < 150 else "degraded",
            "last_update": snapshot.timestamp,
            "avg_computation_time_ms": snapshot.computation_time_ms,
            "should_act": snapshot.state.should_act
        }
