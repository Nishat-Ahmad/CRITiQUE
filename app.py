import os
import io
from datetime import datetime, timedelta
from uuid import uuid4
from typing import List, Optional

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# FastAPI & Starlette Imports
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

# SQLAlchemy Imports
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import sessionmaker, relationship, Session, declarative_base

# --- 1. CONFIGURATION & DATABASE SETUP ---

SECRET_KEY = os.environ.get('CRITIQUE_SECRET', 'dev-secret')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Database Setup
DB_PATH = os.path.join(BASE_DIR, 'campuseats.db') 
SQLALCHEMY_DATABASE_URI = f"sqlite:///{DB_PATH}"

engine = create_engine(SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

app = FastAPI(title="CRITiQUE", docs_url="/docs", redoc_url=None)

STATIC_DIR = os.path.join(BASE_DIR, 'server', 'static')
TEMPLATES_DIR = os.path.join(BASE_DIR, 'server', 'templates')

if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

# ⚡ CUSTOM DATE FILTER
def format_time_ago(value):
    if not value: return ""
    # Value is ms timestamp
    dt = datetime.fromtimestamp(int(value) / 1000)
    now = datetime.now()
    diff = now - dt
    
    if diff.days == 0:
        if diff.seconds < 60:
            return "Just now"
        if diff.seconds < 3600:
            return f"{diff.seconds // 60}m ago"
        return f"{diff.seconds // 3600}h ago"
    if diff.days < 7:
        return f"{diff.days}d ago"
    return dt.strftime("%b %d, %Y")

templates.env.filters["time_ago"] = format_time_ago


# --- 2. DATABASE MODELS ---

def now_ts():
    return int(datetime.utcnow().timestamp() * 1000)

class User(Base):
    __tablename__ = "user"
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    role = Column(String(10), nullable=False, default='student')
    university = Column(String, nullable=True)
    password = Column(String, nullable=True)
    total_reviews = Column(Integer, default=0)

class Place(Base):
    __tablename__ = "place"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=True)
    address = Column(String, nullable=True)
    photo = Column(String, nullable=True)
    tags = Column(String, nullable=True)
    creator_id = Column(String, ForeignKey('user.id'), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(Integer, default=now_ts)

    dishes = relationship("Dish", back_populates="place", cascade="all, delete-orphan")

class Dish(Base):
    __tablename__ = "dish"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    price = Column(Integer, nullable=True)
    photo = Column(String, nullable=True)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False)
    
    place = relationship("Place", back_populates="dishes")
    reviews = relationship("DishReview", back_populates="dish", cascade="all, delete-orphan")

class DishReview(Base):
    __tablename__ = "dish_review"
    id = Column(Integer, primary_key=True, index=True)
    dish_id = Column(Integer, ForeignKey('dish.id'), nullable=False)
    user_id = Column(String, ForeignKey('user.id'), nullable=False)
    rating = Column(Integer, nullable=False)
    text = Column(Text, nullable=True)
    created_at = Column(Integer, default=now_ts)
    
    dish = relationship("Dish", back_populates="reviews")

class Review(Base):
    __tablename__ = "review"
    id = Column(Integer, primary_key=True, index=True)
    place_id = Column(Integer, ForeignKey('place.id'), nullable=False)
    user_id = Column(String, ForeignKey('user.id'), nullable=False)
    rating = Column(Integer, nullable=False)
    text = Column(Text, nullable=True)
    created_at = Column(Integer, default=now_ts)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- 3. HELPER FUNCTIONS ---

PLACE_TYPES = ['Cafeteria', 'Cafe', 'Restaurant', 'Food Truck', 'Bakery', 'Fast Food', 'Desserts', 'Beverages', 'Other']

def flash(request: Request, message: str):
    if '_messages' not in request.session:
        request.session['_messages'] = []
    request.session['_messages'].append(message)

def get_flashed_messages(request: Request):
    return request.session.pop('_messages', [])

def get_common_context(request: Request, db: Session):
    uid = request.session.get('user_id')
    user = db.query(User).filter(User.id == uid).first() if uid else None
    
    def jinja_url_for(name: str, **kwargs):
        if name == 'static' and 'filename' in kwargs:
            kwargs['path'] = kwargs.pop('filename')
        return request.url_for(name, **kwargs)

    return {
        "request": request,
        "current_user": user,
        "place_types": PLACE_TYPES,
        "get_flashed_messages": lambda: get_flashed_messages(request),
        "url_for": jinja_url_for
    }

