#!/usr/bin/env python3
import random
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from app import SessionLocal, User, Place, Review, DishReview
from sqlalchemy.orm import joinedload

MANIFEST_PATH = Path("user_manifest.txt")

# If the database stores timestamps in seconds instead of milliseconds we'll
# detect that at runtime and convert reads/writes appropriately.
DB_IN_SECONDS = None  # will be set to True/False by detect_db_timeunit(db)

random.seed(20251220)

POPULAR_PLACES = {
    "ayan": 4.0,
    "raju": 4.0,
    "hns": 3.0,
}
DEFAULT_WEIGHT = 1.0

def load_manifest(path):
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("==="):
            continue
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                email, name, password, hostel = parts[0], parts[1], parts[2], parts[3]
                lines.append({"email": email, "name": name, "password": password, "hostel": hostel})
    unique = {}
    for entry in lines:
        if entry["email"] not in unique:
            unique[entry["email"]] = entry
    users = list(unique.values())
    return users

def ensure_users(db, manifest_users):
    existing = {u.email: u for u in db.query(User).all()}
    created = []
    for u in manifest_users:
        email = u["email"]
        if email in existing:
            continue
        uid = email
        obj = User(id=uid, email=email, name=u["name"], role="student", university=None, password=u["password"], total_reviews=0)
        db.add(obj)
        created.append(obj)
    if created:
        db.commit()
    # manifest_users is a list of dicts (keys: email, name, password, hostel)
    users = {u["email"]: db.query(User).filter(User.email == u["email"]).first() for u in manifest_users}
    return users

def fetch_places_and_dishes(db):
    places = db.query(Place).options(joinedload(Place.dishes)).all()
    place_map = []
    for p in places:
        dishes = list(p.dishes) if getattr(p, "dishes", None) is not None else []
        place_map.append({"place": p, "dishes": dishes, "name": p.name})
    return place_map

def existing_timestamps(db):
    # Return a set of timestamps normalized to milliseconds regardless of how
    # the DB stores them (seconds vs milliseconds). This set is used to avoid
    # collisions when generating new timestamps.
    global DB_IN_SECONDS
    if DB_IN_SECONDS is None:
        detect_db_timeunit(db)

    ts = set()
    for r in db.query(Review.created_at).all():
        if r[0] is None:
            continue
        val = int(r[0])
        if DB_IN_SECONDS:
            val = val * 1000
        ts.add(val)
    for r in db.query(DishReview.created_at).all():
        if r[0] is None:
            continue
        val = int(r[0])
        if DB_IN_SECONDS:
            val = val * 1000
        ts.add(val)
    return ts


def detect_db_timeunit(db):
    """Detect whether DB stores timestamps in seconds (True) or ms (False).

    Strategy: sample the first non-null created_at from Review or DishReview.
    If the value is small (<= 1e11) it's almost certainly seconds; otherwise
    treat it as milliseconds. If no samples present, default to milliseconds.
    """
    global DB_IN_SECONDS
    sample = None
    r = db.query(Review.created_at).filter(Review.created_at.isnot(None)).first()
    if r and r[0] is not None:
        sample = int(r[0])
    else:
        d = db.query(DishReview.created_at).filter(DishReview.created_at.isnot(None)).first()
        if d and d[0] is not None:
            sample = int(d[0])

    if sample is None:
        # No existing timestamps, assume ms (the script generates ms by default)
        DB_IN_SECONDS = False
        return

    # If sample is small (e.g. ~1.7e9 for 2025 seconds), it's seconds.
    if sample < 1e11:
        DB_IN_SECONDS = True
    else:
        DB_IN_SECONDS = False

def unique_ts_for_day(day_date, used):
    start = int(datetime(day_date.year, day_date.month, day_date.day, tzinfo=timezone.utc).timestamp() * 1000)
    end = start + 24 * 60 * 60 * 1000 - 1
    for _ in range(10000):
        cluster = random.random()
        if cluster < 0.6:
            hour = random.choice([12,13,18,19,20,21,23,0,1])
            minute = random.randint(0,59)
            second = random.randint(0,59)
            dt = datetime(day_date.year, day_date.month, day_date.day, hour, minute, second, tzinfo=timezone.utc)
            ts = int(dt.timestamp() * 1000)
        else:
            ts = random.randint(start + 60*60*1000, end - 60*60*1000)
        if ts in used:
            ts += random.randint(1, 60000)
        if ts not in used and start <= ts <= end:
            used.add(ts)
            return ts
    raise RuntimeError("Unable to generate unique timestamp")

