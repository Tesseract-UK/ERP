"""Seed the database with reference data and demo users.

Run:  python -m app.seed
Safe to re-run: it skips seeding if users already exist.
"""
from datetime import date

from .database import Base, SessionLocal, engine
from .models import (
    Department, Designation, Holiday, LeavePolicy, Location, Shift, User,
)
from .security import hash_password

DEFAULT_POLICIES = {
    "casual": 12, "sick": 10, "earned": 15, "unpaid": 0, "maternity": 182,
    "paternity": 15, "optional_holiday": 2, "wfh": 24,
}

HOLIDAYS_2026 = [
    (date(2026, 1, 1), "New Year's Day", "company"),
    (date(2026, 1, 26), "Republic Day", "national"),
    (date(2026, 3, 4), "Holi", "national"),
    (date(2026, 8, 15), "Independence Day", "national"),
    (date(2026, 10, 2), "Gandhi Jayanti", "national"),
    (date(2026, 11, 8), "Diwali", "national"),
    (date(2026, 12, 25), "Christmas", "national"),
]


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(User).count():
            print("Database already seeded — skipping.")
            return

        engineering = Department(name="Engineering")
        hr_dept = Department(name="Human Resources")
        ops = Department(name="Operations")
        db.add_all([engineering, hr_dept, ops])

        des_eng = Designation(title="Software Engineer")
        des_lead = Designation(title="Engineering Manager")
        des_hr = Designation(title="HR Executive")
        des_admin = Designation(title="System Administrator")
        db.add_all([des_eng, des_lead, des_hr, des_admin])

        hq = Location(name="Head Office", address="Bengaluru, India")
        general = Shift(name="General", start_time="09:00", end_time="18:00")
        db.add_all([hq, general])
        db.flush()

        for leave_type, allocation in DEFAULT_POLICIES.items():
            db.add(LeavePolicy(leave_type=leave_type, annual_allocation=allocation))
        for d, name, kind in HOLIDAYS_2026:
            db.add(Holiday(date=d, name=name, holiday_type=kind))

        def make_user(code, email, name, role, dept, des, manager=None, dob=None):
            u = User(employee_code=code, email=email, full_name=name, role=role,
                     password_hash=hash_password("Password@123"),
                     department_id=dept.id, designation_id=des.id,
                     location_id=hq.id, shift_id=general.id,
                     manager_id=manager.id if manager else None,
                     joining_date=date(2025, 1, 15), date_of_birth=dob)
            db.add(u)
            db.flush()
            return u

        admin = make_user("EMP0001", "admin@tesseract.com", "Aarav Sharma", "admin",
                          ops, des_admin, dob=date(1988, 5, 12))
        hr_user = make_user("EMP0002", "hr@tesseract.com", "Priya Nair", "hr",
                            hr_dept, des_hr, manager=admin, dob=date(1992, 8, 21))
        manager = make_user("EMP0003", "manager@tesseract.com", "Rahul Verma", "manager",
                            engineering, des_lead, manager=admin, dob=date(1990, 8, 10))
        make_user("EMP0004", "employee@tesseract.com", "Sneha Iyer", "employee",
                  engineering, des_eng, manager=manager, dob=date(1996, 8, 5))
        make_user("EMP0005", "dev2@tesseract.com", "Karan Patel", "employee",
                  engineering, des_eng, manager=manager, dob=date(1995, 2, 18))

        db.commit()
        print("Seeded demo data. All demo accounts use password: Password@123")
        print("  admin@tesseract.com / hr@tesseract.com / manager@tesseract.com / "
              "employee@tesseract.com / dev2@tesseract.com")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
