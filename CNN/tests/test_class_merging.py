"""Tests for the class-merging label remap in data.py.

Verifies that Cut + Laceration + Stab_wound collapse into a single Sharp_wound
class (10 -> 8 classes) and that every original index maps to the right merged
index, without touching any files on disk.

Runs under pytest, or standalone: `python tests/test_class_merging.py`.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from data import resolve_classes  # noqa: E402

# The original on-disk folder classes (alphabetical, as ImageFolder returns them).
ORIGINAL = [
    "Abrasions", "Bruises", "Burns", "Cut", "Laceration",
    "Normal", "Pressure_wound", "Stab_wound", "Surgical_wound", "Venous_wound",
]


def test_merge_collapses_to_eight_classes():
    eff, _ = resolve_classes(ORIGINAL, config.MERGED_CLASSES)
    assert len(eff) == 8
    assert "Sharp_wound" in eff
    for gone in ("Cut", "Laceration", "Stab_wound"):
        assert gone not in eff


def test_members_map_to_sharp_wound_index():
    eff, label_map = resolve_classes(ORIGINAL, config.MERGED_CLASSES)
    orig_index = {c: i for i, c in enumerate(ORIGINAL)}
    sharp = eff.index("Sharp_wound")
    for member in ("Cut", "Laceration", "Stab_wound"):
        assert label_map[orig_index[member]] == sharp


def test_non_merged_class_keeps_its_own_index():
    eff, label_map = resolve_classes(ORIGINAL, config.MERGED_CLASSES)
    orig_index = {c: i for i, c in enumerate(ORIGINAL)}
    assert eff[label_map[orig_index["Bruises"]]] == "Bruises"
    assert eff[label_map[orig_index["Normal"]]] == "Normal"


def test_empty_merge_map_is_identity():
    eff, label_map = resolve_classes(ORIGINAL, {})
    assert eff == sorted(ORIGINAL)
    assert len(eff) == 10
    assert label_map == list(range(10))


def test_unknown_member_raises_value_error():
    try:
        resolve_classes(ORIGINAL, {"Bogus": ["NotARealClass"]})
    except ValueError:
        return
    raise AssertionError("expected ValueError for a member not in the dataset")


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok:", _name)
    print("all class-merging tests passed")
