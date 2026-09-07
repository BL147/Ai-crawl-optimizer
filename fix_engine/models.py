"""Data models for Phase 2 Fix Application Engine."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class FixStatus(str, Enum):
    """Execution statuses supported by the Fix Application Engine."""
    APPLIED = "applied"
    ALREADY_APPLIED = "already_applied"
    UNSUPPORTED_FIX = "unsupported_fix"
    TARGET_NOT_ALLOWED = "target_not_allowed"
    APPLICATION_FAILED = "application_failed"


@dataclass
class FixResult:
    """Structured result returned after attempting to apply a fix."""
    fix_id: str
    status: str
    target: str
    files_changed: List[str] = field(default_factory=list)
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to clean JSON-serializable dictionary."""
        res: Dict[str, Any] = {
            "fix_id": self.fix_id,
            "status": self.status,
            "target": self.target,
            "files_changed": list(self.files_changed),
            "message": self.message,
        }
        if self.details:
            res["details"] = self.details
        return res


@dataclass
class TestEnvironment:
    """Represents an approved, registered local test environment."""
    __test__ = False
    id: str
    root_dir: Path
    base_url: Optional[str] = None
    robots_path: Optional[Path] = None
    config_path: Optional[Path] = None
    description: str = ""

    def __post_init__(self) -> None:
        # Canonicalize root_dir to an absolute resolved Path
        self.root_dir = Path(self.root_dir).resolve()
        if self.root_dir == Path(self.root_dir.anchor):
            raise ValueError(f"root_dir cannot be root filesystem directory: '{self.root_dir}'")

        # Resolve robots_path if provided, ensuring it cannot escape root_dir
        if self.robots_path is not None:
            resolved_robots = (self.root_dir / self.robots_path).resolve()
            if not self._is_subpath(resolved_robots, self.root_dir):
                raise ValueError(
                    f"robots_path '{self.robots_path}' attempts path traversal outside root_dir '{self.root_dir}'"
                )
            self.robots_path = resolved_robots
        else:
            default_robots = (self.root_dir / "robots.txt").resolve()
            self.robots_path = default_robots

        # Resolve config_path if provided, ensuring it cannot escape root_dir
        if self.config_path is not None:
            resolved_cfg = (self.root_dir / self.config_path).resolve()
            if not self._is_subpath(resolved_cfg, self.root_dir):
                raise ValueError(
                    f"config_path '{self.config_path}' attempts path traversal outside root_dir '{self.root_dir}'"
                )
            self.config_path = resolved_cfg

    @staticmethod
    def _is_subpath(child: Path, parent: Path) -> bool:
        """Check if child path resides strictly inside parent directory."""
        try:
            child.relative_to(parent)
            return True
        except ValueError:
            return False
