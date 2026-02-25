from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional
import sys
import os

from flask import Flask, jsonify, request
from pymongo import MongoClient
import numpy as np
from fastembed import TextEmbedding

# Add parent directory to path to import connection script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from connect_mongodb_ec2 import connect_to_mongodb

app = Flask(__name__)

# Global MongoDB connection
tunnel = None
mongo_client = None
db = None
collection = None
embedding_model = None

# Database configuration
MONGO_DB = "traffic"
MONGO_COLLECTION = "traffic"


def init_mongodb():
    """Initialize MongoDB connection"""
    global tunnel, mongo_client, db, collection
    if mongo_client is None:
        tunnel, mongo_client, db, collection = connect_to_mongodb(test_connection=False)
        if not mongo_client:
            raise Exception("Failed to connect to MongoDB")
    return collection


def init_embedding_model():
    """Initialize embedding model for vector search"""
    global embedding_model
    if embedding_model is None:
        print("Loading FastEmbed model...")
        embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        print("✅ Embedding model loaded!")
    return embedding_model


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


def _doc_to_record(doc: dict) -> TrafficRecord:
    """Convert MongoDB document to TrafficRecord"""
    # Parse date
    date_str = doc.get("CRASH DATE", "")
    try:
        crash_date = datetime.strptime(date_str, "%m/%d/%Y")
    except (ValueError, TypeError):
        crash_date = datetime.now()
    
    # Get vehicles
    vehicles = []
    for i in range(1, 6):
        vehicle = doc.get(f"VEHICLE TYPE CODE {i}")
        if vehicle and str(vehicle).strip() and str(vehicle).upper() not in ["", "None"]:
            vehicles.append(str(vehicle).strip().upper())
    
    # Get contributing factors
    factors = []
    for i in range(1, 6):
        factor = doc.get(f"CONTRIBUTING FACTOR VEHICLE {i}")
        if factor and str(factor).strip() and str(factor) not in ["", "None", "Unspecified"]:
            factors.append(str(factor).strip().upper())
    
    primary_factor = factors[0] if factors else "Unspecified"
    
    # Get coordinates from LOCATION field (GeoJSON)
    latitude = None
    longitude = None
    location = doc.get("LOCATION")
    if location and isinstance(location, dict) and location.get("type") == "Point":
        coords = location.get("coordinates", [])
        if len(coords) >= 2:
            longitude = float(coords[0])
            latitude = float(coords[1])
    
    # Fallback to LATITUDE/LONGITUDE fields
    if latitude is None:
        lat_val = doc.get("LATITUDE")
        if lat_val:
            try:
                latitude = float(lat_val)
            except (ValueError, TypeError):
                pass
    
    if longitude is None:
        lon_val = doc.get("LONGITUDE")
        if lon_val:
            try:
                longitude = float(lon_val)
            except (ValueError, TypeError):
                pass
    
    def safe_int(value):
        try:
            return int(value) if value is not None else 0
        except (ValueError, TypeError):
            return 0
    
    return TrafficRecord(
        date=crash_date,
        borough=(doc.get("BOROUGH") or "Unknown").upper(),
        zip_code=doc.get("ZIP CODE") or None,
        latitude=latitude,
        longitude=longitude,
        on_street=doc.get("ON STREET NAME") or None,
        cross_street=doc.get("CROSS STREET NAME") or None,
        off_street=doc.get("OFF STREET NAME") or None,
        persons_injured=safe_int(doc.get("NUMBER OF PERSONS INJURED")),
        persons_killed=safe_int(doc.get("NUMBER OF PERSONS KILLED")),
        pedestrians_injured=safe_int(doc.get("NUMBER OF PEDESTRIANS INJURED")),
        pedestrians_killed=safe_int(doc.get("NUMBER OF PEDESTRIANS KILLED")),
        cyclists_injured=safe_int(doc.get("NUMBER OF CYCLIST INJURED")),
        cyclists_killed=safe_int(doc.get("NUMBER OF CYCLIST KILLED")),
        motorists_injured=safe_int(doc.get("NUMBER OF MOTORIST INJURED")),
        motorists_killed=safe_int(doc.get("NUMBER OF MOTORIST KILLED")),
        vehicles=vehicles,
        collision_id=str(doc.get("COLLISION_ID", "unknown")),
        primary_factor=primary_factor,
        contributing_factors=factors,
    )


