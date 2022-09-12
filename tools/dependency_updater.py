from __future__ import annotations

import json
import pathlib

import pkg_resources
import requests
from packaging.version import parse

__PYLAV_VERSION__ = "0.9.4.0"
__PYLAV_SHARED_VERSION__ = "0.4.4.0"

pylav_current_microversion = parse(__PYLAV_VERSION__)
pylavcogs_shared_current_micro_version = parse(__PYLAV_SHARED_VERSION__)

print(f"__PYLAV_VERSION__: {pylav_current_microversion}")
print(f"__PYLAV_SHARED_VERSION__: {pylavcogs_shared_current_micro_version}")

pylav_max_allowed_version = (
    f"{pylav_current_microversion.major}.{pylav_current_microversion.minor}.{pylav_current_microversion.micro+1}"
)
pylavcogs_shared_max_allowed_version = f"{pylavcogs_shared_current_micro_version.major}.{pylavcogs_shared_current_micro_version.minor}.{pylavcogs_shared_current_micro_version.micro+1}"

print(f"PyLav max version: {pylav_max_allowed_version}")
print(f"PyLavCogs-Shared max version: {pylavcogs_shared_max_allowed_version}")

pylav_requirement = pkg_resources.Requirement.parse(
    f"Py-Lav>={pylav_current_microversion},<{pylav_max_allowed_version}"
)
pylavcogs_shared_requirement = pkg_resources.Requirement.parse(
    f"pylavcogs-shared>={pylavcogs_shared_current_micro_version},<{pylavcogs_shared_max_allowed_version}"
)

print(f"Looking for most recent release matching: {pylav_requirement}")
print(f"Looking for most recent release matching: {pylavcogs_shared_requirement}")

pylav_data = requests.get("https://pypi.org/pypi/Py-Lav/json").json()["releases"]
pylavcogs_shared_data = requests.get("https://pypi.org/pypi/pylavcogs_shared/json").json()["releases"]


pylav_data_releases = {version for version, data in pylav_data.items() if data[0]["yanked"] is False}
pylavcogs_shared_releases = {version for version, data in pylavcogs_shared_data.items() if data[0]["yanked"] is False}
pylav_current_post_version = max(parse(i) for i in pylav_data_releases if pylav_requirement.specifier.contains(i))
pylavcogs_shared_current_post_version = max(
    parse(i) for i in pylavcogs_shared_releases if pylavcogs_shared_requirement.specifier.contains(i)
)


print(f"Most recent PyLav version: {max(parse(i) for i in pylav_data_releases)}")
print(f"Most recent PyLav version: {max(parse(i) for i in pylavcogs_shared_releases)}")

print(f"Most recent PyLav version in range: {pylav_current_post_version}")
print(f"Most recent PyLavCogs-Shared version in range: {pylavcogs_shared_current_post_version}")

new_pylav_version = f"Py-Lav>={pylav_current_post_version}<{pylav_max_allowed_version}"
new_pylavcogs_shared_version = (
    f"pylavcogs-shared>={pylavcogs_shared_current_post_version},<{pylavcogs_shared_max_allowed_version}"
)

print(f"New PyLav version range: {new_pylav_version}")
print(f"New PyLavCogs-Shared version range: {new_pylavcogs_shared_version}")


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
                        elif (
                            requirement.project_name == "pylavcogs-shared"
                            and requirement != new_pylavcogs_shared_version
                        ):
                            new_requirements.append(new_pylavcogs_shared_version)
                            changed = True
                        else:
                            new_requirements.append(requirement)
                    if changed:
                        print(f"Updating requirements for {cog.name}")
                        info["requirements"] = new_requirements
                        info_json.seek(0)
                        info_json.truncate()
                        json.dump(info, info_json, indent=4)
