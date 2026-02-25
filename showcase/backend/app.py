from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Dict, Iterable, List, Optional
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import numpy as np
from sentence_transformers import SentenceTransformer

app = Flask(__name__)
CORS(app)

# Global MongoDB connection
mongo_client = None
db = None
collection = None
embedding_model = None

# Database configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/?replicaSet=rs0")
MONGO_DB = os.getenv("MONGO_DB", "traffic")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "traffic")


def init_mongodb():
    """Initialize MongoDB connection via env-configured URI (local or Atlas)."""
    global mongo_client, db, collection
    if mongo_client is None:
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_client.admin.command("ping")
        db = mongo_client[MONGO_DB]
        collection = db[MONGO_COLLECTION]
    return collection


def init_embedding_model():
    """Initialize embedding model for vector search"""
    global embedding_model
    if embedding_model is None:
        print("Loading SentenceTransformer model...")
        try:
            embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
            print("✅ Embedding model loaded!")
        except Exception as e:
            print(f"❌ Error loading embedding model: {e}")
            print("⚠️  Vector search will not work without embedding model")
            return None
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
                if date_str:
                    self.reference_date = datetime.strptime(date_str, "%m/%d/%Y")
                else:
                    self.reference_date = datetime.now()
            except Exception as e:
                print(f"⚠️  Error parsing reference date: {e}")
                self.reference_date = datetime.now()
        else:
            self.reference_date = datetime.now()
        
        # Debug: Print reference date info
        print(f"📅 Reference date: {self.reference_date.strftime('%Y-%m-%d')} (Year: {self.reference_date.year})")
        
        # Get unique boroughs
        boroughs = self.collection.distinct("BOROUGH")
        self.boroughs = sorted([b for b in boroughs if b and str(b).strip()])
        self.boroughs.insert(0, "All")
        
        # Get available years from CRASH DATE field
        try:
            # Get sample of dates to extract years
            sample_docs = list(self.collection.find({"CRASH DATE": {"$exists": True, "$ne": None}}).limit(1000))
            years_set = set()
            for doc in sample_docs:
                date_str = doc.get("CRASH DATE", "")
                if date_str and "/" in date_str:
                    try:
                        # Extract year from "MM/DD/YYYY" format
                        parts = date_str.split("/")
                        if len(parts) == 3:
                            year = int(parts[2])
                            if 2000 <= year <= 2100:  # Valid year range
                                years_set.add(year)
                    except (ValueError, IndexError):
                        continue
            
            self.available_years = sorted(list(years_set), reverse=True)
            if not self.available_years:
                # Fallback: use reference date
                self.available_years = [self.reference_date.year, self.reference_date.year - 1]
            print(f"📅 Available years: {self.available_years}")
        except Exception as e:
            print(f"⚠️  Error getting years: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to reference date year and previous year
            self.available_years = [self.reference_date.year, self.reference_date.year - 1]
        
        # Get precincts (if PRECINCT field exists, otherwise return empty)
        self.precincts = []
        try:
            # Try different possible field names
            for field_name in ["PRECINCT", "PRECINCT CODE", "PRECINCT_CODE", "Precinct"]:
                try:
                    precincts = self.collection.distinct(field_name)
                    if precincts:
                        self.precincts = sorted([str(p) for p in precincts if p and str(p).strip() and str(p) != "None"])
                        if self.precincts:
                            print(f"📋 Found {len(self.precincts)} precincts in field '{field_name}'")
                            break
                except:
                    continue
        except Exception as e:
            print(f"⚠️  Error getting precincts: {e}")
        
        if not self.precincts:
            self.precincts = ["All"]  # Default if no precincts found
            print("⚠️  No precincts found, using 'All' only")
        
        # NLQ presets (keeping for compatibility, but we'll use vector search instead)
        self.nlq_presets = []

    def _filtered_records(
        self,
        start: datetime,
        end: datetime,
        borough: str,
    ) -> List[TrafficRecord]:
        """Query MongoDB for filtered records - optimized for performance"""
        query = {}
        
        # Borough filter
        if borough != "All":
            query["BOROUGH"] = borough.upper()
        
        # Get documents matching borough
        # We'll filter by date in Python since dates are stored as strings
        # Limit to reasonable number for performance (reduced for faster response)
        docs = list(self.collection.find(query).limit(15000))
        
        # Filter by exact date range
        filtered_docs = []
        for doc in docs:
            date_str = doc.get("CRASH DATE", "")
            if not date_str:
                continue
            try:
                crash_date = datetime.strptime(date_str, "%m/%d/%Y")
                if start <= crash_date <= end:
                    filtered_docs.append(doc)
            except (ValueError, TypeError):
                continue
        
        return [_doc_to_record(doc) for doc in filtered_docs]

    def get_period_bounds(self, selected_year: Optional[int] = None) -> Dict[str, Dict[str, datetime]]:
        """Get period bounds - returns full year data for last 4 years"""
        # Get last 4 years
        years_to_show = self.available_years[:4] if len(self.available_years) >= 4 else self.available_years
        
        periods = {
            "full_year": {
                "label": "Full Year",
                "years": {}
            }
        }
        
        # Add full year ranges for each year
        for year in years_to_show:
            year_start = datetime(year, 1, 1)
            year_end = datetime(year, 12, 31)
            # If it's the current year, cap at reference date
            if year == self.reference_date.year:
                year_end = self.reference_date
            
            periods["full_year"]["years"][str(year)] = {
                "start": year_start,
                "end": year_end
            }
        
        return periods

    @staticmethod
    def _shift_year(date: datetime, delta: int) -> datetime:
        try:
            return date.replace(year=date.year + delta)
        except ValueError:
            return date.replace(month=2, day=28, year=date.year + delta)

    def _generate_section_payload(self, borough: str, selected_year: Optional[int] = None) -> Dict[str, List[Dict]]:
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
        
        periods = self.get_period_bounds(selected_year)
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
        
        # Build cache for all years
        for period_id, period in periods.items():
            record_cache[period_id] = {}
            for year_str, year_range in period.get("years", {}).items():
                year_records = self._filtered_records(year_range["start"], year_range["end"], borough)
                record_cache[period_id][year_str] = year_records

        for section_id, section_label, metrics in section_metrics:
            section_rows = []
            for metric in metrics:
                row = {
                    "id": metric.id,
                    "label": metric.label,
                    "values": {},
                }
                for period_id, period in periods.items():
                    # Multi-year mode with delta calculations
                    year_values = {}
                    year_list = sorted([int(y) for y in period["years"].keys()], reverse=True)
                    
                    for i, year in enumerate(year_list):
                        year_str = str(year)
                        year_records = record_cache[period_id].get(year_str, [])
                        year_value = metric.compute(year_records)
                        year_values[year_str] = {
                            "value": year_value,
                            "delta": None
                        }
                        
                        # Calculate delta from previous year
                        if i < len(year_list) - 1:
                            prev_year = year_list[i + 1]
                            prev_year_str = str(prev_year)
                            prev_year_records = record_cache[period_id].get(prev_year_str, [])
                            prev_year_value = metric.compute(prev_year_records)
                            
                            if prev_year_value > 0:
                                delta = ((year_value - prev_year_value) / prev_year_value) * 100
                                year_values[year_str]["delta"] = round(delta, 1)
                            elif prev_year_value == 0 and year_value > 0:
                                # Use a special marker for infinite increase (JSON can't serialize float('inf'))
                                year_values[year_str]["delta"] = "inf"
                    
                    row["values"][period_id] = year_values
                section_rows.append(row)
            result.append({"id": section_id, "label": section_label, "rows": section_rows})

        return {"periods": periods, "sections": result}

    def build_sections(self, borough: str, selected_year: Optional[int] = None) -> Dict[str, List[Dict]]:
        return self._generate_section_payload(borough, selected_year)
    
    def get_metric_insights(self, borough: str, metric_id: str, selected_year: Optional[int] = None) -> Dict:
        """Get aggregated insights for a specific metric"""
        from collections import Counter
        from typing import Dict, List
        
        # Get period bounds to determine date range
        periods = self.get_period_bounds(selected_year)
        
        # Get all records for the selected years and borough
        all_records = []
        for period_id, period in periods.items():
            for year_str, year_range in period.get("years", {}).items():
                records = self._filtered_records(year_range["start"], year_range["end"], borough)
                all_records.extend(records)
        
        if not all_records:
            return {
                "total_incidents": 0,
                "top_contributing_factors": [],
                "top_streets": [],
                "top_zip_codes": [],
                "top_vehicle_types": [],
                "avg_injuries_per_incident": 0,
                "avg_fatalities_per_incident": 0,
            }
        
        # Filter records based on metric type
        filtered_records = []
        if "injury" in metric_id.lower() or "collision" in metric_id.lower():
            # For injury/collision metrics, include all records with injuries
            if "injury" in metric_id.lower():
                filtered_records = [r for r in all_records if r.persons_injured > 0]
            else:
                filtered_records = all_records
        elif "fatality" in metric_id.lower() or "killed" in metric_id.lower():
            # For fatality metrics, include all records with fatalities
            filtered_records = [r for r in all_records if r.persons_killed > 0]
        elif "pedestrian" in metric_id.lower():
            filtered_records = [r for r in all_records if r.pedestrians_injured > 0 or r.pedestrians_killed > 0]
        elif "bicycle" in metric_id.lower() or "cyclist" in metric_id.lower():
            filtered_records = [r for r in all_records if r.cyclists_injured > 0 or r.cyclists_killed > 0]
        elif "motor" in metric_id.lower() or "vehicle" in metric_id.lower():
            filtered_records = [r for r in all_records if r.motorists_injured > 0 or r.motorists_killed > 0]
        else:
            filtered_records = all_records
        
        if not filtered_records:
            return {
                "total_incidents": 0,
                "top_contributing_factors": [],
                "top_streets": [],
                "top_zip_codes": [],
                "top_vehicle_types": [],
                "avg_injuries_per_incident": 0,
                "avg_fatalities_per_incident": 0,
            }
        
        # Aggregate statistics
        total_incidents = len(filtered_records)
        
        # Top contributing factors
        all_factors = []
        for record in filtered_records:
            if record.contributing_factors:
                all_factors.extend(record.contributing_factors)
        factor_counts = Counter(all_factors)
        top_factors = [{"factor": factor, "count": count} for factor, count in factor_counts.most_common(5)]
        
        # Top streets (on_street)
        street_counts = Counter(
            r.on_street for r in filtered_records 
            if r.on_street and r.on_street.strip() and r.on_street.upper() not in ["", "NONE", "UNKNOWN"]
        )
        top_streets = [{"street": street, "count": count} for street, count in street_counts.most_common(5)]
        
        # Top zip codes
        zip_counts = Counter(
            r.zip_code for r in filtered_records 
            if r.zip_code and str(r.zip_code).strip()
        )
        top_zips = [{"zip": str(zip_code), "count": count} for zip_code, count in zip_counts.most_common(5)]
        
        # Top vehicle types
        all_vehicles = []
        for record in filtered_records:
            if record.vehicles:
                all_vehicles.extend(record.vehicles)
        vehicle_counts = Counter(all_vehicles)
        top_vehicles = [{"vehicle": vehicle, "count": count} for vehicle, count in vehicle_counts.most_common(5)]
        
        # Average injuries and fatalities per incident
        total_injuries = sum(r.persons_injured for r in filtered_records)
        total_fatalities = sum(r.persons_killed for r in filtered_records)
        avg_injuries = round(total_injuries / total_incidents, 2) if total_incidents > 0 else 0
        avg_fatalities = round(total_fatalities / total_incidents, 2) if total_incidents > 0 else 0
        
        return {
            "total_incidents": total_incidents,
            "top_contributing_factors": top_factors,
            "top_streets": top_streets,
            "top_zip_codes": top_zips,
            "top_vehicle_types": top_vehicles,
            "avg_injuries_per_incident": avg_injuries,
            "avg_fatalities_per_incident": avg_fatalities,
            "total_injuries": total_injuries,
            "total_fatalities": total_fatalities,
        }

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
        
        # Only get documents with valid location (GeoJSON Point)
        query["LOCATION.type"] = "Point"
        
        # Also check for documents with LATITUDE and LONGITUDE as fallback
        docs = list(
            self.collection.find(query)
            .sort("CRASH DATE", -1)
            .limit(limit)
        )
        
        # If we don't have enough with GeoJSON, try with LATITUDE/LONGITUDE
        if len(docs) < limit:
            alt_query = {}
            if borough != "All":
                alt_query["BOROUGH"] = borough.upper()
            alt_query["LATITUDE"] = {"$exists": True, "$ne": None, "$ne": 0}
            alt_query["LONGITUDE"] = {"$exists": True, "$ne": None, "$ne": 0}
            alt_query["LOCATION.type"] = {"$ne": "Point"}  # Exclude ones we already got
            alt_docs = list(
                self.collection.find(alt_query)
                .sort("CRASH DATE", -1)
                .limit(limit - len(docs))
            )
            # Add unique documents
            existing_ids = {str(d.get("_id")) for d in docs}
            for doc in alt_docs:
                if str(doc.get("_id")) not in existing_ids:
                    docs.append(doc)
        
        results = []
        for doc in docs:
            latitude = None
            longitude = None
            
            # Try GeoJSON first
            location = doc.get("LOCATION")
            if location and isinstance(location, dict) and location.get("type") == "Point":
                coords = location.get("coordinates", [])
                if len(coords) >= 2:
                    longitude = float(coords[0])
                    latitude = float(coords[1])
            
            # Fallback to LATITUDE/LONGITUDE fields
            if latitude is None or longitude is None:
                lat_val = doc.get("LATITUDE")
                lon_val = doc.get("LONGITUDE")
                if lat_val and lon_val:
                    try:
                        latitude = float(lat_val)
                        longitude = float(lon_val)
                        # Validate coordinates (not 0,0)
                        if latitude == 0 and longitude == 0:
                            continue
                    except (ValueError, TypeError):
                        continue
            
            if latitude is not None and longitude is not None:
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
                    "latitude": latitude,
                    "longitude": longitude,
                    "borough": (doc.get("BOROUGH") or "Unknown").title(),
                    "injuries": int(doc.get("NUMBER OF PERSONS INJURED", 0) or 0),
                    "fatalities": int(doc.get("NUMBER OF PERSONS KILLED", 0) or 0),
                })
        
        return results

    def vector_search(self, query_text: str, limit: int = 10) -> Dict:
        """Perform vector search using embeddings"""
        model = init_embedding_model()
        
        if model is None:
            return {
                "queryText": query_text,
                "error": "Embedding model not available. Vector search is disabled.",
                "totalMatches": 0,
                "columns": [],
                "rows": [],
                "mapIncidents": [],
            }
        
        # Generate query embedding
        query_embedding = model.encode(query_text)
        query_vector = np.array(query_embedding)
        query_dim = len(query_vector)
        
        # Get documents with embeddings
        docs_with_embeddings = list(
            self.collection.find(
                {"crash_text_embedding": {"$exists": True, "$ne": None}}
            ).limit(5000)  # Limit for performance
        )
        
        # Calculate cosine similarity - filter out documents with wrong dimensions
        similarities = []
        skipped_count = 0
        for doc in docs_with_embeddings:
            try:
                doc_embedding = doc.get("crash_text_embedding")
                if not doc_embedding:
                    continue
                
                doc_vec = np.array(doc_embedding)
                
                # Check if dimensions match
                if len(doc_vec) != query_dim:
                    skipped_count += 1
                    continue
                
                # Calculate cosine similarity
                dot_product = np.dot(query_vector, doc_vec)
                query_norm = np.linalg.norm(query_vector)
                doc_norm = np.linalg.norm(doc_vec)
                
                if query_norm == 0 or doc_norm == 0:
                    continue
                
                similarity = dot_product / (query_norm * doc_norm)
                similarities.append((similarity, doc))
            except Exception as e:
                # Skip documents with invalid embeddings
                skipped_count += 1
                continue
        
        # Log skipped documents (only if significant number)
        if skipped_count > 10:
            print(f"⚠️  Skipped {skipped_count} documents with invalid or mismatched embeddings")
        
        if not similarities:
            return {
                "queryText": query_text,
                "error": f"No documents with valid embeddings found. Query dimension: {query_dim}. Skipped {skipped_count} documents with mismatched dimensions.",
                "totalMatches": 0,
                "columns": [],
                "rows": [],
                "mapIncidents": [],
            }
        
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
        
        for i, record in enumerate(records):
            # Get crash_text from original document
            original_doc = top_docs[i]
            crash_text = original_doc.get("crash_text", "") if original_doc else ""
            
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
                "description": crash_text,
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
                {"id": "description", "label": "Description"},
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
    
    # Get precincts filtered by borough if provided
    borough = request.args.get("borough", None)
    precincts = data_store.precincts
    
    if borough and borough != "All":
        # Filter precincts by borough
        try:
            query = {"BOROUGH": borough.upper()}
            # Try to get distinct precincts for this borough
            borough_precincts = data_store.collection.distinct("PRECINCT", query)
            if not borough_precincts:
                borough_precincts = data_store.collection.distinct("PRECINCT CODE", query)
            if borough_precincts:
                precincts = sorted([str(p) for p in borough_precincts if p and str(p).strip()])
                if not precincts:
                    precincts = ["All"]
            else:
                precincts = ["All"]
        except:
            precincts = ["All"]
    
    return jsonify(
        {
            "boroughs": data_store.boroughs,
            "precincts": precincts,
            "years": data_store.available_years,
            "nlqQueries": data_store.nlq_presets,
        }
    )


