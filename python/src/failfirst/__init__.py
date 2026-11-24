"""failfirst: a check that has never failed carries no information."""
__version__ = "0.1.2"

from .core import LockError, baseline, format_report, verify  # noqa: E402
from .model import SpecError, criterion_hash, load_criteria, normalize_criteria  # noqa: E402
from .agent import CliError, describe  # noqa: E402
from .runner import evaluate, observe  # noqa: E402

__all__ = ["baseline", "verify", "format_report", "load_criteria", "normalize_criteria",
           "criterion_hash", "evaluate", "observe", "SpecError", "LockError", "CliError", "describe", "__version__"]
