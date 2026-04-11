"""Core package initialization."""
from .mod import Mod, ModStatus
from .portal import FactorioPortalAPI
from .downloader import ModDownloader
from .checker import ModChecker
from .mod_list import ModListStore
from .dependency_graph import DepType, DepState, DepNode, build_dep_graph
from .update_guidance import UpdateClassification, GuidanceResult, UpdateGuidanceClassifier
from .profiles import (
    Profile,
    PresetSeed,
    PresetFamily,
    ProfileDiff,
    ProfileDiffItem,
    ProfileSnapshot,
    ProfileStore,
    CURATED_PRESETS,
    DiffAction,
    build_diff,
)
from .queue_models import (
    OperationSource,
    OperationKind,
    OperationState,
    QueueFailure,
    QueueActionState,
    QueueOperation,
    QueueResult,
)

__all__ = [
    "Mod",
    "ModStatus",
    "FactorioPortalAPI",
    "ModDownloader",
    "ModChecker",
    "ModListStore",
    "DepType",
    "DepState",
    "DepNode",
    "build_dep_graph",
    "UpdateClassification",
    "GuidanceResult",
    "UpdateGuidanceClassifier",
    "ModStatus",
    "FactorioPortalAPI",
    "ModDownloader",
    "ModChecker",
    "ModListStore",
    "Profile",
    "PresetSeed",
    "PresetFamily",
    "ProfileDiff",
    "ProfileDiffItem",
    "ProfileSnapshot",
    "ProfileStore",
    "CURATED_PRESETS",
    "DiffAction",
    "build_diff",
    "OperationSource",
    "OperationKind",
    "OperationState",
    "QueueFailure",
    "QueueActionState",
    "QueueOperation",
    "QueueResult",
]
