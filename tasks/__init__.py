from .graders import EasyGrader, HardGrader, MediumGrader


def _fallback_grade(*_args, **_kwargs):
    return 0.02


try:
    from .easy_task import grade_easy
except ImportError:
    grade_easy = _fallback_grade

try:
    from .medium_task import grade_medium
except ImportError:
    grade_medium = _fallback_grade

try:
    from .hard_task import grade_hard
except ImportError:
    grade_hard = _fallback_grade

try:
    from .recovery_task import grade_recovery
except ImportError:
    grade_recovery = _fallback_grade

try:
    from .edge_task import grade_edge
except ImportError:
    grade_edge = _fallback_grade

__all__ = [
    'grade_easy',
    'grade_medium',
    'grade_hard',
    'grade_recovery',
    'grade_edge',
    'EasyGrader',
    'MediumGrader',
    'HardGrader',
]
