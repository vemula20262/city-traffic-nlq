from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional

from flask import Flask, jsonify, request

DATA_FILE = Path(__file__).resolve().parent.parent / "sample.csv"

app = Flask(__name__)


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


@dataclass
class TrafficRecord:
    date: datetime
    borough: str
    zip_code: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    on_street: Optional[str]
    cross_street: Optional[str]
    off_street: Optional[str]
    persons_injured: int
    persons_killed: int
    pedestrians_injured: int
    pedestrians_killed: int
    cyclists_injured: int
    cyclists_killed: int
    motorists_injured: int
    motorists_killed: int
    vehicles: List[str]
    collision_id: str
    primary_factor: str
    contributing_factors: List[str]


@dataclass
class MetricConfig:
    id: str
    label: str

    def compute(self, records: Iterable[TrafficRecord]) -> int:
        raise NotImplementedError


class SumMetric(MetricConfig):
    def __init__(self, id: str, label: str, value_getter):
        super().__init__(id, label)
        self.value_getter = value_getter

    def compute(self, records: Iterable[TrafficRecord]) -> int:
        return sum(self.value_getter(record) for record in records)


TWO_WHEELER_KEYWORDS = {
    "MOPED",
    "MOTORCYCLE",
    "SCOOTER",
    "ELECTRIC SCOOTER",
    "E-BIKE",
    "MOTORBIKE",
    "VESPA",
}


def _has_coordinates(record: TrafficRecord) -> bool:
    return record.latitude is not None and record.longitude is not None


def _factor_equals(record: TrafficRecord, value: str) -> bool:
    upper = value.upper()
    return any(factor == upper for factor in record.contributing_factors)


NLQ_TABLE_COLUMNS = [
    {"id": "date", "label": "Crash Date"},
    {"id": "borough", "label": "Borough"},
    {"id": "location", "label": "Location"},
    {"id": "injuries", "label": "Injuries"},
    {"id": "fatalities", "label": "Fatalities"},
    {"id": "factor", "label": "Primary Factor"},
]


def _brooklyn_injury(record: TrafficRecord) -> bool:
    return (
        record.borough == "BROOKLYN"
        and record.persons_injured > 0
        and _has_coordinates(record)
    )


def _bronx_injury(record: TrafficRecord) -> bool:
    return (
        record.borough == "BRONX"
        and record.persons_injured > 0
        and _has_coordinates(record)
    )


def _passing_too_closely(record: TrafficRecord) -> bool:
    return _has_coordinates(record) and _factor_equals(record, "Passing Too Closely")


NLQ_PRESETS: Dict[str, Dict[str, object]] = {
    "brooklyn_injury_collisions": {
        "label": "Show the latest injury collisions in Brooklyn",
        "description": "Filters recent Brooklyn crashes where at least one person was injured and plots them on the map.",
        "predicate": _brooklyn_injury,
        "limit": 6,
    },
    "bronx_injury_collisions": {
        "label": "Highlight Bronx collisions that caused injuries",
        "description": "Returns Bronx collisions with reported injuries to compare hotspots outside Brooklyn.",
        "predicate": _bronx_injury,
        "limit": 6,
    },
    "passing_too_closely_citywide": {
        "label": "Find collisions caused by passing too closely",
        "description": "Surfaces citywide crashes where 'Passing Too Closely' was cited as a contributing factor.",
        "predicate": _passing_too_closely,
        "limit": 10,
    },
}


