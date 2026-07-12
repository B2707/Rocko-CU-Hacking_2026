"""Tests for inferring the ground-truth class from an image filename.

These cover the trickiest bit of test_folder.py: matching filenames (which may be
singular/plural, use spaces/underscores, or carry numbers) to class names, and
mapping merged sub-classes (Cut/Laceration/Stab_wound) to the combined
Sharp_wound class.

Runs under pytest, or standalone: `python tests/test_label_matching.py`.
"""
import os
import sys

# Make the CNN package modules importable regardless of how tests are launched.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_folder import _normalize, build_alias_map, match_label  # noqa: E402

# The 8-class (post-merge) label set the shipped model uses.
CLASSES = [
    "Abrasions", "Bruises", "Burns", "Normal",
    "Pressure_wound", "Sharp_wound", "Surgical_wound", "Venous_wound",
]


def test_normalize_strips_non_letters():
    assert _normalize("Pressure_wound (3)") == "pressurewound"
    assert _normalize("stab_wound.jpg".split(".")[0]) == "stabwound"


def test_merged_members_map_to_sharp_wound():
    am = build_alias_map(CLASSES)
    assert match_label("laceration.jpg", am) == "Sharp_wound"
    assert match_label("cut_web.jpg", am) == "Sharp_wound"
    assert match_label("stab_wound.jpg", am) == "Sharp_wound"


def test_singular_filename_matches_plural_class():
    am = build_alias_map(CLASSES)
    assert match_label("bruise.jpg", am) == "Bruises"


def test_direct_class_names_match():
    am = build_alias_map(CLASSES)
    assert match_label("venous_wound_web.jpg", am) == "Venous_wound"
    assert match_label("normal_web.jpg", am) == "Normal"
    assert match_label("abrasion_web.jpg", am) == "Abrasions"


def test_unrelated_filename_returns_none():
    am = build_alias_map(CLASSES)
    assert match_label("random_photo_1234.jpg", am) is None


if __name__ == "__main__":
    for _name, _fn in sorted(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok:", _name)
    print("all label-matching tests passed")
