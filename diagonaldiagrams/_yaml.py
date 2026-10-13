"""PyYAML, if it is installed. YAML specs are optional; JSON always works."""
try:
    import yaml  # optional; falls back to JSON if missing
    HAS_YAML = True
except ImportError:
    yaml = None
    HAS_YAML = False
