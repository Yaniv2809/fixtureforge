"""
Cache AI responses to save costs and speed
"""
import hashlib
import json
# import os
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timedelta


class ResponseCache:
    """Cache AI responses locally"""
    
    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # Default: ~/.fixtureforge/cache
            self.cache_dir = Path.home() / ".fixtureforge" / "cache"
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(days=7)  # Cache for 7 days
    
    def _hash_key(self, model_name: str, context: str, overrides: Dict) -> str:
        """Generate cache key"""
        key_data = {
            "model": model_name,
            "context": context,
            "overrides": overrides
        }
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(
        self,
        model_name: str,
        context: Optional[str],
        overrides: Dict[str, Any]
    ) -> Optional[Any]:
        """Get from cache"""
        key = self._hash_key(model_name, context or "", overrides)
        cache_file = self.cache_dir / f"{key}.json"
        
        if not cache_file.exists():
            return None
        
        # Check if expired
        mod_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - mod_time > self.ttl:
            cache_file.unlink()  # Delete expired
            return None
        
        # Load
        with open(cache_file, 'r') as f:
            return json.load(f)
    
    def set(
        self,
        model_name: str,
        context: Optional[str],
        overrides: Dict[str, Any],
        data: Any
    ):
        """Save to cache"""
        key = self._hash_key(model_name, context or "", overrides)
        cache_file = self.cache_dir / f"{key}.json"
        
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def clear(self):
        """Clear all cache"""
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        files = list(self.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in files)
        
        return {
            "entries": len(files),
            "size_mb": round(total_size / 1024 / 1024, 2),
            "location": str(self.cache_dir)
        }