def serialize_place(place, db: Session):
    avg = db.query(func.avg(Review.rating)).filter(Review.place_id == place.id).scalar() or 0
    creator_name = None
    if place.creator_id:
        cu = db.query(User).filter(User.id == place.creator_id).first()
        creator_name = cu.name if cu else None
        
    return {
        'id': place.id,
        'name': place.name,
        'type': place.type,
        'address': place.address,
        'photo': place.photo,
        'tags': place.tags.split(',') if place.tags else [],
        'createdAt': place.created_at,
        'avgRating': float(avg),
        'creatorId': place.creator_id,
        'creatorName': creator_name,
        'description': place.description
    }

# --- 4. ROUTES ---

@app.get("/", response_class=HTMLResponse)
def home(request: Request, q: str = "", tag: str = "", db: Session = Depends(get_db)):
    places = db.query(Place).all()
    results = [p for p in places if q.lower() in p.name.lower() and (not tag or (p.tags and tag in p.tags.split(',')))]
    serialized = [serialize_place(p, db) for p in results]
    
    # Search Dishes
    serialized_dishes = []
    if q:
        dishes = db.query(Dish).all()
        dish_matches = [d for d in dishes if q.lower() in d.name.lower()]
        serialized_dishes = [{
            'id': d.id,
            'name': d.name,
            'price': d.price,
            'photo': d.photo,
            'place_id': d.place_id,
            'place_name': d.place.name
        } for d in dish_matches]

    place_counts = []
    for p in places:
        count = db.query(Review).filter(Review.place_id == p.id).count()
        place_counts.append((p, count))
    place_counts.sort(key=lambda x: x[1], reverse=True)
    trending = [serialize_place(p[0], db) for p in place_counts[:3]]
    
    context = get_common_context(request, db)
    context.update({"places": serialized, "dishes": serialized_dishes, "trending": trending, "q": q, "tag": tag})
    return templates.TemplateResponse("home.html", context)

@app.get("/register", response_class=HTMLResponse)
def register_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("register.html", get_common_context(request, db))

@app.post("/register")
async def register_post(request: Request, email: str = Form(...), name: str = Form(...), university: str = Form(""), password: str = Form(...), admin_code: str = Form(""), db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == email).first():
        flash(request, "Email already exists")
        return RedirectResponse(request.url_for("register_view"), status_code=303)
    role = 'student'
    valid_codes = [os.environ.get('CRITIQUE_ADMIN_CODE'), 'campuseatsadmin2025']
    if admin_code in [c for c in valid_codes if c]:
        role = 'admin'
    user = User(id=str(uuid4()), email=email, name=name, university=university, password=password, role=role)
    db.add(user)
    db.commit()
    request.session['user_id'] = user.id
    return RedirectResponse(request.url_for("home"), status_code=303)

@app.get("/login", response_class=HTMLResponse)
def login_view(request: Request, db: Session = Depends(get_db)):
    return templates.TemplateResponse("login.html", get_common_context(request, db))