@app.route("/api/traffic-stats")
def traffic_stats():
    if not data_store:
        return jsonify({"error": "Database not available"}), 500
    
    try:
        borough = request.args.get("borough", "All")
        year_param = request.args.get("year")
        selected_year = int(year_param) if year_param and year_param.isdigit() else None
        
        print(f"📊 Building stats for borough={borough}, year={selected_year}")
        sections_payload = data_store.build_sections(borough, selected_year)
        
        response = {
            "referenceDate": data_store.reference_date.strftime("%Y-%m-%d"),
            "availableYears": data_store.available_years,
            "selectedYear": selected_year,
            "borough": borough,
            "sections": sections_payload.get("sections", []),
            "periods": {
                period_id: {
                    "label": period.get("label", "Full Year"),
                    "years": {
                        year_str: {
                            "start": year_range["start"].strftime("%Y-%m-%d"),
                            "end": year_range["end"].strftime("%Y-%m-%d"),
                        }
                        for year_str, year_range in period.get("years", {}).items()
                    }
                }
                for period_id, period in sections_payload.get("periods", {}).items()
            },
        }
        print(f"✅ Stats built: {len(response['sections'])} sections, {len(response['periods'])} periods")
        return jsonify(response)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Error in traffic_stats: {error_details}")
        return jsonify({"error": str(e), "details": error_details}), 500


