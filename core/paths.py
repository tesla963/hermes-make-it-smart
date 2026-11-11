"""Where the index lives, and why it is global.

Hermes ships ``plugins/plugin_storage.py`` with ``plugin_data_dir(name)``, which
resolves ``get_hermes_home()`` on every call — and that function follows the
ACTIVE PROFILE. For most plugins that is right: a plugin's state belongs to the
profile that used it.

This plugin is the exception, because its whole job is to index the twelve
``state.db`` files that live under every profile at once. Splitting its index per
profile would mean twelve half-indexes of the same twelve databases: twelve
subject counters that each number ``Flight Path 001``, twelve export counters
that each start at ``[0001]``, and no single place to look up what was decided.

So the index is global. That does not break the host's rule — the host says
*where* plugin data goes (``plugin-data/<name>``), not that each profile needs
its own copy. We resolve the same path from the real Hermes root instead of from
the profile-relative one.

Kept in ``core/`` with no host imports, so the rule survives a port.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

PLUGIN = "make-it-smart"


def hermes_root() -> Path:
    """The one real Hermes home, whatever profile is active.

    ``get_hermes_home()`` returns ``<root>/profiles/<name>`` when a profile is in
    play. ``HERMES_HOME``, when set, already points at the root.
    """
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env).expanduser().resolve()
    return Path.home() / ".hermes"


def data_dir(plugin: str = PLUGIN) -> Path:
    """Canonical plugin data directory:
    Resolves HERMES_PLUGIN_DATA (env) -> hermes_root() / "plugin-data" / plugin.
    Created if missing.
    """
    env = os.environ.get("HERMES_PLUGIN_DATA")
    if env:
        root = Path(env).expanduser().resolve()
    else:
        root = hermes_root() / "plugin-data" / plugin
    root.mkdir(parents=True, exist_ok=True)
    return root


def ui_data_dir(plugin: str = PLUGIN) -> Path:
    """The desktop UI mirror folder:
    ~/Library/Application Support/Hermes/plugin-files/data/<plugin>/ (macOS)
    or fallback to <hermes root>/plugin-files/data/<plugin>/
    """
    env = os.environ.get("HERMES_UI_DATA")
    if env:
        p = Path(env).expanduser().resolve()
    else:
        mac_dir = Path.home() / "Library" / "Application Support" / "Hermes" / "plugin-files" / "data" / plugin
        if mac_dir.parent.exists() or (Path.home() / "Library" / "Application Support" / "Hermes").exists():
            p = mac_dir
        else:
            p = hermes_root() / "plugin-files" / "data" / plugin
    p.mkdir(parents=True, exist_ok=True)
    return p


def bateria_dir(plugin: str = PLUGIN) -> Path:
    """Canonical directory where personal battery and runtime data live."""
    return data_dir(plugin)


def bateria_objetiva(plugin: str = PLUGIN) -> Path:
    """Objective knowledge battery packaged with the plugin: core/bateria.yaml."""
    return Path(__file__).resolve().parent / "bateria.yaml"


def bateria_personal(plugin: str = PLUGIN) -> Path:
    """Personal battery path.
    Resolves HERMES_PLUGIN_DATA -> canonical data_dir() -> (fallback check UI mirror).
    Canonical always takes priority.
    """
    canonical = data_dir(plugin) / "bateria.personal.yaml"
    if canonical.exists():
        return canonical
    ui_mirror = ui_data_dir(plugin) / "bateria.personal.yaml"
    if ui_mirror.exists():
        return ui_mirror
    return canonical


def exports_dir(plugin: str = PLUGIN) -> Path:
    """Where the CSV exports handed to the owner are written."""
    root = data_dir(plugin) / "exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def index_db(plugin: str = PLUGIN) -> Path:
    """The index: sessions, facets, subject counters. A cache, never a source."""
    return data_dir(plugin) / "data.db"


# --------------------------------------------------------------------------- #
# The export counter
# --------------------------------------------------------------------------- #

_LEDGER = "index.json"


def _ledger_path(plugin: str = PLUGIN) -> Path:
    return exports_dir(plugin) / _LEDGER


def next_export_number(plugin: str = PLUGIN) -> int:
    """Reserve the next ``[CCCC]`` and persist it.

    The counter never resets: an export number is a citation, and reusing one
    would make "look at export 0007" ambiguous after a reinstall.
    """
    path = _ledger_path(plugin)
    data: dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            data = {}
    n = int(data.get("last_export", 0)) + 1
    data["last_export"] = n
    data.setdefault("exports", []).append(n)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    return n


def export_filename(count: int, when, sessions: int) -> str:
    """``[0007] 20261109_1744_884sesiones.csv``

    The number comes first so the files sort by export order in any file
    manager, and so a session can cite the export it came from.
    """
    stamp = when.strftime("%Y%m%d_%H%M")
    return f"[{count:04d}] {stamp}_{sessions}sesiones.csv"