class TrafficDataStore:
    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.records: List[TrafficRecord] = []
        self._load()
        self.reference_date: datetime = max(record.date for record in self.records)
        self.boroughs = sorted({record.borough for record in self.records if record.borough})
        self.boroughs.insert(0, "All")
        self.nlq_presets = [
            {
                "id": key,
                "label": value["label"],
                "description": value["description"],
            }
            for key, value in NLQ_PRESETS.items()
        ]
        self.mock_collections = self._build_mock_collections()

    def _load(self) -> None:
        import csv

        with self.data_file.open(newline="", encoding="utf-8-sig") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                date_str = row.get("CRASH DATE")
                if not date_str:
                    continue
                try:
                    crash_date = datetime.strptime(date_str, "%m/%d/%Y")
                except ValueError:
                    continue

                vehicles = [
                    row.get(column, "")
                    for column in (
                        "VEHICLE TYPE CODE 1",
                        "VEHICLE TYPE CODE 2",
                        "VEHICLE TYPE CODE 3",
                        "VEHICLE TYPE CODE 4",
                        "VEHICLE TYPE CODE 5",
                    )
                ]

                factors = [
                    row.get(column, "")
                    for column in (
                        "CONTRIBUTING FACTOR VEHICLE 1",
                        "CONTRIBUTING FACTOR VEHICLE 2",
                        "CONTRIBUTING FACTOR VEHICLE 3",
                        "CONTRIBUTING FACTOR VEHICLE 4",
                        "CONTRIBUTING FACTOR VEHICLE 5",
                    )
                ]
                cleaned_factors = [factor.strip() for factor in factors if factor and factor.strip()]
                primary_factor = cleaned_factors[0] if cleaned_factors else "Unspecified"

                def to_float(number: str) -> Optional[float]:
                    try:
                        return float(number)
                    except (TypeError, ValueError):
                        return None

                record = TrafficRecord(
                    date=crash_date,
                    borough=(row.get("BOROUGH") or "Unknown").upper(),
                    zip_code=row.get("ZIP CODE") or None,
                    latitude=to_float(row.get("LATITUDE")),
                    longitude=to_float(row.get("LONGITUDE")),
                    on_street=row.get("ON STREET NAME") or None,
                    cross_street=row.get("CROSS STREET NAME") or None,
                    off_street=row.get("OFF STREET NAME") or None,
                    persons_injured=_safe_int(row.get("NUMBER OF PERSONS INJURED")),
                    persons_killed=_safe_int(row.get("NUMBER OF PERSONS KILLED")),
                    pedestrians_injured=_safe_int(row.get("NUMBER OF PEDESTRIANS INJURED")),
                    pedestrians_killed=_safe_int(row.get("NUMBER OF PEDESTRIANS KILLED")),
                    cyclists_injured=_safe_int(row.get("NUMBER OF CYCLIST INJURED")),
                    cyclists_killed=_safe_int(row.get("NUMBER OF CYCLIST KILLED")),
                    motorists_injured=_safe_int(row.get("NUMBER OF MOTORIST INJURED")),
                    motorists_killed=_safe_int(row.get("NUMBER OF MOTORIST KILLED")),
                    vehicles=[vehicle.strip().upper() for vehicle in vehicles if vehicle and vehicle.strip()],
                    collision_id=row.get("COLLISION_ID", "unknown"),
                    primary_factor=primary_factor,
                    contributing_factors=[factor.upper() for factor in cleaned_factors],
                )
                self.records.append(record)

    def _filtered_records(
        self,
        start: datetime,
        end: datetime,
        borough: str,
    ) -> List[TrafficRecord]:
        lower = borough.upper()
        return [
            record
            for record in self.records
            if start <= record.date <= end
            and (borough == "All" or record.borough == lower)
        ]

    def get_period_bounds(self) -> Dict[str, Dict[str, datetime]]:
        reference = self.reference_date
        periods = {
            "week_to_date": {
                "label": "Week to Date",
                "start": reference - timedelta(days=6),
                "end": reference,
            },
            "twenty_eight_day": {
                "label": "28 Day",
                "start": reference - timedelta(days=27),
                "end": reference,
            },
            "year_to_date": {
                "label": "Year to Date",
                "start": reference.replace(month=1, day=1),
                "end": reference,
            },
        }
        for period in periods.values():
            period["previous_start"] = self._shift_year(period["start"], -1)
            period["previous_end"] = self._shift_year(period["end"], -1)
        return periods

    @staticmethod
    def _shift_year(date: datetime, delta: int) -> datetime:
        try:
            return date.replace(year=date.year + delta)
        except ValueError:
            # Handle February 29th gracefully by stepping back to the 28th
            return date.replace(month=2, day=28, year=date.year + delta)

    def _generate_section_payload(self, borough: str) -> Dict[str, List[Dict]]:
        periods = self.get_period_bounds()
        section_metrics = [
            (
                "collisions",
                "Collisions",
                [
                    SumMetric("collisions_total", "Collisions", lambda _: 1),
                    SumMetric(
                        "injury_collisions",
                        "Injury Collisions",
                        lambda record: 1 if record.persons_injured > 0 else 0,
                    ),
                SumMetric("total_injuries", "Total Injuries", lambda record: record.persons_injured),
                SumMetric("motor_vehicle_injuries", "Motor Vehicle+", lambda record: record.motorists_injured),
                SumMetric("pedestrian_injuries", "Pedestrian", lambda record: record.pedestrians_injured),
                SumMetric("bicycle_injuries", "Traditional Bicycle", lambda record: record.cyclists_injured),
                SumMetric(
                    "two_wheeler_collisions",
                    "Motorized Two-Wheeler+",
                    lambda record: 1
                    if any(vehicle in TWO_WHEELER_KEYWORDS for vehicle in record.vehicles)
                    else 0,
                ),
                ],
            ),
            (
                "fatalities",
                "Fatalities",
                [
                    SumMetric("total_fatalities", "Total Fatalities", lambda record: record.persons_killed),
                    SumMetric(
                        "motor_vehicle_fatalities",
                        "Motor Vehicle+",
                        lambda record: record.motorists_killed,
                ),
                SumMetric(
                    "pedestrian_fatalities",
                    "Pedestrian",
                    lambda record: record.pedestrians_killed,
                ),
                SumMetric(
                    "bicycle_fatalities",
                    "Traditional Bicycle",
                    lambda record: record.cyclists_killed,
                ),
                SumMetric(
                    "two_wheeler_fatalities",
                    "Motorized Two-Wheeler+",
                    lambda record: record.persons_killed
                    if any(vehicle in TWO_WHEELER_KEYWORDS for vehicle in record.vehicles)
                    else 0,
                ),
                ],
            ),
        ]

        result = []
        record_cache: Dict[str, Dict[str, List[TrafficRecord]]] = {}
        for period_id, period in periods.items():
            record_cache[period_id] = {
                "current": self._filtered_records(period["start"], period["end"], borough),
                "previous": self._filtered_records(
                    period["previous_start"], period["previous_end"], borough
                ),
            }

        for section_id, section_label, metrics in section_metrics:
            section_rows = []
            for metric in metrics:
                row = {
                    "id": metric.id,
                    "label": metric.label,
                    "values": {},
                }
                for period_id, period in periods.items():
                    current_records = record_cache[period_id]["current"]
                    previous_records = record_cache[period_id]["previous"]
                    current_value = metric.compute(current_records)
                    previous_value = metric.compute(previous_records)
                    row["values"][period_id] = self._format_period_value(current_value, previous_value)
                section_rows.append(row)
            result.append({"id": section_id, "label": section_label, "rows": section_rows})

        return {"periods": periods, "sections": result}

    def build_sections(self, borough: str) -> Dict[str, List[Dict]]:
        return self._generate_section_payload(borough)

    def _build_mock_collections(self) -> Dict[str, List[Dict]]:
        collections = {
            "collisions_summary": [],
            "fatalities_summary": [],
            "incidents": self.recent_incidents("All", limit=len(self.records)),
        }

        for borough in self.boroughs:
            payload = self._generate_section_payload(borough)
            for section in payload["sections"]:
                target_key = (
                    "collisions_summary" if section["id"] == "collisions" else "fatalities_summary"
                )
                for row in section["rows"]:
                    for period_id, values in row["values"].items():
                        collections[target_key].append(
                            {
                                "borough": borough,
                                "section": section["label"],
                                "metricId": row["id"],
                                "metricLabel": row["label"],
                                "period": period_id,
                                "currentYear": self.reference_date.year,
                                "previousYear": self.reference_date.year - 1,
                                "values": values,
                            }
                        )

        return collections

    @staticmethod
    def _format_period_value(current: int, previous: int) -> Dict[str, Optional[float]]:
        change = None
        if previous:
            change = round(((current - previous) / previous) * 100, 1)
        return {
            "current": current,
            "previous": previous,
            "percentChange": change,
        }

    def recent_incidents(self, borough: str, limit: int = 100) -> List[Dict]:
        incidents = [
            record
            for record in self.records
            if record.latitude is not None and record.longitude is not None
            and (borough == "All" or record.borough == borough.upper())
        ]
        incidents.sort(key=lambda record: record.date, reverse=True)
        return [
            {
                "collisionId": record.collision_id,
                "date": record.date.strftime("%Y-%m-%d"),
                "latitude": record.latitude,
                "longitude": record.longitude,
                "borough": record.borough,
                "injuries": record.persons_injured,
                "fatalities": record.persons_killed,
            }
            for record in incidents[:limit]
        ]

    def run_nlq_query(self, query_id: str) -> Optional[Dict]:
        preset = NLQ_PRESETS.get(query_id)
        if not preset:
            return None

        predicate: Callable[[TrafficRecord], bool] = preset["predicate"]  # type: ignore[index]
        limit = preset.get("limit", 10)  # type: ignore[index]
        filtered = [record for record in self.records if predicate(record)]

        if not filtered:
            return {
                "queryId": query_id,
                "queryText": preset["label"],
                "description": preset["description"],
                "totalMatches": 0,
                "columns": NLQ_TABLE_COLUMNS,
                "rows": [],
                "mapIncidents": [],
            }

        filtered.sort(key=lambda record: record.date, reverse=True)
        selected = filtered[:limit]

        def prettify_borough(value: str) -> str:
            if value == "UNKNOWN":
                return "Unknown"
            return value.title()

        rows = [
            {
                "collisionId": record.collision_id,
                "date": record.date.strftime("%Y-%m-%d"),
                "borough": prettify_borough(record.borough),
                "location": record.on_street
                or record.off_street
                or (record.cross_street or "Location not reported"),
                "injuries": record.persons_injured,
                "fatalities": record.persons_killed,
                "factor": record.primary_factor,
            }
            for record in selected
        ]

        map_incidents = [
            {
                "collisionId": record.collision_id,
                "date": record.date.strftime("%Y-%m-%d"),
                "latitude": record.latitude,
                "longitude": record.longitude,
                "borough": prettify_borough(record.borough),
                "injuries": record.persons_injured,
                "fatalities": record.persons_killed,
            }
            for record in selected
            if record.latitude is not None and record.longitude is not None
        ]

        return {
            "queryId": query_id,
            "queryText": preset["label"],
            "description": preset["description"],
            "totalMatches": len(filtered),
            "columns": NLQ_TABLE_COLUMNS,
            "rows": rows,
            "mapIncidents": map_incidents,
        }


