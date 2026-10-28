"""Fictional charge histories for the demo records database.

Every person is invented: the face is a synthetic FLUXSynID identity (CC BY-NC 4.0) and the
name, alias, marks and cases are drawn at random from the lists below. Areas and police
stations are real Bengaluru localities so the demo reads naturally; the cases are not."""

import random
from datetime import date, timedelta

from sqlmodel import Session, select

from backend.models import RecordCharge, RecordPerson

STATUSES = ("under_investigation", "charge_sheeted", "convicted", "acquitted")

MALE = ["Ravi", "Suresh", "Manjunath", "Arjun", "Imran", "Karthik", "Venkatesh", "Mahesh", "Prakash", "Anand",
        "Sandeep", "Rahul", "Faisal", "Naveen", "Girish", "Srinivas", "Abdul", "Joseph", "Harish", "Deepak",
        "Santosh", "Raghu", "Mohan", "Vijay", "Sunil", "Ajay", "Kiran", "Salman", "Praveen", "Nagaraj"]
FEMALE = ["Lakshmi", "Priya", "Kavya", "Asha", "Fathima", "Divya", "Rekha", "Meena", "Shilpa", "Anitha",
          "Pooja", "Sowmya", "Nandini", "Ayesha", "Geetha", "Mary", "Swathi", "Radha", "Bhavya", "Sunitha"]
SURNAMES = ["Kumar", "Gowda", "Reddy", "Shetty", "Naik", "Rao", "Khan", "Sharma", "Patil", "Hegde", "Nair",
            "Iyer", "Pasha", "D'Souza", "Murthy", "Babu", "Singh", "Shaikh", "Pillai", "Yadav", "Prasad", "Achar"]
ALIASES = ["Kencha", "Tiger", "Chotu", "Bonda", "Kaalia", "Pappu", "Guddu", "Sultan", "Babloo", "Raja", "Bhai",
           "Kariya", "Long", "Silent", "Gunda", "Puttu", "Bullet", "Scooter", "Kitty", "Rani", "Chikka", "Dabba"]
AREAS = ["Hebbal", "Yelahanka", "Whitefield", "Indiranagar", "Koramangala", "Jayanagar", "Malleshwaram",
         "Rajajinagar", "Banashankari", "K R Puram", "Marathahalli", "HSR Layout", "Shivajinagar", "Upparpet",
         "Electronic City", "Kengeri", "Yeshwanthpur", "R T Nagar", "Hennur", "Madiwala"]
MARKS = ["scar on left cheek", "scar above right eyebrow", "mole above upper lip", "mole on right side of nose",
         "tattoo of a trident on right forearm", "tattoo 'Amma' on left forearm", "burn mark on left hand",
         "missing upper front tooth", "cut mark on chin", "tattoo of a scorpion on neck", "pierced left ear",
         "birthmark on right temple", "stitch mark on forehead", "tattoo of a heart on right hand"]
BUILDS = ["slim", "medium", "athletic", "heavy", "stocky"]
# (BNS section, offence, weight): thefts and snatching far more common than violent crime
OFFENCES = [
    ("303(2)", "Theft", 20), ("304", "Snatching (chain/mobile)", 14), ("305", "Theft in a dwelling house", 8),
    ("331(4)", "House-breaking by night", 7), ("317(2)", "Receiving stolen property", 7),
    ("309(4)", "Robbery", 6), ("318(4)", "Cheating", 8), ("316(2)", "Criminal breach of trust", 4),
    ("115(2)", "Voluntarily causing hurt", 9), ("118(1)", "Hurt by a dangerous weapon", 4),
    ("117(2)", "Grievous hurt", 3), ("351(2)", "Criminal intimidation", 6), ("324(4)", "Mischief", 4),
    ("336(2)", "Forgery", 3), ("78", "Stalking", 2), ("109", "Attempt to murder", 2), ("103(1)", "Murder", 1),
    ("310(2)", "Dacoity", 1), ("NDPS 20(b)", "Possession of ganja", 5),
]


def _age(band: str | None, rng: random.Random) -> int:
    lo = int(band[:2]) if band and band[:2].isdigit() else 25
    return rng.randint(max(lo, 19), lo + 9)


def _status(fir: date, rng: random.Random) -> str:
    years = (date(2026, 10, 28) - fir).days / 365
    if years < 1:
        return rng.choice(["under_investigation"] * 3 + ["charge_sheeted"])
    if years < 3:
        return rng.choice(["under_investigation", "charge_sheeted", "charge_sheeted", "convicted", "acquitted"])
    return rng.choice(["charge_sheeted", "convicted", "convicted", "convicted", "acquitted", "acquitted"])


def seed_records(session: Session, faces: list[dict], seed: int = 7) -> int:
    """One fictional person per face, with 1-6 cases. Idempotent: faces already used are skipped.
    Returns how many people were added."""
    rng = random.Random(seed)
    existing = session.exec(select(RecordPerson)).all()
    used = {p.source for p in existing}
    next_no = len(existing) + 1
    fir_seq: dict[str, int] = {}
    added = 0
    weights = [w for *_, w in OFFENCES]
    for face in faces:
        source = f"FLUXSynID {face['id']}"
        # draw for every face, so a face's record is the same however many were seeded before
        male = (face.get("gender") or "").lower().startswith("m")
        first = rng.choice(MALE if male else FEMALE)
        name = f"{first} {rng.choice(SURNAMES)}"
        alias = rng.choice(ALIASES) if rng.random() < 0.45 else None
        home = rng.choice(AREAS)
        marks = ", ".join(rng.sample(MARKS, rng.choice([0, 1, 1, 2])))
        height = rng.randint(162, 186) if male else rng.randint(148, 170)
        build = rng.choice(BUILDS)
        age = _age(face.get("age"), rng)
        # repeat offenders tend to stick to one kind of crime and to nearby stations
        habit = rng.choices(OFFENCES, weights)[0]
        cases = []
        for _ in range(rng.choice([1, 1, 1, 2, 2, 3, 4, 6])):
            off = habit if rng.random() < 0.6 else rng.choices(OFFENCES, weights)[0]
            area = home if rng.random() < 0.6 else rng.choice(AREAS)
            when = date(2026, 10, 1) - timedelta(days=rng.randint(10, min(age - 18, 11) * 365))
            cases.append((off, area, when, _status(when, rng)))
        if source in used:
            continue
        person = RecordPerson(
            record_no=f"BLR-CR-{next_no:05d}", name=name, alias=alias, gender="male" if male else "female",
            age=age, area=home, height_cm=height, build=build, marks=marks or None,
            photo_path=f"records/faces/{face['id']}_doc.jpg",
            live_photo_path=f"records/faces/{face['id']}_live.jpg", source=source,
        )
        session.add(person)
        session.flush()
        for (section, offence, _), area, when, status in cases:
            key = f"{area}/{when.year}"
            fir_seq[key] = fir_seq.get(key, rng.randint(40, 300)) + rng.randint(1, 40)
            session.add(RecordCharge(
                person_id=person.id, fir_no=f"{fir_seq[key]:04d}/{when.year}", police_station=f"{area} Police Station",
                date=when.isoformat(), section=section, offence=offence, status=status,
            ))
        added += 1
        next_no += 1
    session.commit()
    return added
