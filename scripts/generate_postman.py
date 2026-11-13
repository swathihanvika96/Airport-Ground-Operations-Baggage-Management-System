"""Generate postman/airport_ground_operations_collection.json from the live OpenAPI schema.

    python scripts/generate_postman.py

Folder "0. End-to-End Demo" runs the mandatory demo in order (Collection Runner) and stores ids/tokens
in collection variables. The remaining folders contain every endpoint grouped by tag.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.main import app  # noqa: E402

SPEC = app.openapi()
SCHEMAS = SPEC["components"]["schemas"]
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "postman",
                   "airport_ground_operations_collection.json")


def resolve(schema):
    while "$ref" in schema:
        schema = SCHEMAS[schema["$ref"].split("/")[-1]]
    return schema


def example(schema, name=""):
    schema = resolve(schema)
    if "anyOf" in schema:
        options = [s for s in schema["anyOf"] if s.get("type") != "null"]
        return example(options[0], name) if options else None
    if "default" in schema and schema["default"] is not None:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        props, req = schema.get("properties", {}), set(schema.get("required", []))
        return {k: example(v, k) for k, v in props.items() if k in req or ("default" in resolve(v))}
    if t == "array":
        return [example(schema.get("items", {}), name)]
    if t == "integer":
        return 1
    if t == "number":
        return 10.5
    if t == "boolean":
        return True
    fmt = schema.get("format")
    if fmt == "date-time":
        return "2030-01-01T10:00:00Z"
    if fmt == "date":
        return "2030-01-01"
    if fmt == "email":
        return "user@example.com"
    return f"<{name or 'string'}>"


def request_item(path, method, op):
    url_path = path.replace("{", ":").replace("}", "")
    body = None
    content = op.get("requestBody", {}).get("content", {})
    if "application/json" in content:
        body = {"mode": "raw", "raw": json.dumps(example(content["application/json"]["schema"]), indent=2),
                "options": {"raw": {"language": "json"}}}
    elif "application/x-www-form-urlencoded" in content:
        body = {"mode": "urlencoded", "urlencoded": [{"key": "username", "value": "{{admin_email}}"},
                                                     {"key": "password", "value": "{{admin_password}}"}]}
    params = [p for p in op.get("parameters", []) if p["in"] == "query"]
    path_vars = [{"key": p["name"], "value": "1"} for p in op.get("parameters", []) if p["in"] == "path"]
    item = {
        "name": op.get("summary") or op.get("operationId"),
        "request": {
            "method": method.upper(),
            "header": [{"key": "Content-Type", "value": "application/json"}] if body and body["mode"] == "raw" else [],
            "url": {"raw": "{{base_url}}" + url_path, "host": ["{{base_url}}"],
                    "path": [s for s in url_path.split("/") if s],
                    "query": [{"key": p["name"], "value": "", "disabled": True,
                               "description": p.get("description", "")} for p in params],
                    "variable": path_vars},
        },
    }
    if body:
        item["request"]["body"] = body
    if not op.get("security") and path.endswith(("/auth/token", "/auth/login", "/auth/register",
                                                   "/auth/refresh", "/auth/forgot-password",
                                                   "/auth/reset-password")) or "oauth/google" in path:
        item["request"]["auth"] = {"type": "noauth"}
    return item


def demo_step(name, method, path, body=None, save=None, form=None, expect=200):
    tests = [f"pm.test('{name} -> {expect}', () => pm.response.to.have.status({expect}));"]
    for var, expr in (save or {}).items():
        tests.append(f"pm.collectionVariables.set('{var}', pm.response.json(){expr});")
    req = {"method": method, "header": [],
           "url": {"raw": "{{base_url}}" + path, "host": ["{{base_url}}"], "path": [s for s in path.split("/") if s]}}
    if body is not None:
        req["header"] = [{"key": "Content-Type", "value": "application/json"}]
        req["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2), "options": {"raw": {"language": "json"}}}
    if form:
        req["body"] = {"mode": "urlencoded", "urlencoded": [{"key": k, "value": v} for k, v in form.items()]}
        req["auth"] = {"type": "noauth"}
    return {"name": name, "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": tests}}],
            "request": req}


def demo_folder():
    v = "/api/v1"
    dep = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)
    steps = [
        demo_step("1. Admin login (OAuth2 token)", "POST", f"{v}/auth/token",
                  form={"username": "{{admin_email}}", "password": "{{admin_password}}"},
                  save={"access_token": ".access_token", "refresh_token": ".refresh_token"}),
        demo_step("2a. Register airport (departure)", "POST", f"{v}/airports", {
            "code": "{{dep_code}}", "name": "Demo Departure Airport", "city": "Bengaluru", "country": "India"},
            save={"airport_id": ".id"}, expect=201),
        demo_step("2b. Register airport (arrival)", "POST", f"{v}/airports", {
            "code": "{{arr_code}}", "name": "Demo Arrival Airport", "city": "Goa", "country": "India"},
            save={"arrival_airport_id": ".id"}, expect=201),
        demo_step("3. Create terminal", "POST", f"{v}/terminals", {
            "airport_id": "{{airport_id}}", "code": "T1", "name": "Terminal 1", "capacity": 4000},
            save={"terminal_id": ".id"}, expect=201),
        demo_step("3b. Register gate", "POST", f"{v}/gates", {"terminal_id": "{{terminal_id}}", "gate_number": "A5"},
                  save={"gate_id": ".id"}, expect=201),
        demo_step("3c. Register check-in counter", "POST", f"{v}/counters",
                  {"terminal_id": "{{terminal_id}}", "counter_number": "C01"}, save={"counter_id": ".id"}, expect=201),
        demo_step("4. Register flight", "POST", f"{v}/flights", {
            "flight_number": "AI501", "airline_name": "Air India", "airline_code": "AI", "aircraft_type": "A320neo",
            "departure_airport_id": "{{airport_id}}", "arrival_airport_id": "{{arrival_airport_id}}",
            "departure_terminal_id": "{{terminal_id}}", "scheduled_departure": dep.isoformat(),
            "scheduled_arrival": (dep + timedelta(minutes=80)).isoformat()}, save={"flight_id": ".id"}, expect=201),
        demo_step("5. Assign gate", "POST", f"{v}/gates/{{{{gate_id}}}}/assign", {"flight_id": "{{flight_id}}"},
                  expect=201),
        demo_step("5b. Assign counter", "POST", f"{v}/counters/{{{{counter_id}}}}/assign",
                  {"flight_id": "{{flight_id}}"}, expect=201),
        demo_step("5c. Open check-in", "PATCH", f"{v}/flights/{{{{flight_id}}}}/status", {"status": "CHECK_IN_OPEN"}),
        demo_step("6. Register passenger (synthetic) + map to flight", "POST", f"{v}/passengers", {
            "first_name": "Asha", "last_name": "Synthetic", "id_type": "PASSPORT",
            "id_reference": "SYN{{$randomInt}}{{$randomInt}}", "flight_id": "{{flight_id}}"},
            save={"passenger_id": ".id"}, expect=201),
        demo_step("7-8. Check-in + boarding pass reference", "POST", f"{v}/checkin",
                  {"passenger_id": "{{passenger_id}}", "flight_id": "{{flight_id}}", "seat_number": "14C"},
                  save={"checkin_id": ".checkin.id", "boarding_pass_ref": ".boarding_pass.reference"}, expect=201),
        demo_step("9. Register baggage", "POST", f"{v}/baggage",
                  {"passenger_id": "{{passenger_id}}", "flight_id": "{{flight_id}}", "weight_kg": 18.5,
                   "category": "CHECKED"}, save={"baggage_id": ".id", "tag_number": ".tag_number"}, expect=201),
        demo_step("10a. Baggage check-in completed", "PATCH", f"{v}/baggage/{{{{baggage_id}}}}/status",
                  {"status": "CHECKIN_COMPLETED", "location": "Counter C01"}),
        demo_step("10b. Complete screening", "POST", f"{v}/baggage/{{{{baggage_id}}}}/screenings",
                  {"result": "CLEARED", "machine_id": "XR-2", "remarks": "Clear"}, expect=201),
        demo_step("11a. Track: sorting", "PATCH", f"{v}/baggage/{{{{baggage_id}}}}/status",
                  {"status": "SORTING", "location": "Sorter 3"}),
        demo_step("11b. Track: loaded", "PATCH", f"{v}/baggage/{{{{baggage_id}}}}/status",
                  {"status": "LOADED", "location": "Hold 2"}),
        demo_step("11c. Track by tag", "GET", f"{v}/baggage/track/{{{{tag_number}}}}"),
        demo_step("12a. Register ground staff", "POST", f"{v}/ground-staff", {
            "employee_code": "GS{{$randomInt}}", "full_name": "Ravi Kumar", "department": "RAMP_OPERATIONS",
            "designation": "Ramp Agent", "skills": ["loading"]}, save={"staff_id": ".id"}, expect=201),
        demo_step("12b. Assign ground staff to flight", "POST", f"{v}/resources/allocate", {
            "resource_type": "STAFF", "resource_id": "{{staff_id}}", "flight_id": "{{flight_id}}",
            "role_description": "Ramp lead"}, expect=201),
        demo_step("12c. Create & assign ground task", "POST", f"{v}/ground-tasks", {
            "flight_id": "{{flight_id}}", "task_type": "BAGGAGE_LOADING", "priority": "HIGH",
            "assigned_staff_id": "{{staff_id}}"}, save={"task_id": ".id"}, expect=201),
        demo_step("13a. Create turnaround", "POST", f"{v}/turnarounds",
                  {"flight_id": "{{flight_id}}", "parking_stand": "S7"},
                  save={"turnaround_id": ".id", "activity_arrival_id": ".activities[0].id"}, expect=201),
        demo_step("13b. Start aircraft arrival activity", "POST",
                  f"{v}/turnarounds/{{{{turnaround_id}}}}/activities/{{{{activity_arrival_id}}}}/start",
                  {"assigned_team": "Team Alpha"}),
        demo_step("13c. Complete aircraft arrival activity", "POST",
                  f"{v}/turnarounds/{{{{turnaround_id}}}}/activities/{{{{activity_arrival_id}}}}/complete", {}),
        demo_step("14a. Register equipment", "POST", f"{v}/equipment", {
            "equipment_code": "TUG-{{$randomInt}}", "name": "Pushback Tug", "equipment_type": "AIRCRAFT_TUG"},
            save={"equipment_id": ".id"}, expect=201),
        demo_step("14b. Allocate equipment", "POST", f"{v}/equipment-assignments",
                  {"equipment_id": "{{equipment_id}}", "flight_id": "{{flight_id}}"}, expect=201),
        demo_step("15. Record flight delay", "POST", f"{v}/delays", {
            "flight_id": "{{flight_id}}", "delay_category": "GROUND_OPERATIONS", "reason": "Late fuel bowser",
            "delay_minutes": 25, "responsible_department": "FUEL_SERVICES"}, expect=201),
        demo_step("16a. Update flight status: BOARDING", "PATCH", f"{v}/flights/{{{{flight_id}}}}/status",
                  {"status": "BOARDING"}),
        demo_step("16b. Board passenger", "POST", f"{v}/checkin/{{{{checkin_id}}}}/board"),
        demo_step("16c. Update flight status: DEPARTED", "PATCH", f"{v}/flights/{{{{flight_id}}}}/status",
                  {"status": "DEPARTED"}),
        demo_step("17. View dashboard", "GET", f"{v}/dashboard/overview"),
        demo_step("18a. Daily flight operations report", "GET", f"{v}/reports/flights/daily"),
        demo_step("18b. Delay analysis report (CSV)", "GET", f"{v}/reports/delays/analysis?format=csv"),
        demo_step("19. Verify audit logs for flight", "GET", f"{v}/audit-logs/entity/flight/{{{{flight_id}}}}"),
    ]
    return {"name": "0. End-to-End Demo (run in order)", "item": steps,
            "description": "Run with the Collection Runner on a fresh DB (or change dep_code/arr_code)."}


def build():
    folders: dict[str, list] = {}
    for path, methods in SPEC["paths"].items():
        for method, op in methods.items():
            tag = (op.get("tags") or ["Other"])[0]
            folders.setdefault(tag, []).append(request_item(path, method, op))
    collection = {
        "info": {"name": "Airport Ground Operations & Baggage Management API",
                 "description": "Generated from OpenAPI. Login via '1. Admin login' (sets {{access_token}}).",
                 "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"},
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{access_token}}", "type": "string"}]},
        "variable": [{"key": k, "value": val} for k, val in {
            "base_url": "http://localhost:8000", "admin_email": "admin@airportops.com",
            "admin_password": "Admin@12345", "access_token": "", "dep_code": "DMA", "arr_code": "DMB"}.items()],
        "item": [demo_folder()] + [{"name": t, "item": items} for t, items in folders.items()],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(collection, fh, indent=2)
    total = sum(len(i) for i in folders.values())
    print(f"Wrote {OUT}: {total} endpoints in {len(folders)} folders + demo")


if __name__ == "__main__":
    build()