@app.route("/api/incidents")
def incidents():
    if not data_store:
        return jsonify({"error": "Database not available"}), 500
    borough = request.args.get("borough", "All")
    return jsonify({"items": data_store.recent_incidents(borough)})


@app.route("/api/metric-insights")
def metric_insights():
    if not data_store:
        return jsonify({"error": "Database not available"}), 500
    
    try:
        borough = request.args.get("borough", "All")
        metric_id = request.args.get("metric_id", "")
        year_param = request.args.get("year")
        selected_year = int(year_param) if year_param and year_param.isdigit() else None
        
        print(f"📊 Metric insights request: borough={borough}, metric_id={metric_id}, year={selected_year}")
        
        if not metric_id:
            print("❌ Missing metric_id parameter")
            return jsonify({"error": "metric_id is required"}), 400
        
        print(f"🔍 Computing insights for metric: {metric_id}")
        insights = data_store.get_metric_insights(borough, metric_id, selected_year)
        print(f"✅ Insights computed: {len(insights.get('top_contributing_factors', []))} factors, {insights.get('total_incidents', 0)} incidents")
        return jsonify(insights)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Error in metric_insights: {error_details}")
        return jsonify({"error": str(e), "details": error_details}), 500


@app.route("/api/vector-search", methods=["POST"])
def vector_search():
    """Vector search endpoint"""
    if not data_store:
        return jsonify({"error": "Database not available"}), 500
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Request body is required"}), 400
        
        query_text = data.get("query", "").strip()
        
        if not query_text:
            return jsonify({"error": "Query text is required"}), 400
        
        limit = int(data.get("limit", 10))
        
        result = data_store.vector_search(query_text, limit=limit)
        
        # Check if result has an error
        if "error" in result:
            return jsonify(result), 500
        
        return jsonify(result)
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Vector search error: {error_details}")
        return jsonify({"error": f"Vector search failed: {str(e)}"}), 500


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
    app.run(
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )

