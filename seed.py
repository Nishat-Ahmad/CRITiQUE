import random
from datetime import datetime, timedelta
from uuid import uuid4
from app import SessionLocal, engine, Base, User, Place, Review, Dish

# 1. RESET THE DATABASE
print("⚡ DROPPING OLD TABLES...")
Base.metadata.drop_all(bind=engine)
print("⚡ CREATING NEW TABLES...")
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# 2. CREATE USERS
print("⚡ SEEDING USERS...")
admins = [
    User(id=str(uuid4()), email="admin@giki.edu.pk", name="Admin", role="admin", password="admin", university="GIKI"),
]

students = [
    User(id=str(uuid4()), email=f"student{i}@giki.edu.pk", name=n, role="student", password="123", university="GIKI")
    for i, n in enumerate(["Ali Khan", "Sara Ahmed", "Bilal", "Zainab", "Omar"])
]

all_users = admins + students
db.add_all(all_users)
db.commit()

# 3. CREATE PLACES (GIKI SPOTS)
print("⚡ SEEDING PLACES...")
places_data = [
    {
        "name": "Hot N Spicy",
        "type": "Fast Food",
        "address": "Tuc (Student Center)",
        "photo": "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/hot_n_spicy.jpg",
        "tags": "roll paratha, zinger, spicy, tuc, late-night",
        "description": "The legendary spot for Zinger Burgers and Roll Parathas. If you haven't had the Mayo Garlic Roll, do you even go here?"
    },
    {
        "name": "Raju Campus Hotel",
        "type": "Cafe",
        "address": "Tuc (Student Center)",
        "photo": "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/campus_hotel.jpg",
        "tags": "tea, chai, paratha, breakfast, cheap",
        "description": "Best chai on campus. The Aloo Paratha is a breakfast staple."
    },
    {
        "name": "Ayan Gardens",
        "type": "Restaurant",
        "address": "Near Hostels",
        "photo": "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/ayan_gardens.jpg",
        "tags": "juices, shakes, fries, rice, dinner",
        "description": "Great spot for fresh juices, shakes, and heavy dinner options like Shashlik."
    },
    {
        "name": "Asrar Bucks",
        "type": "Cafe",
        "address": "Faculty Market",
        "photo": "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/asrar_bucks.jpg",
        "tags": "coffee, shakes, cold coffee, oreo",
        "description": "The place to go for a caffeine fix or a sweet treat."
    },
    {
        "name": "Khyber Shinwari",
        "type": "Restaurant",
        "address": "Behind Tuc",
        "photo": "https://images.unsplash.com/photo-1555939594-58d7cb561ad1?q=80&w=1974&auto=format&fit=crop",
        "tags": "karahi, bbq, dinner, desi, heavy",
        "description": "Authentic Shinwari Karahi. Bring a group, it takes time but it's worth it."
    },
    {
        "name": "Staff Canteen",
        "type": "Cafeteria",
        "address": "Near Admin Block",
        "photo": "https://images.unsplash.com/photo-1565895405138-6c3a1555da6a?q=80&w=2070&auto=format&fit=crop",
        "tags": "lunch, cheap, roti, daal, faculty",
        "description": "Budget friendly lunch. The Daal Chawal is iconic."
    }
]

created_places = []
for p_data in places_data:
    place = Place(
        name=p_data["name"],
        type=p_data["type"],
        address=p_data["address"],
        photo=p_data["photo"],
        tags=p_data["tags"],
        description=p_data["description"],
        creator_id=admins[0].id
    )
    db.add(place)
    created_places.append(place)
db.commit()