def unique_ts_now(used, offset_ms_max=60000):
    base = int(datetime.utcnow().timestamp() * 1000)
    for _ in range(10000):
        offset = random.randint(-offset_ms_max, offset_ms_max)
        ts = base + offset
        if ts in used:
            ts += random.randint(1, 60000)
        if ts not in used:
            used.add(ts)
            return ts
    raise RuntimeError("Unable to generate unique now timestamp")


def pick_place_weighted(places):
    weighted = []
    for place in places:
        # place_map entry: {"place": p, "dishes": dishes, "name": p.name}
        name = place["name"].lower() if "name" in place else str(place["place"]).lower()
        weight = DEFAULT_WEIGHT
        for key, w in POPULAR_PLACES.items():
            if key in name:
                weight = w
                break
        weighted.append((place, weight))
    return random.choices(
        [p for p, _ in weighted],
        weights=[w for _, w in weighted],
        k=1
    )[0]

def pick_place(place_map):
    pm = pick_place_weighted(place_map)
    return pm["place"], pm["dishes"]

def maybe_subject(place_name, dish_name, is_dish):
    if random.random() < 0.05:
        if is_dish and dish_name:
            return dish_name.split()[0]  # partial name
        return place_name.split()[0]
    return ""

def generate_review_text(user_name, place_name, dish_name, is_dish, mood):
    subject = maybe_subject(place_name, dish_name, is_dish)
    prefix = f"{subject} " if subject else ""


    BASE_POSITIVE = [
        # ===== POSITIVE =====
        f"{prefix} acha tha",
        f"{prefix} bohat acha laga",
        f"{prefix} ka taste sahi tha",
        f"{prefix} actually good tha",
        f"{prefix} kaafi enjoyable tha",
        f"{prefix} worth it laga",
        f"{prefix} satisfying tha",
        f"{prefix} solid choice hai",
        f"{prefix} kaafi reliable hai",
        f"{prefix} hit the spot",
        f"{prefix} ka flavour on point tha",
        f"{prefix} better than expected",
        f"{prefix} fresh laga",
        f"{prefix} mood bana diya",
        f"{prefix} comfort food type hai",
        f"{prefix} kaafi smooth experience tha",
        f"{prefix} legit acha laga",
        f"{prefix} did not disappoint",
        f"{prefix} kaafi consistent hai",
        f"{prefix} ka taste balanced tha",
        f"{prefix} enjoyed it honestly",
        f"{prefix} lowkey banger hai",
        f"{prefix} clutch choice tha",
        f"{prefix} simple but good",
        f"{prefix} kaafi clean taste tha",
        f"{prefix} reliable option hai",
        f"{prefix} roz bhi kha sakta hoon",
        f"{prefix} achi quality ka tha",
        f"{prefix} ka scene sahi tha",
        f"{prefix} kaafi comforting tha",
        f"{prefix} hit hua aaj",
        f"{prefix} worked for me",
        f"{prefix} achi tarah bana tha",
        f"{prefix} felt fresh today",
        f"{prefix} ka taste on point tha",
        f"{prefix} kaafi enjoyable experience",
        f"{prefix} decent se better tha",
        f"{prefix} solid overall",
        f"{prefix} kaafi acha nikla",
        f"{prefix} expected se acha tha",
        f"{prefix} kaafi smooth tha",
        f"{prefix} no complaints",
        f"{prefix} would recommend",
        f"{prefix} ka scene clean tha",
        f"{prefix} kaafi achi cheez hai",
        f"{prefix} liked it overall",
        f"{prefix} kaafi dependable hai",
        f"{prefix} achi choice thi",
        f"{prefix} kaafi sahi laga",
        f"{prefix} ka taste kaafi nice tha",
        f"{prefix} achi vibe deta hai",
        f"{prefix} kaafi theek nikla",
        f"{prefix} enjoyed this one",
        f"{prefix} kaafi acha laga aaj",
        f"{prefix} ka taste solid hai",
        f"{prefix} kaafi chill experience",
        f"{prefix} no issues honestly",
        f"{prefix} kaafi decent nikla",
        f"{prefix} kaafi acha option hai",
        f"{prefix} would have again",
        f"{prefix} kaafi tasty tha",
    ]
    BASE_NEUTRAL = [
        # ===== NEUTRAL =====
        f"{prefix} theek tha",
        f"{prefix} okay tha",
        f"{prefix} average laga",
        f"{prefix} bas normal tha",
        f"{prefix} decent hi tha",
        f"{prefix} mid tha",
        f"{prefix} kuch khaas nahi",
        f"{prefix} expected jaisa hi tha",
        f"{prefix} chal jata hai",
        f"{prefix} kaam chal gaya",
        f"{prefix} fine tha overall",
        f"{prefix} na acha na bura",
        f"{prefix} campus food jaisa tha",
        f"{prefix} normal experience tha",
        f"{prefix} bas okayish laga",
        f"{prefix} average hi tha honestly",
        f"{prefix} thora basic laga",
        f"{prefix} simple sa tha",
        f"{prefix} nothing special",
        f"{prefix} regular sa laga",
        f"{prefix} expected se different nahi",
        f"{prefix} acceptable tha",
        f"{prefix} manageable tha",
        f"{prefix} theek hi hai overall",
        f"{prefix} average quality ka tha",
        f"{prefix} thora bland laga",
        f"{prefix} normal hi nikla",
        f"{prefix} zyada yaad rehne wala nahi",
        f"{prefix} theek tha bas",
        f"{prefix} okay experience tha",
        f"{prefix} average se thora better",
        f"{prefix} theek level ka tha",
        f"{prefix} nothing crazy",
        f"{prefix} simple hi tha",
        f"{prefix} okayish overall",
        f"{prefix} kaam ka tha",
        f"{prefix} expected hi tha",
        f"{prefix} okay tha fr",
        f"{prefix} normal sa laga",
        f"{prefix} not bad not great",
        f"{prefix} bas theek tha",
        f"{prefix} average experience tha",
        f"{prefix} kuch khaas nahi tha",
        f"{prefix} manageable experience tha",
        f"{prefix} thora meh laga",
        f"{prefix} expected jaisa laga",
        f"{prefix} bilkul average tha",
        f"{prefix} kuch zyada special nahi tha",
        f"{prefix} sahi tha overall",
        f"{prefix} na zyada acha na bura",
        f"{prefix} theek tha honestly",
        f"{prefix} kuch khaas feel nahi hua",
        f"{prefix} bilkul normal tha",
        f"{prefix} expected se zyada nahi tha",
        f"{prefix} bas chal jata hai",
    ]
    BASE_NEGATIVE = [
        # ===== NEGATIVE =====
        f"{prefix} acha nahi tha",
        f"{prefix} disappointed kar gaya",
        f"{prefix} ka taste off tha",
        f"{prefix} worth it nahi laga",
        f"{prefix} waste sa laga",
        f"{prefix} kaafi bekaar tha",
        f"{prefix} meh tha honestly",
        f"{prefix} expected better",
        f"{prefix} mood kharab ho gaya",
        f"{prefix} nahi jamma",
        f"{prefix} phir nahi lunga",
        f"{prefix} quality gir gayi hai",
        f"{prefix} kaafi weak tha",
        f"{prefix} underwhelming tha",
        f"{prefix} not it",
        f"{prefix} disappointing tha",
        f"{prefix} taste weird laga",
        f"{prefix} zyada acha nahi laga",
        f"{prefix} overpriced feel hua",
        f"{prefix} bilkul hit nahi hua",
        f"{prefix} regret ho gaya",
        f"{prefix} time waste laga",
        f"{prefix} paisay waste lagay",
        f"{prefix} ka scene off tha",
        f"{prefix} bilkul maza nahi aya",
        f"{prefix} below expectations tha",
        f"{prefix} ka taste flat tha",
        f"{prefix} kaafi disappointing",
        f"{prefix} not worth it today",
        f"{prefix} avoid kar sakte ho",
        f"{prefix} kaafi meh experience",
        f"{prefix} quality weak lagi",
        f"{prefix} aaj bilkul sahi nahi tha",
        f"{prefix} ka taste dull tha",
        f"{prefix} phir try nahi karunga",
        f"{prefix} overall disappointing",
        f"{prefix} kaafi off laga",
        f"{prefix} let down tha",
        f"{prefix} kaafi bekaar nikla",
        f"{prefix} zyada pasand nahi aya",
        f"{prefix} kaafi meh laga",
        f"{prefix} bilkul pasand nahi aya",
        f"{prefix} expected se behtar nahi tha",
        f"{prefix} kaafi underwhelming tha",
        f"{prefix} bilkul acha nahi laga",
    ]

    ADD_ONS = [
        "price ke hisaab se theek tha",
        "price thori zyada lagi",
        "portion decent tha",
        "portion chota laga",
        "fresh bana hua laga",
        "fresh nahi laga",
        "rush bohat tha",
        "waiting zyada thi",
        "late night ke liye theek tha",
        "bhook bohat lagi thi",
        "exam ke baad khaya",
        "hostel ke paas convenient hai",
        "roz roz ka scene hai",
        "taste consistent nahi laga",
        "taste kaafi stable hai",
        "aaj mood bana",
        "aaj mood nahi bana",
        "simple but filling tha",
        "zyada oily tha",
        "zyada heavy nahi tha",
        "light sa laga",
        "campus food jaisa hi hai",
        "is price pe better mil jata",
        "time pass ke liye theek",
        "friends ke sath khaya",
        "akele khaya tha",
        "portion okay tha",
        "service slow thi",
        "service theek thi",
        "overall theek laga",
        "overall disappointing tha",
        "quality average thi",
        "quality achi lagi",
        "taste thora bland tha",
        "taste theek tha",
        "expectations low thi",
        "expectations high thi",
        "aaj average laga",
        "roz ka option ban sakta",
        "phir try kar sakta hoon",
        "phir lene ka mood nahi",
        "price justified laga",
        "price thori mehngi lagi",
        "zyada yaad rehne wala nahi",
        "kaam chal gaya honestly",
        "bas okay tha",
        "nothing special honestly",
        "overall fine hi tha",
        "overall meh laga",
    ]

    TAGS = ["ngl", "tbh", "fr", "honestly", "lol"]

    bucket = random.choices(
        ["positive", "neutral", "negative"],
        weights=[0.45, 0.30, 0.25],
        k=1
    )[0]

    if bucket == "positive":
        base = random.choice(BASE_POSITIVE)
    elif bucket == "neutral":
        base = random.choice(BASE_NEUTRAL)
    else:
        base = random.choice(BASE_NEGATIVE)
    parts = [base]

    if random.random() < 0.45:
        parts.append(random.choice(ADD_ONS))

    text = ". ".join(parts)

    if random.random() < 0.4:
        text = text.lower()

    if random.random() < 0.3:
        text += f" {random.choice(TAGS)}"

    return text.strip(), bucket


