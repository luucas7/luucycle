#!/usr/bin/env python3
"""Compare raw and projected bytes of EXACTLY the same deterministic inputs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/luucycle/scripts"))
from compact import encode, project
from synthetic_returns import scenario


# Independent consumer contract: do not derive this list from the projector.
CRITICAL = ("id", "status", "decision", "ids", "evidence", "changes", "blockers", "controls")


def measure():
    rows = []
    for name, packet in scenario().items():
        raw = encode(packet)
        projected = project(raw, f"fixture:{name}.json")
        assert len(projected["items"]) == len(packet["items"])
        for original, item in zip(packet["items"], projected["items"]):
            assert set(item) == set(CRITICAL)
            for key in CRITICAL:
                assert encode(item[key]) == encode(original[key]), (name, original["id"], key)
        for key in ("schema", "kind", "complete", "expected_count", "errors"):
            assert projected[key] == packet[key], (name, key)
        assert projected["source"]["bytes"] == len(raw)
        after = len(encode(projected))
        reduction = 100 * (1 - after / len(raw))
        if name == "tasks":
            assert len(packet["items"]) >= 90
            assert reduction >= 80, reduction
        rows.append((name, len(packet["items"]), len(raw), after, reduction, projected["status"]))
    return rows


if __name__ == "__main__":
    print("| Entrée | Éléments | Brut (octets) | Projeté (octets) | Réduction | État |")
    print("| --- | ---: | ---: | ---: | ---: | --- |")
    for name, count, before, after, reduction, status in measure():
        print(f"| {name} | {count} | {before} | {after} | {reduction:.2f} % | {status} |")
    print("Champs critiques et contrôles : conservation exacte sur ces mêmes entrées.")
