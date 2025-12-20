"""JSON serialization for artifacts."""
import json
from pathlib import Path
from typing import Type
from pydantic import BaseModel

def save_artifact(artifact: BaseModel, file_path: str, pretty: bool = True):
    """Save Pydantic model to JSON file."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = artifact.model_dump(mode="json")
    
    with open(path, 'w') as f:
        if pretty:
            json.dump(data, f, indent=2, default=str)
        else:
            json.dump(data, f, default=str)

def load_artifact(file_path: str, model_class: Type[BaseModel]) -> BaseModel:
    """Load Pydantic model from JSON file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return model_class(**data)