# 4. SEED DISHES
print("⚡ SEEDING DISHES...")
# Map place names to dishes
dishes_map = {
    "Hot N Spicy": [
        ("Zinger Burger", 450, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Zinger%20Burger.jpg"),
        ("Zinger Cheese Burger", 500, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Zinger%20Cheese%20Burger.jpg"),
        ("Fillet Burger", 400, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Fillet%20Burger.jpg"),
        ("Double Fillet Burger", 600, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Double%20Fillet%20Burger.jpg"),
        ("Supreme Burger", 550, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Supreme%20Burger.jpg"),
        ("Crown Crust Pizza", 1200, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Crown%20Crust%20Pizza.jpg"),
        ("Pepperoni Pizza", 1100, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Pepperoni%20Pizza.jpg"),
        ("JKS Pizza", 1150, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/JKS%20Pizza.jpg"),
        ("Classic Cookie", 150, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Classic%20Cookie.jpg"),
        ("Double Chocolate Cookie", 180, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Hot%20N%20Spicy/Double%20Chocolate%20Cookie.jpg")
    ],
    "Raju Campus Hotel": [
        ("Fried Wings", 350, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Raju%20Campus%20Hotel/Fried%20Wings.jpg"),
        ("Kung Pao Chicken", 600, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Raju%20Campus%20Hotel/Kung%20Pao%20Chicken.jpg"),
        ("Singaporean Rice", 550, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Raju%20Campus%20Hotel/Singaporean%20Rice.jpg"),
        ("Aloo Paratha", 100, "https://images.unsplash.com/photo-1606491956689-2ea28c674675?q=80&w=1974&auto=format&fit=crop"),
        ("Doodh Patti", 60, "https://images.unsplash.com/photo-1576092768241-dec231879fc3?q=80&w=1974&auto=format&fit=crop")
    ],
    "Ayan Gardens": [
        ("Shashlik Rice", 500, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Shashlik%20Rice.jpg"),
        ("Tikka Fried Rice", 450, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Tikka%20Fried%20Rice.jpg"),
        ("Special Sandwich", 350, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Special%20Sandwich.jpg"),
        ("Loaded Fries", 400, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Loaded%20Fries.jpg"),
        ("French Fries", 200, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/French%20Fries.jpg"),
        ("Banana Milkshake", 250, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Banana%20Milkshake.jpg"),
        ("Apple Juice", 200, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Apple%20Juice.jpg"),
        ("Lassi", 150, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Lassi.jpg"),
        ("Blueberry Lassi", 200, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Blueberry%20Lassi.jpg"),
        ("Mint Lassi", 180, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Mint%20Lassi.jpg"),
        ("Tea", 50, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Ayan%20Gardens/Tea.jpg")
    ],
    "Asrar Bucks": [
        ("Cold Coffee", 300, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Asrar%20Bucks/Cold%20Coffee.jpg"),
        ("Oreo Milkshake", 350, "https://raw.githubusercontent.com/HassanIqbal715/Tuc-Eats/main/public/images/items/Asrar%20Bucks/Oreo%20Milkshake.jpg")
    ],
    "Khyber Shinwari": [
        ("Chicken Karahi (Half)", 1200, "https://images.unsplash.com/photo-1603496987351-f84a3ba5ec85?q=80&w=2076&auto=format&fit=crop"),
        ("Seekh Kabab", 400, None),
        ("Naan", 30, None)
    ],
    "Staff Canteen": [
        ("Daal Chawal", 120, "https://images.unsplash.com/photo-1546833999-b9f581a1996d?q=80&w=2070&auto=format&fit=crop"),
        ("Chicken Qorma", 200, None)
    ]
}

for place in created_places:
    if place.name in dishes_map:
        for d_name, d_price, d_photo in dishes_map[place.name]:
            dish = Dish(
                name=d_name,
                price=d_price,
                photo=d_photo,
                place_id=place.id
            )
            db.add(dish)
db.commit()

# 5. SEED REVIEWS
print("⚡ SEEDING REVIEWS...")
reviews_text = [
    "Absolutely loved it! 10/10 would recommend.",
    "It was okay, but a bit pricey.",
    "Best food on campus hands down.",
    "Service was slow but food was good.",
    "Not my cup of tea.",
    "Legendary status.",
    "Hygiene could be better."
]

for place in created_places:
    # Add 3-7 reviews per place
    for _ in range(random.randint(3, 7)):
        user = random.choice(all_users)
        review = Review(
            place_id=place.id,
            user_id=user.id,
            rating=random.randint(3, 5),
            text=random.choice(reviews_text),
            created_at=int((datetime.utcnow() - timedelta(days=random.randint(0, 30))).timestamp() * 1000)
        )
        db.add(review)
        # Update user stats
        user.total_reviews += 1

db.commit()
print("✅ SEEDING COMPLETE!")
