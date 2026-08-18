"""Weather dataset variable catalog."""

import re

_ENTRIES = [
    (
        "Sea temperature",
        r"sea temperature|sea[_ ]surface[_ ]temperature|sea[_ ]water[_ ].*temperature|\bthetao\b",
        ("RdYlBu", True),
    ),
    ("Air temperature", r"air temperature|temperature", ("RdYlBu", True)),
    ("Salinity", r"salinity", ("Viridis", False)),
    (
        "Currents",
        r"currents?|\butotal\b|\bvtotal\b|total velocity|water[_ ].*velocity",
        ("Viridis", False),
    ),
    ("Wave height", r"wave height|\bhm0\b|\bvhm0\b", ("Cividis", False)),
    ("Wave period", r"wave period|\bvtpk\b|\btp\b", ("Viridis", False)),
    ("Wave direction", r"wave direction|\bvmdr\b|\bmdir\b", ("Spectral", False)),
    ("Wind", r"wind", ("Viridis", False)),
    ("MSL pressure", r"msl pressure|pressure", ("RdBu", True)),
]

_COMPILED = [(label, re.compile(pattern, re.I), ramp) for label, pattern, ramp in _ENTRIES]

DEFAULT_RAMP = ("Viridis", False)

# The qualifier is the trailing "@ 0.5 m" in "Sea temperature @ 0.5 m", which is
# what MDAL appends to the variable name when it reads a 3D field as a 2D slice.
_QUALIFIER_RE = re.compile(r"(@\s*[\d.]+\s*\w+)\s*$")


def entry_for(text):
    """``(label, ramp)`` for the first field ``text`` looks like, or None."""
    for label, pattern, ramp in _COMPILED:
        if pattern.search(text):
            return label, ramp
    return None


def canonical_name(raw_name, fallback):
    """The card label for one variable.

    ``raw_name`` is what the file called it — for a merged pair, the two
    component variable names — and ``fallback`` the cleaned-up name to keep when
    the field is not one we recognise.
    """
    entry = entry_for(raw_name)
    if entry is None:
        return fallback
    label = entry[0]
    qualifier = _QUALIFIER_RE.search(fallback)
    return f"{label} {qualifier.group(1)}" if qualifier else label


def ramp_for(name):
    """``(ramp name, inverted)`` for a display name."""
    entry = entry_for(name)
    return entry[1] if entry is not None else DEFAULT_RAMP
