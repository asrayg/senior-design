#!/usr/bin/env python3
from versioning.cameo_tracker import track_cameo_requirements
from versioning.simulink_tracker import track_simulink_blocks

def main():
    print(f"\n{'='*70}")
    print("UNIVERSAL ARTIFACT VERSION TRACKING")
    print(f"{'='*70}")

    cameo_versions, cameo_new, cameo_changed = track_cameo_requirements()
    simulink_versions, sim_new, sim_changed = track_simulink_blocks()

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Cameo Requirements: {len(cameo_versions)} total ({cameo_new} new, {cameo_changed} changed)")
    print(f"Simulink Blocks: {len(simulink_versions)} total ({sim_new} new, {sim_changed} changed)")
    print(f"{'='*70}")


if __name__ == "__main__":
    main()