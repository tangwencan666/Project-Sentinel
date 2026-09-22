"""Resolve explicitly assembled valid datasets while retaining initial suites."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def dataset_path(version):
    original='v2-hybrid.json' if version=='v2' else 'v3-context-optimized.json'
    validated=ROOT/'evaluation/results'/original.replace('.json','-validated.json')
    return validated if validated.exists() else ROOT/'evaluation/results'/original