data_store = TrafficDataStore(DATA_FILE)


@app.after_request
def apply_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return response


@app.route("/api/filters")
def filters():
    return jsonify(
        {
            "boroughs": data_store.boroughs,
            "precincts": ["All"],
            "nlqQueries": data_store.nlq_presets,
        }
    )


@app.route("/api/traffic-stats")
def traffic_stats():
    borough = request.args.get("borough", "All")
    sections_payload = data_store.build_sections(borough)
    response = {
        "referenceDate": data_store.reference_date.strftime("%Y-%m-%d"),
        "currentYear": data_store.reference_date.year,
        "previousYear": data_store.reference_date.year - 1,
        "borough": borough,
        "sections": sections_payload["sections"],
        "periods": {
            period_id: {
                "label": period["label"],
                "start": period["start"].strftime("%Y-%m-%d"),
                "end": period["end"].strftime("%Y-%m-%d"),
            }
            for period_id, period in sections_payload["periods"].items()
        },
    }
    return jsonify(response)


@app.route("/api/incidents")
def incidents():
    borough = request.args.get("borough", "All")
    return jsonify({"items": data_store.recent_incidents(borough)})


@app.route("/api/nlq")
def nlq_query():
    query_id = request.args.get("queryId")
    if not query_id:
        return jsonify({"error": "queryId is required"}), 400

    result = data_store.run_nlq_query(query_id)
    if result is None:
        return jsonify({"error": f"Unknown query: {query_id}"}), 404
    return jsonify(result)


@app.route("/api/mock-collections")
def mock_collections():
    return jsonify(data_store.mock_collections)


@app.route("/")
def health_check():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
