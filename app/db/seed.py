"""Seed synthetic demo data:  python -m app.db.seed

Creates one user per role (password: Passw0rd!), airports, terminals, gates, counters, flights,
passengers, ground staff and equipment. Safe to re-run (skips if the demo airport exists).
"""
from datetime import timedelta

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.db.init_db import ensure_superuser
from app.models import (
    Airport, CheckInCounter, Equipment, Flight, Gate, GroundStaff, Passenger, PassengerFlight, Terminal, User,
)
from app.utils.datetime_utils import utcnow
from app.utils.enums import (
    Department, EquipmentType, GateType, IdentificationType, Shift, TravelClass, UserRole,
)
from app.utils.reference_generator import booking_reference

DEMO_PASSWORD = "Passw0rd!"


def run() -> None:
    db = SessionLocal()
    try:
        ensure_superuser(db)
        if db.query(Airport).filter_by(code="BLR").first():
            print("Demo data already present - skipping")
            return
        users = {}
        for role in UserRole:
            if role == UserRole.SUPER_ADMIN:
                continue
            uname = role.value.lower()
            u = User(email=f"{uname}@airportops.com", username=uname, full_name=role.value.replace("_", " ").title(),
                     hashed_password=hash_password(DEMO_PASSWORD), role=role, is_active=True, is_verified=True)
            db.add(u)
            users[role] = u
        blr = Airport(code="BLR", icao_code="VOBL", name="Kempegowda International Airport", city="Bengaluru",
                      state="Karnataka", country="India", timezone="Asia/Kolkata", latitude=13.1986, longitude=77.7066)
        bom = Airport(code="BOM", icao_code="VABB", name="Chhatrapati Shivaji Maharaj International Airport",
                      city="Mumbai", state="Maharashtra", country="India", timezone="Asia/Kolkata")
        goi = Airport(code="GOI", icao_code="VOGO", name="Goa International Airport", city="Dabolim", state="Goa",
                      country="India", timezone="Asia/Kolkata")
        db.add_all([blr, bom, goi])
        db.flush()
        t1 = Terminal(airport_id=blr.id, code="T1", name="Terminal 1", capacity=4000)
        t2 = Terminal(airport_id=blr.id, code="T2", name="Terminal 2", capacity=6000, is_international=True)
        db.add_all([t1, t2])
        db.flush()
        for i in range(1, 7):
            db.add(Gate(terminal_id=t1.id, gate_number=f"A{i}", gate_type=GateType.DOMESTIC))
            db.add(Gate(terminal_id=t2.id, gate_number=f"B{i}", gate_type=GateType.INTERNATIONAL))
        for i in range(1, 9):
            db.add(CheckInCounter(terminal_id=t1.id, counter_number=f"C{i:02d}"))
        now = utcnow().replace(minute=0, second=0)
        flights = []
        for n, (dest, hrs) in enumerate([(bom, 3), (goi, 4), (bom, 6), (goi, 8)], start=1):
            f = Flight(flight_number=f"AI{500 + n}", airline_name="Air India", airline_code="AI",
                       aircraft_type="A320neo", aircraft_registration=f"VT-EX{n}", seat_capacity=180,
                       departure_airport_id=blr.id, arrival_airport_id=dest.id, departure_terminal_id=t1.id,
                       scheduled_departure=now + timedelta(hours=hrs),
                       scheduled_arrival=now + timedelta(hours=hrs + 1, minutes=40))
            db.add(f)
            flights.append(f)
        db.flush()
        first_names = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Saanvi", "Vihaan", "Anaya", "Ishaan", "Tara"]
        for i, fn in enumerate(first_names):
            p = Passenger(first_name=fn, last_name="Testpassenger", email=f"{fn.lower()}@example.com",
                          phone=f"+91-90000{i:05d}", nationality="Indian", id_type=IdentificationType.PASSPORT,
                          id_reference=f"SYN{100000 + i}")
            db.add(p)
            db.flush()
            db.add(PassengerFlight(passenger_id=p.id, flight_id=flights[i % len(flights)].id,
                                   booking_reference=booking_reference(),
                                   travel_class=TravelClass.BUSINESS if i % 5 == 0 else TravelClass.ECONOMY))
        sup = GroundStaff(employee_code="GS001", full_name="Ravi Supervisor", department=Department.RAMP_OPERATIONS,
                          designation="Ramp Supervisor", skills=["supervision", "marshalling"], shift=Shift.MORNING,
                          user_id=users[UserRole.GROUND_STAFF_SUPERVISOR].id)
        db.add(sup)
        db.flush()
        crew = [("GS002", "Asha Loader", Department.BAGGAGE_HANDLING, "Baggage Handler", ["loading", "unloading"],
                 users[UserRole.BAGGAGE_HANDLING_STAFF].id),
                ("GS003", "Vikram Cleaner", Department.AIRCRAFT_SERVICES, "Cabin Cleaner", ["cleaning"], None),
                ("GS004", "Neha Fuel", Department.FUEL_SERVICES, "Fuel Coordinator", ["refueling"], None),
                ("GS005", "Arjun Tech", Department.MAINTENANCE, "Aircraft Technician", ["inspection"],
                 users[UserRole.MAINTENANCE_STAFF].id)]
        for code, name, dept, desig, skills, uid in crew:
            db.add(GroundStaff(employee_code=code, full_name=name, department=dept, designation=desig, skills=skills,
                               shift=Shift.MORNING, supervisor_id=sup.id, user_id=uid))
        for code, name, etype in [("CART-01", "Baggage Cart 1", EquipmentType.BAGGAGE_CART),
                                  ("CART-02", "Baggage Cart 2", EquipmentType.BAGGAGE_CART),
                                  ("GPU-01", "Ground Power Unit 1", EquipmentType.GROUND_POWER_UNIT),
                                  ("TUG-01", "Pushback Tug 1", EquipmentType.AIRCRAFT_TUG),
                                  ("STAIR-01", "Passenger Stairs 1", EquipmentType.PASSENGER_STAIRS),
                                  ("LOAD-01", "Belt Loader 1", EquipmentType.LOADING_EQUIPMENT)]:
            db.add(Equipment(equipment_code=code, name=name, equipment_type=etype, airport_id=blr.id,
                             terminal_id=t1.id, next_maintenance_date=(now + timedelta(days=30)).date()))
        db.commit()
        print(f"Seeded demo data. Role users: <role>@airportops.com / {DEMO_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