class TrafficDataStore:
    def __init__(self):
        self.collection = init_mongodb()
        # Get reference date from most recent document
        latest_doc = self.collection.find_one(sort=[("CRASH DATE", -1)])
        if latest_doc:
            try:
                date_str = latest_doc.get("CRASH DATE", "")
                self.reference_date = datetime.strptime(date_str, "%m/%d/%Y")
            except:
                self.reference_date = datetime.now()
        else:
            self.reference_date = datetime.now()
        
        # Get unique boroughs
        boroughs = self.collection.distinct("BOROUGH")
        self.boroughs = sorted([b for b in boroughs if b and str(b).strip()])
        self.boroughs.insert(0, "All")
        
        # NLQ presets (keeping for compatibility, but we'll use vector search instead)
        self.nlq_presets = []

    def _filtered_records(
        self,
        start: datetime,
        end: datetime,
        borough: str,
    ) -> List[TrafficRecord]:
        """Query MongoDB for filtered records"""
        query = {}
        
        # Date range - MongoDB stores dates as strings in "MM/DD/YYYY" format
        # We need to compare strings, but for proper ordering we convert to comparable format
        start_str = start.strftime("%m/%d/%Y")
        end_str = end.strftime("%m/%d/%Y")
        
        # For string comparison, we need to ensure proper format
        # Since dates are stored as "MM/DD/YYYY", we can do string comparison
        query["CRASH DATE"] = {"$gte": start_str, "$lte": end_str}
        
        # Borough filter
        if borough != "All":
            query["BOROUGH"] = borough.upper()
        
        docs = list(self.collection.find(query).limit(10000))  # Limit for performance
        return [_doc_to_record(doc) for doc in docs]

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
            return date.replace(month=2, day=28, year=date.year + delta)

    def _generate_section_payload(self, borough: str) -> Dict[str, List[Dict]]:
        # Import metric classes
        from dataclasses import dataclass
        from typing import Iterable
        
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
            "MOPED", "MOTORCYCLE", "SCOOTER", "ELECTRIC SCOOTER",
            "E-BIKE", "MOTORBIKE", "VESPA",
        }
        
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
        """Get recent incidents from MongoDB"""
        query = {}
        
        # Filter by borough
        if borough != "All":
            query["BOROUGH"] = borough.upper()
        
        # Only get documents with valid location
        query["LOCATION.type"] = "Point"
        
        docs = list(
            self.collection.find(query)
            .sort("CRASH DATE", -1)
            .limit(limit)
        )
        
        results = []
        for doc in docs:
            location = doc.get("LOCATION")
            if location and isinstance(location, dict) and location.get("type") == "Point":
                coords = location.get("coordinates", [])
                if len(coords) >= 2:
                    # Convert date from MM/DD/YYYY to YYYY-MM-DD
                    date_str = doc.get("CRASH DATE", "")
                    try:
                        if "/" in date_str:
                            parts = date_str.split("/")
                            if len(parts) == 3:
                                formatted_date = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
                            else:
                                formatted_date = date_str
                        else:
                            formatted_date = date_str
                    except:
                        formatted_date = date_str
                    
                    results.append({
                        "collisionId": str(doc.get("COLLISION_ID", "")),
                        "date": formatted_date,
                        "latitude": float(coords[1]),
                        "longitude": float(coords[0]),
                        "borough": (doc.get("BOROUGH") or "Unknown").title(),
                        "injuries": int(doc.get("NUMBER OF PERSONS INJURED", 0) or 0),
                        "fatalities": int(doc.get("NUMBER OF PERSONS KILLED", 0) or 0),
                    })
        
        return results

    def vector_search(self, query_text: str, limit: int = 10) -> Dict:
        """Perform vector search using embeddings"""
        model = init_embedding_model()
        
        # Generate query embedding
        query_embedding = list(model.embed([query_text]))[0]
        query_vector = np.array(query_embedding).tolist()
        
        # Perform vector search using $vectorSearch (MongoDB Atlas) or manual cosine similarity
        # Since we're using self-hosted MongoDB, we'll use aggregation with manual similarity
        
        # Get documents with embeddings
        pipeline = [
            {
                "$match": {
                    "crash_text_embedding": {"$exists": True, "$ne": None}
                }
            },
            {
                "$addFields": {
                    "similarity": {
                        "$let": {
                            "vars": {
                                "dotProduct": {
                                    "$reduce": {
                                        "input": {"$range": [0, {"$size": "$crash_text_embedding"}]},
                                        "initialValue": 0,
                                        "in": {
                                            "$add": [
                                                "$$value",
                                                {
                                                    "$multiply": [
                                                        {"$arrayElemAt": ["$crash_text_embedding", "$$this"]},
                                                        {"$arrayElemAt": [query_vector, "$$this"]}
                                                    ]
                                                }
                                            ]
                                        }
                                    }
                                },
                                "queryNorm": {
                                    "$sqrt": {
                                        "$reduce": {
                                            "input": query_vector,
                                            "initialValue": 0,
                                            "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}
                                        }
                                    }
                                },
                                "docNorm": {
                                    "$sqrt": {
                                        "$reduce": {
                                            "input": "$crash_text_embedding",
                                            "initialValue": 0,
                                            "in": {"$add": ["$$value", {"$multiply": ["$$this", "$$this"]}]}
                                        }
                                    }
                                }
                            },
                            "as": "sim",
                            "in": {
                                "$divide": [
                                    "$$sim.dotProduct",
                                    {"$multiply": ["$$sim.queryNorm", "$$sim.docNorm"]}
                                ]
                            }
                        }
                    }
                }
            },
            {"$sort": {"similarity": -1}},
            {"$limit": limit}
        ]
        
        # For better performance, use Python-based cosine similarity
        docs_with_embeddings = list(
            self.collection.find(
                {"crash_text_embedding": {"$exists": True, "$ne": None}}
            ).limit(5000)  # Limit for performance
        )
        
        # Calculate cosine similarity
        query_vec = np.array(query_vector)
        similarities = []
        for doc in docs_with_embeddings:
            doc_vec = np.array(doc["crash_text_embedding"])
            similarity = np.dot(query_vec, doc_vec) / (np.linalg.norm(query_vec) * np.linalg.norm(doc_vec))
            similarities.append((similarity, doc))
        
        # Sort by similarity and get top results
        similarities.sort(key=lambda x: x[0], reverse=True)
        top_docs = [doc for _, doc in similarities[:limit]]
        
        # Convert to records and format response
        records = [_doc_to_record(doc) for doc in top_docs]
        
        def prettify_borough(value: str) -> str:
            if value == "UNKNOWN":
                return "Unknown"
            return value.title()
        
        rows = []
        map_incidents = []
        
        for record in records:
            rows.append({
                "collisionId": record.collision_id,
                "date": record.date.strftime("%Y-%m-%d"),
                "borough": prettify_borough(record.borough),
                "location": record.on_street
                or record.off_street
                or (record.cross_street or "Location not reported"),
                "injuries": record.persons_injured,
                "fatalities": record.persons_killed,
                "factor": record.primary_factor,
            })
            
            if record.latitude and record.longitude:
                map_incidents.append({
                    "collisionId": record.collision_id,
                    "date": record.date.strftime("%Y-%m-%d"),
                    "latitude": record.latitude,
                    "longitude": record.longitude,
                    "borough": prettify_borough(record.borough),
                    "injuries": record.persons_injured,
                    "fatalities": record.persons_killed,
                })
        
        return {
            "queryText": query_text,
            "totalMatches": len(similarities),
            "columns": [
                {"id": "date", "label": "Crash Date"},
                {"id": "borough", "label": "Borough"},
                {"id": "location", "label": "Location"},
                {"id": "injuries", "label": "Injuries"},
                {"id": "fatalities", "label": "Fatalities"},
                {"id": "factor", "label": "Primary Factor"},
            ],
            "rows": rows,
            "mapIncidents": map_incidents,
        }