def rating_from_sentiment(bucket, user_type):
    if bucket == "positive":
        return random.choice([4, 5]) if user_type == "loyalist" else random.choice([3, 4, 5])
    if bucket == "neutral":
        return 3
    return random.choice([1, 2])

def commit_review_place(db, user_obj, place_obj, rating, text, created_at):
    # created_at passed into this file is milliseconds; convert to DB unit
    global DB_IN_SECONDS
    created_at_db = int(created_at // 1000) if DB_IN_SECONDS else int(created_at)
    r = Review(place_id=place_obj.id, user_id=user_obj.id, rating=rating, text=text, created_at=created_at_db)
    db.add(r)
    user_obj.total_reviews = (user_obj.total_reviews or 0) + 1
    db.commit()

def commit_review_dish(db, user_obj, dish_obj, rating, text, created_at):
    global DB_IN_SECONDS
    created_at_db = int(created_at // 1000) if DB_IN_SECONDS else int(created_at)
    r = DishReview(dish_id=dish_obj.id, user_id=user_obj.id, rating=rating, text=text, created_at=created_at_db)
    db.add(r)
    user_obj.total_reviews = (user_obj.total_reviews or 0) + 1
    db.commit()

def phase_seed(db, manifest_users, place_map):
    used_ts = existing_timestamps(db)
    loyalists = [u for u in manifest_users if ("Hostel 5" in u["hostel"] or "Hostel 6" in u["hostel"])]
    churners = [u for u in manifest_users if u not in loyalists]
    user_objs = {}
    for u in manifest_users:
        user_objs[u["email"]] = db.query(User).filter(User.email == u["email"]).first()
    
    # Modified to run for the past 3 days (today included)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=2)
    days = [start + timedelta(days=i) for i in range(3)]
    
    churn_weights = [0.33, 0.33, 0.34] # Even distribution for 3 days
    for c in churners:
        # Skip churners who already have any reviews in the DB. This prevents
        # duplicate churner posts if --seed is run multiple times.
        user_obj = user_objs[c["email"]]
        # existing_any = (user_obj.total_reviews or 0) > 0 or db.query(Review).filter(Review.user_id == user_obj.id).count() > 0 or db.query(DishReview).filter(DishReview.user_id == user_obj.id).count() > 0
        # if existing_any:
        #     continue

        day = random.choices(days, weights=churn_weights, k=1)[0]
        ts = unique_ts_for_day(day, used_ts)
        place_obj, dishes = pick_place(place_map)
        make_dish = bool(dishes) and (random.random() < 0.6)
        bucket = random.choices(
            ["positive", "neutral", "negative"],
            weights=[0.45, 0.30, 0.25],
            k=1
        )[0]
        rating = rating_from_sentiment(bucket, "churner")
        mood = random.choice(["late-night hunger","mild disappointment","price frustration","this saved my day","not worth it today"])
        if make_dish:
            dish_obj = random.choice(dishes)
            text, _ = generate_review_text(user_obj.name, place_obj.name, dish_obj.name, True, mood)
            commit_review_dish(db, user_obj, dish_obj, rating, text, ts)
        else:
            text, _ = generate_review_text(user_obj.name, place_obj.name, None, False, mood)
            commit_review_place(db, user_obj, place_obj, rating, text, ts)

    for day in days:
        for loyal in loyalists:
            if random.random() < 0.5:
                user_obj = user_objs[loyal["email"]]
                # Ensure the loyalist doesn't already have a review for this day
                # (so re-running --seed won't create a second review for the same
                # loyal user on the same day). We check both Review and DishReview
                # tables using the DB's timestamp unit.
                global DB_IN_SECONDS
                day_start_ms = int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp() * 1000)
                day_end_ms = day_start_ms + 24 * 60 * 60 * 1000 - 1
                if DB_IN_SECONDS:
                    db_start = day_start_ms // 1000
                    db_end = day_end_ms // 1000
                else:
                    db_start = day_start_ms
                    db_end = day_end_ms

                already_today = db.query(Review).filter(Review.user_id == user_obj.id, Review.created_at >= db_start, Review.created_at <= db_end).count() > 0 or db.query(DishReview).filter(DishReview.user_id == user_obj.id, DishReview.created_at >= db_start, DishReview.created_at <= db_end).count() > 0
                if already_today:
                    continue

                ts = unique_ts_for_day(day, used_ts)
                place_obj, dishes = pick_place(place_map)
                make_dish = bool(dishes) and (random.random() < 0.6)
                bucket = random.choices(
                    ["positive", "neutral", "negative"],
                    weights=[0.7, 0.20, 0.10],
                    k=1
                )[0]
                rating = rating_from_sentiment(bucket, "loyalist")
                mood = random.choice(["loyalty comfort food","this saved my day","late-night hunger","mild disappointment"])
                if make_dish:
                    dish_obj = random.choice(dishes)
                    text, _ = generate_review_text(user_obj.name, place_obj.name, dish_obj.name, True, mood)
                    commit_review_dish(db, user_obj, dish_obj, rating, text, ts)
                else:
                    text, _ = generate_review_text(user_obj.name, place_obj.name, None, False, mood)
                    commit_review_place(db, user_obj, place_obj, rating, text, ts)

def phase_pulse(db, manifest_users, place_map):
    used_ts = existing_timestamps(db)
    loyalists = [u for u in manifest_users if ("Hostel 5" in u["hostel"] or "Hostel 6" in u["hostel"])]
    user_objs = {u["email"]: db.query(User).filter(User.email == u["email"]).first() for u in loyalists}
    # Generate between 1 and 10 loyalist reviews per pulse, gaussian left skewed
    n = random.choices([1,2,3,4,5,6,7,8,9,10], weights=[0.05,0.05,0.2,0.3,0.1,0.1,0.05,0.05,0.05,0.05], k=1)[0]
    chosen = random.sample(loyalists, k=n)
    for loyal in chosen:
        ts = unique_ts_now(used_ts, offset_ms_max=60000)
        place_obj, dishes = pick_place(place_map)
        make_dish = bool(dishes) and (random.random() < 0.6)
        user_obj = user_objs[loyal["email"]]
        # Generate a sentiment bucket as in generate_review_text
        bucket = random.choices(
            ["positive", "neutral", "negative"],
            weights=[0.8, 0.10, 0.10],
            k=1
        )[0]
        rating = rating_from_sentiment(bucket, "loyalist")
        mood = random.choice(["late-night hunger","this saved my day","loyalty comfort food"])
        if make_dish:
            dish_obj = random.choice(dishes)
            text, _ = generate_review_text(user_obj.name, place_obj.name, dish_obj.name, True, mood)
            commit_review_dish(db, user_obj, dish_obj, rating, text, ts)
        else:
            text, _ = generate_review_text(user_obj.name, place_obj.name, None, False, mood)
            commit_review_place(db, user_obj, place_obj, rating, text, ts)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", action="store_true")
    args = parser.parse_args()
    print("RUN MODE:", "SEED" if args.seed else "PULSE")
    Session = SessionLocal
    db = Session()
    manifest_users = load_manifest(MANIFEST_PATH)
    ensure_users(db, manifest_users)
    place_map = fetch_places_and_dishes(db)

    if args.seed:
        phase_seed(db, manifest_users, place_map)
    else:
        phase_pulse(db, manifest_users, place_map)
    db.close()

if __name__ == "__main__":
    main()
