from claimlens.detection.association import associate_damages_with_parts
from claimlens.detection.schemas import DetectedDamage, DetectedPart


def test_damage_associated_with_overlapping_part():
    part = DetectedPart(
        part_id=0,
        name="front-bumper",
        confidence=0.90,
        box=(100.0, 100.0, 300.0, 200.0),
        polygon=[(100.0, 100.0), (300.0, 100.0), (300.0, 200.0), (100.0, 200.0)],
        is_structural=False,
    )
    damage = DetectedDamage(
        damage_id=1,
        name="scratch",
        confidence=0.85,
        box=(120.0, 120.0, 180.0, 150.0),
        polygon=[(120.0, 120.0), (180.0, 120.0), (180.0, 150.0), (120.0, 150.0)],
    )

    associated, unassociated, has_structural = associate_damages_with_parts([damage], [part])

    assert len(associated) == 1
    assert len(unassociated) == 0
    assert not has_structural
    assert associated[0].host_part.name == "front-bumper"
    assert associated[0].overlap_ratio > 0.95
    assert not associated[0].is_structural


def test_damage_on_structural_part_flags_structural():
    part = DetectedPart(
        part_id=7,
        name="quarter-panel",
        confidence=0.88,
        box=(50.0, 50.0, 250.0, 250.0),
        polygon=[(50.0, 50.0), (250.0, 50.0), (250.0, 250.0), (50.0, 250.0)],
        is_structural=True,
    )
    damage = DetectedDamage(
        damage_id=0,
        name="dent",
        confidence=0.92,
        box=(100.0, 100.0, 200.0, 200.0),
        polygon=[(100.0, 100.0), (200.0, 100.0), (200.0, 200.0), (100.0, 200.0)],
    )

    associated, _unassociated, has_structural = associate_damages_with_parts([damage], [part])

    assert len(associated) == 1
    assert has_structural
    assert associated[0].is_structural
    assert associated[0].host_part.name == "quarter-panel"


def test_unassociated_damage_when_no_overlap():
    part = DetectedPart(
        part_id=0,
        name="front-bumper",
        confidence=0.90,
        box=(0.0, 0.0, 50.0, 50.0),
        polygon=[(0.0, 0.0), (50.0, 0.0), (50.0, 50.0), (0.0, 50.0)],
    )
    damage = DetectedDamage(
        damage_id=1,
        name="scratch",
        confidence=0.75,
        box=(200.0, 200.0, 250.0, 250.0),
        polygon=[(200.0, 200.0), (250.0, 200.0), (250.0, 250.0), (200.0, 250.0)],
    )

    associated, unassociated, has_structural = associate_damages_with_parts([damage], [part])

    assert len(associated) == 0
    assert len(unassociated) == 1
    assert not has_structural
    assert unassociated[0].name == "scratch"
