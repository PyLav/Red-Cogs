from __future__ import annotations

import json
import pathlib
import sys

from packaging.requirements import Requirement
from packaging.version import parse

__PYLAV_VERSION__ = sys.argv[1] or sys.argv[2]

pylav_current_minor_version = parse(__PYLAV_VERSION__)

print(f"__PYLAV_VERSION__: {pylav_current_minor_version}")

pylav_threshold_version = f"{pylav_current_minor_version.major}.{pylav_current_minor_version.minor + 1}"

print(f"PyLav max version: {pylav_threshold_version}")

new_pylav_version = f"Py-Lav[all]>={__PYLAV_VERSION__}<{pylav_threshold_version}"

print(f"New PyLav version range: {new_pylav_version}")


for cog in pathlib.Path(__file__).parent.parent.iterdir():
    if cog.is_dir():
        cog_json = cog / "info.json"
        if cog_json.exists():
            with cog_json.open("r+", encoding="utf-8", newline="\n") as info_json:
                info = json.load(info_json)
                if info["requirements"]:
                    new_requirements = []
                    changed = False
                    for requirement in info["requirements"]:
                        requirement = Requirement(requirement)
                        if requirement.name == "Py-Lav" and str(requirement) != new_pylav_version:
                            new_requirements.append(new_pylav_version)
                            changed = True
                        else:
                            new_requirements.append(str(requirement))
                    if changed:
                        print(f"Updating requirements for {cog.name}")
                        info["requirements"] = new_requirements
                        info_json.seek(0)
                        info_json.truncate()
                        json.dump(info, info_json, indent=4)
                        info_json.write("\n")