@app.post("/login")
async def login_post(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        flash(request, "Account not found")
        return RedirectResponse(request.url_for("login_view"), status_code=303)
    if user.password != password:
        flash(request, "Invalid credentials")
        return RedirectResponse(request.url_for("login_view"), status_code=303)
    request.session['user_id'] = user.id
    return RedirectResponse(request.url_for("home"), status_code=303)

@app.get("/logout")
def logout_view(request: Request):
    request.session.pop('user_id', None)
    return RedirectResponse(request.url_for("home"), status_code=303)

@app.get("/places/new", response_class=HTMLResponse)
def new_place_view(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get('user_id')
    if not user_id:
        flash(request, "Please login to add a place")
        return RedirectResponse(request.url_for("login_view"), status_code=303)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != 'admin':
        flash(request, "Only admins can add places")
        return RedirectResponse(request.url_for("home"), status_code=303)
        
    return templates.TemplateResponse("add_place.html", get_common_context(request, db))

@app.post("/places/new")
async def new_place_post(request: Request, name: str = Form(...), type: str = Form(""), address: str = Form(""), tags: str = Form(""), photo: str = Form(""), description: str = Form(""), db: Session = Depends(get_db)):
    user_id = request.session.get('user_id')
    if not user_id:
        return RedirectResponse(request.url_for("login_view"), status_code=303)
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != 'admin':
        flash(request, "Only admins can add places")
        return RedirectResponse(request.url_for("home"), status_code=303)
        
    p = Place(name=name, type=type, address=address, tags=tags, photo=photo, description=description, creator_id=user_id)
    db.add(p)
    db.commit()
    return RedirectResponse(request.url_for("home"), status_code=303)

@app.get("/places/{place_id}", response_class=HTMLResponse)
def place_view(request: Request, place_id: int, db: Session = Depends(get_db)):
    p = db.query(Place).filter(Place.id == place_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Place not found")
    reviews = db.query(Review).filter(Review.place_id == place_id).order_by(Review.created_at.desc()).all()
    reviews_ser = [{'id': r.id, 'user': (db.query(User).filter(User.id == r.user_id).first().name if db.query(User).filter(User.id == r.user_id).first() else r.user_id), 'rating': r.rating, 'text': r.text, 'createdAt': r.created_at, 'userId': r.user_id} for r in reviews]
    
    recommendations = []
    try:
        from recommender import ContentRecommender
        all_places = db.query(Place).all()
        places_data = [{'id': pl.id, 'name': pl.name, 'type': pl.type, 'tags': pl.tags, 'description': pl.description} for pl in all_places]
        engine = ContentRecommender(places_data)
        rec_ids = engine.recommend(place_id)
        recommendations = [serialize_place(db.query(Place).get(rid), db) for rid in rec_ids]
    except Exception as e:
        print(f"Recommender error: {e}")

    dishes = db.query(Dish).filter(Dish.place_id == place_id).all()
    dishes_ser = [{
        'id': d.id,
        'name': d.name,
        'price': d.price,
        'photo': d.photo,
        'avgRating': float(db.query(func.avg(DishReview.rating)).filter(DishReview.dish_id == d.id).scalar() or 0)
    } for d in dishes]

    context = get_common_context(request, db)
    context.update({"place": serialize_place(p, db), "reviews": reviews_ser, "recommendations": recommendations, "dishes": dishes_ser})
    return templates.TemplateResponse("place.html", context)

@app.post("/places/{place_id}")
async def place_post_review(request: Request, place_id: int, rating: int = Form(5), text: str = Form(""), db: Session = Depends(get_db)):
    user_id = request.session.get('user_id')
    if not user_id:
        flash(request, "Please login to review")
        return RedirectResponse(request.url_for("login_view"), status_code=303)
    r = Review(place_id=place_id, user_id=user_id, rating=rating, text=text)
    db.add(r)
    user = db.query(User).filter(User.id == user_id).first()
    if user: user.total_reviews = (user.total_reviews or 0) + 1
    db.commit()
    return RedirectResponse(request.url_for("place_view", place_id=place_id), status_code=303)

@app.post("/places/{place_id}/delete")
async def delete_place(request: Request, place_id: int, db: Session = Depends(get_db)):
    user = get_common_context(request, db)['current_user']
    if not user or user.role != 'admin':
        return RedirectResponse(request.url_for("home"), status_code=303)
        
    place = db.query(Place).filter(Place.id == place_id).first()
    if place:
        db.delete(place)
        db.commit()
        
    return RedirectResponse(request.url_for("home"), status_code=303)



@app.get("/dishes/{dish_id}", response_class=HTMLResponse)
def dish_view(request: Request, dish_id: int, db: Session = Depends(get_db)):
    d = db.query(Dish).filter(Dish.id == dish_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Dish not found")
    
    reviews = db.query(DishReview).filter(DishReview.dish_id == dish_id).order_by(DishReview.created_at.desc()).all()
    reviews_ser = [{'id': r.id, 'user': (db.query(User).filter(User.id == r.user_id).first().name if db.query(User).filter(User.id == r.user_id).first() else r.user_id), 'rating': r.rating, 'text': r.text, 'createdAt': r.created_at, 'userId': r.user_id} for r in reviews]
    
    avg = db.query(func.avg(DishReview.rating)).filter(DishReview.dish_id == dish_id).scalar() or 0
    
    dish_data = {
        'id': d.id,
        'name': d.name,
        'price': d.price,
        'photo': d.photo,
        'place_id': d.place_id,
        'place_name': d.place.name,
        'avgRating': float(avg)
    }

    context = get_common_context(request, db)
    context.update({"dish": dish_data, "reviews": reviews_ser})
    return templates.TemplateResponse("dish.html", context)

@app.post("/dishes/{dish_id}")
async def dish_post_review(request: Request, dish_id: int, rating: int = Form(5), text: str = Form(""), db: Session = Depends(get_db)):
    user_id = request.session.get('user_id')
    if not user_id:
        flash(request, "Please login to review")
        return RedirectResponse(request.url_for("login_view"), status_code=303)
    
    r = DishReview(dish_id=dish_id, user_id=user_id, rating=rating, text=text)
    db.add(r)
    
    user = db.query(User).filter(User.id == user_id).first()
    if user: user.total_reviews = (user.total_reviews or 0) + 1
    
    db.commit()
    return RedirectResponse(request.url_for("dish_view", dish_id=dish_id), status_code=303)

@app.post("/reviews/{review_id}/delete")
async def delete_review(request: Request, review_id: int, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r: return RedirectResponse(request.url_for("home"), status_code=303)
    user_id = request.session.get('user_id')
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if not user or (user.role != 'admin' and user.id != r.user_id):
        flash(request, "Not authorized")
        return RedirectResponse(request.url_for("place_view", place_id=r.place_id), status_code=303)
    author = db.query(User).filter(User.id == r.user_id).first()
    if author: author.total_reviews = max(0, (author.total_reviews or 0) - 1)
    place_id = r.place_id
    db.delete(r)
    db.commit()
    return RedirectResponse(request.url_for("place_view", place_id=place_id), status_code=303)

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get('user_id')
    user = db.query(User).filter(User.id == user_id).first() if user_id else None
    if not user: return RedirectResponse(request.url_for("login_view"), status_code=303)
    context = get_common_context(request, db)
    if user.role != 'admin':
        context.update({'error': 'Admins only.'})
        return templates.TemplateResponse("dashboard.html", context)
    
    n_days = 14
    now = datetime.utcnow()
    days_data = [{'date': (now - timedelta(days=i)).strftime('%Y-%m-%d'), 'count': db.query(Review).filter(Review.created_at >= int(datetime(year=(now - timedelta(days=i)).year, month=(now - timedelta(days=i)).month, day=(now - timedelta(days=i)).day).timestamp() * 1000), Review.created_at < int((datetime(year=(now - timedelta(days=i)).year, month=(now - timedelta(days=i)).month, day=(now - timedelta(days=i)).day) + timedelta(days=1)).timestamp() * 1000)).count()} for i in range(n_days - 1, -1, -1)]
    
    total = db.query(Review).count()
    star_only = db.query(Review).filter((Review.text == None) | (Review.text == '')).count()
    star_only_ratio = (star_only / total) * 100 if total else 0
    
    avg_rows = db.query(Place.id, Place.name, func.avg(Review.rating), func.count(Review.id)).join(Review, Review.place_id == Place.id).group_by(Place.id).order_by(func.count(Review.id).desc()).all()
    average_rating_per_place = [{'placeId': r[0], 'name': r[1], 'avgRating': float(r[2] or 0), 'count': int(r[3] or 0)} for r in avg_rows]
    
    day24 = int((now - timedelta(days=1)).timestamp() * 1000)
    recent_reviews = db.query(Review).filter(Review.created_at >= day24).all()
    active_users_today = len(set([r.user_id for r in recent_reviews]))
    
    # --- BML METRICS ---
    
    # 1. Retention Rate (% of users with > 1 review)
    # Validates: Platform stickiness and habit formation.
    users_with_reviews = db.query(User).filter(User.total_reviews > 0).count()
    returning_users = db.query(User).filter(User.total_reviews > 1).count()
    retention_rate = (returning_users / users_with_reviews * 100) if users_with_reviews else 0

    # 2. Contributor Conversion (% of registered users who have posted a review)
    # Validates: The crowdsourcing business model. Are users consuming or producing?
    total_users = db.query(User).count()
    contributor_conversion = (users_with_reviews / total_users * 100) if total_users else 0

    # 3. Growth Velocity (Week-over-Week Review Growth)
    # Validates: Viral growth and adoption rate.
    week_ms = 7 * 24 * 60 * 60 * 1000
    now_ms = int(datetime.utcnow().timestamp() * 1000)
    
    this_week_count = db.query(Review).filter(Review.created_at >= (now_ms - week_ms)).count()
    last_week_count = db.query(Review).filter(Review.created_at >= (now_ms - 2 * week_ms), Review.created_at < (now_ms - week_ms)).count()
    
    if last_week_count > 0:
        growth_velocity = ((this_week_count - last_week_count) / last_week_count) * 100
    else:
        growth_velocity = 100 if this_week_count > 0 else 0

    context.update({
        'totalReviewsPerDay': days_data, 
        'starOnlyRatio': star_only_ratio, 
        'averageRatingPerPlace': average_rating_per_place, 
        'activeUsersToday': active_users_today,
        'retentionRate': retention_rate,
        'contributorConversion': contributor_conversion,
        'growthVelocity': growth_velocity
    })
    return templates.TemplateResponse("dashboard.html", context)

@app.get("/chart/reviews.png")
def chart_reviews_png(db: Session = Depends(get_db)):
    n_days = 14
    now = datetime.utcnow()
    dates, counts = [], []
    for i in range(n_days - 1, -1, -1):
        d = now - timedelta(days=i)
        start = int(datetime(d.year, d.month, d.day).timestamp() * 1000)
        end = start + 24 * 60 * 60 * 1000
        count = db.query(Review).filter(Review.created_at >= start, Review.created_at < end).count()
        dates.append(d.strftime('%Y-%m-%d'))
        counts.append(count)
    fig, ax = plt.subplots(figsize=(8,3))
    ax.plot(dates, counts, marker='o')
    ax.set_title('Reviews per day')
    ax.set_xticks(dates)
    ax.tick_params(axis='x', rotation=45)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")

@app.get("/places/{place_id}/edit", response_class=HTMLResponse)
def edit_place_view(request: Request, place_id: int, db: Session = Depends(get_db)):
    user = get_common_context(request, db)['current_user']
    if not user or user.role != 'admin':
        return RedirectResponse(request.url_for("home"), status_code=303)
        
    place = db.query(Place).filter(Place.id == place_id).first()
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
        
    context = get_common_context(request, db)
    context.update({"place": place})
    return templates.TemplateResponse("edit_place.html", context)

@app.post("/places/{place_id}/edit")
async def edit_place_post(request: Request, place_id: int, name: str = Form(...), type: str = Form(""), address: str = Form(""), tags: str = Form(""), photo: str = Form(""), description: str = Form(""), db: Session = Depends(get_db)):
    user = get_common_context(request, db)['current_user']
    if not user or user.role != 'admin':
        return RedirectResponse(request.url_for("home"), status_code=303)
        
    place = db.query(Place).filter(Place.id == place_id).first()
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
        
    place.name = name
    place.type = type
    place.address = address
    place.tags = tags
    place.photo = photo
    place.description = description
    
    db.commit()
    return RedirectResponse(request.url_for("place_view", place_id=place_id), status_code=303)

@app.get("/places/{place_id}/add_dish", response_class=HTMLResponse)
def add_dish_view(request: Request, place_id: int, db: Session = Depends(get_db)):
    user = get_common_context(request, db)['current_user']
    if not user or user.role != 'admin':
        flash(request, "Admins only")
        return RedirectResponse(request.url_for("place_view", place_id=place_id), status_code=303)
        
    place = db.query(Place).filter(Place.id == place_id).first()
    if not place:
        raise HTTPException(status_code=404, detail="Place not found")
        
    context = get_common_context(request, db)
    context.update({"place": place})
    return templates.TemplateResponse("add_dish.html", context)

@app.post("/places/{place_id}/add_dish")
async def add_dish_post(request: Request, place_id: int, name: str = Form(...), price: int = Form(...), photo: str = Form(""), db: Session = Depends(get_db)):
    user = get_common_context(request, db)['current_user']
    if not user or user.role != 'admin':
        return RedirectResponse(request.url_for("home"), status_code=303)
        
    d = Dish(name=name, price=price, photo=photo, place_id=place_id)
    db.add(d)
    db.commit()
    return RedirectResponse(request.url_for("place_view", place_id=place_id), status_code=303)

if __name__ == '__main__':
    import uvicorn
    uvicorn.run("app:app", host='0.0.0.0', port=8000, reload=True)