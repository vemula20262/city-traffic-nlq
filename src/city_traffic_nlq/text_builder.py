from __future__ import annotations


def create_crash_text(doc: dict) -> str:
    parts: list[str] = []

    for index in range(1, 6):
        factor = doc.get(f"CONTRIBUTING FACTOR VEHICLE {index}")
        if factor and str(factor) not in {"", "None", "Unspecified"}:
            parts.append(f"contributing factor: {factor}")

    for index in range(1, 6):
        vehicle = doc.get(f"VEHICLE TYPE CODE {index}")
        if vehicle and str(vehicle) not in {"", "None"}:
            parts.append(f"vehicle: {vehicle}")

    borough = doc.get("BOROUGH")
    if borough:
        parts.append(f"borough: {borough}")

    street = doc.get("ON STREET NAME")
    if street:
        parts.append(f"street: {street}")

    injured = int(float(doc.get("NUMBER OF PERSONS INJURED", 0) or 0))
    killed = int(float(doc.get("NUMBER OF PERSONS KILLED", 0) or 0))

    if killed > 0:
        parts.append("fatal crash")
    elif injured > 0:
        parts.append(f"injury crash with {injured} injured")
    else:
        parts.append("property damage only")

    return " | ".join(parts) if parts else "traffic collision"
