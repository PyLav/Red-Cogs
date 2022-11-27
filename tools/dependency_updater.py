from __future__ import annotations

import json
import pathlib

import pkg_resources
import requests
from packaging.version import parse

__PYLAV_VERSION__ = "1.0.0.0"

pylav_current_minor_version = parse(__PYLAV_VERSION__)

print(f"__PYLAV_VERSION__: {pylav_current_minor_version}")

pylav_threshold_version = f"{pylav_current_minor_version.major}.{pylav_current_minor_version.minor + 1}"

print(f"PyLav max version: {pylav_threshold_version}")

pylav_requirement = pkg_resources.Requirement.parse(f"Py-Lav>={pylav_current_minor_version},<{pylav_threshold_version}")


print(f"Looking for most recent release matching: {pylav_requirement}")

pylav_data = requests.get("https://pypi.org/pypi/Py-Lav/json").json()["releases"]


pylav_data_releases = {version for version, data in pylav_data.items() if data[0]["yanked"] is False}
pylav_latest_compatible_version = max(parse(i) for i in pylav_data_releases if pylav_requirement.specifier.contains(i))


print(f"Most recent PyLav version: {max(parse(i) for i in pylav_data_releases)}")

print(f"Most recent PyLav version in range: {pylav_latest_compatible_version}")

new_pylav_version = f"Py-Lav>={pylav_latest_compatible_version}<{pylav_threshold_version}"

print(f"New PyLav version range: {new_pylav_version}")


for cog in pathlib.Path(__file__).parent.parent.iterdir():
    if cog.is_dir():
        cog_json = cog / "info.json"
        if cog_json.exists():
            with cog_json.open("r+") as info_json:
                info = json.load(info_json)
                if info["requirements"]:
                    new_requirements = []
                    changed = False
                    for requirement in info["requirements"]:
                        requirement = pkg_resources.Requirement.parse(requirement)
                        if requirement.project_name == "Py-Lav" and requirement != new_pylav_version:
                            new_requirements.append(new_pylav_version)
                            changed = True
                        else:
                            new_requirements.append(requirement)
                    if changed:
                        print(f"Updating requirements for {cog.name}")
                        info["requirements"] = new_requirements
                        info_json.seek(0)
                        info_json.truncate()
                        json.dump(info, info_json, indent=4)
                        info_json.write("\n")