# Initialize data store
try:
    data_store = TrafficDataStore()
    print("✅ MongoDB data store initialized")
except Exception as e:
    print(f"❌ Failed to initialize MongoDB: {e}")
    data_store = None


@app.after_request
def apply_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/filters")
def filters():
    if not data_store:
        return jsonify({"error": "Database not available"}), 500
    return jsonify(
        {
            "boroughs": data_store.boroughs,
            "precincts": ["All"],
            "nlqQueries": data_store.nlq_presets,
        }
    )


@app.route("/api/traffic-stats")
def traffic_stats():
    if not data_store:
        return jsonify({"error": "Database not available"}), 500
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
    if not data_store:
        return jsonify({"error": "Database not available"}), 500
    borough = request.args.get("borough", "All")
    return jsonify({"items": data_store.recent_incidents(borough)})


@app.route("/api/vector-search", methods=["POST"])
def vector_search():
    """Vector search endpoint"""
    if not data_store:
        return jsonify({"error": "Database not available"}), 500
    
    data = request.get_json()
    query_text = data.get("query", "").strip()
    
    if not query_text:
        return jsonify({"error": "Query text is required"}), 400
    
    limit = int(data.get("limit", 10))
    
    try:
        result = data_store.vector_search(query_text, limit=limit)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/nlq")
def nlq_query():
    """Legacy endpoint - redirects to vector search"""
    query_id = request.args.get("queryId")
    if query_id:
        return jsonify({"error": "Preset queries not supported. Use vector search instead."}), 400
    return jsonify({"error": "queryId is required"}), 400


@app.route("/")
def health_check():
    return jsonify({"status": "ok", "mongodb": "connected" if data_store else "disconnected"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)

