import os
from datetime import datetime, timedelta
from flask import Flask, request, redirect, url_for, render_template, flash, session, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from sqlalchemy import text
from uuid import uuid4
import io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- Path resolution to support running app.py outside the server folder ---
BASE_DIR = os.path.dirname(__file__)  # e.g., d:\Code\Critique
REPO_DIR = os.path.abspath(os.path.join(BASE_DIR, '..'))  # e.g., d:\Code

def resolve_templates_dir():
	# Candidates in priority order
	candidates = []
	env_tpl = os.environ.get('CRITIQUE_TEMPLATES_DIR')
	if env_tpl:
		candidates.append(env_tpl)
	# Local typical locations
	candidates.append(os.path.join(BASE_DIR, 'templates'))
	candidates.append(os.path.join(BASE_DIR, 'server', 'templates'))
	# Repo fallbacks (both legacy and new names)
	candidates.append(os.path.join(REPO_DIR, 'Critique', 'server', 'templates'))
	candidates.append(os.path.join(REPO_DIR, 'CampusEats', 'server', 'templates'))
	# Pick the first that exists and contains home.html (strong signal)
	for c in candidates:
		if os.path.isdir(c) and os.path.isfile(os.path.join(c, 'home.html')):
			return c
	# Fallback to the first existing directory, even if file not found
	for c in candidates:
		if os.path.isdir(c):
			return c
	# Last resort: local path
	return os.path.join(BASE_DIR, 'templates')

def resolve_static_dir():
	candidates = []
	env_static = os.environ.get('CRITIQUE_STATIC_DIR')
	if env_static:
		candidates.append(env_static)
	# Local typical locations
	candidates.append(os.path.join(BASE_DIR, 'static'))
	candidates.append(os.path.join(BASE_DIR, 'server', 'static'))
	# Repo fallbacks (both legacy and new names)
	candidates.append(os.path.join(REPO_DIR, 'Critique', 'server', 'static'))
	candidates.append(os.path.join(REPO_DIR, 'CampusEats', 'server', 'static'))
	# Prefer one that contains styles.css
	for c in candidates:
		if os.path.isdir(c) and os.path.isfile(os.path.join(c, 'styles.css')):
			return c
	for c in candidates:
		if os.path.isdir(c):
			return c
	return os.path.join(BASE_DIR, 'static')

TEMPLATES_DIR = resolve_templates_dir()
STATIC_DIR = resolve_static_dir()

def resolve_db_path():
	# 1) Environment override
	env_db = os.environ.get('CRITIQUE_DB_PATH')
	if env_db:
		return env_db
	# 2) Prefer an existing DB from common locations (both names)
	candidates = [
		os.path.join(BASE_DIR, 'critique.db'),
		os.path.join(BASE_DIR, 'campuseats.db'),
		os.path.join(BASE_DIR, 'server', 'critique.db'),
		os.path.join(BASE_DIR, 'server', 'campuseats.db'),
		os.path.join(REPO_DIR, 'Critique', 'server', 'critique.db'),
		os.path.join(REPO_DIR, 'Critique', 'server', 'campuseats.db'),
		os.path.join(REPO_DIR, 'CampusEats', 'server', 'critique.db'),
		os.path.join(REPO_DIR, 'CampusEats', 'server', 'campuseats.db'),
	]
	for c in candidates:
		if os.path.exists(c):
			return c
	# 3) Default to a new name aligned with the project rename
	return os.path.join(BASE_DIR, 'critique.db')

DB_PATH = resolve_db_path()

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.secret_key = os.environ.get('CRITIQUE_SECRET') or os.environ.get('CAMPUS_EATS_SECRET', 'dev-secret')
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
CORS(app)
db = SQLAlchemy(app)


def now_ts():
	return int(datetime.utcnow().timestamp() * 1000)


# Shared constants
PLACE_TYPES = [
	'Cafeteria',
	'Cafe',
	'Restaurant',
	'Food Truck',
	'Bakery',
	'Fast Food',
	'Desserts',
	'Beverages',
	'Other'
]


def compute_reviews_per_day(n_days: int = 14):
    now = datetime.utcnow()
    days = []
    for i in range(n_days - 1, -1, -1):
        d = now - timedelta(days=i)
        start = int(datetime(d.year, d.month, d.day).timestamp() * 1000)
        end = start + 24 * 60 * 60 * 1000
        count = Review.query.filter(Review.created_at >= start, Review.created_at < end).count()
        days.append({'date': datetime.utcfromtimestamp(start / 1000).strftime('%Y-%m-%d'), 'count': count})
    return days


class User(db.Model):
	id = db.Column(db.String, primary_key=True)
	email = db.Column(db.String, unique=True, nullable=False)
	name = db.Column(db.String, nullable=False)
	role = db.Column(db.String(10), nullable=False, default='student')  # 'admin' or 'student'
	university = db.Column(db.String, nullable=True)
	password = db.Column(db.String, nullable=True)
	total_reviews = db.Column(db.Integer, default=0)


class Place(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String, nullable=False)
	type = db.Column(db.String, nullable=True)
	address = db.Column(db.String, nullable=True)
	photo = db.Column(db.String, nullable=True)
	tags = db.Column(db.String, nullable=True)  # comma separated
	creator_id = db.Column(db.String, db.ForeignKey('user.id'), nullable=True)
	description = db.Column(db.Text, nullable=True)
	created_at = db.Column(db.Integer, default=lambda: now_ts())


class Review(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	place_id = db.Column(db.Integer, db.ForeignKey('place.id'), nullable=False)
	user_id = db.Column(db.String, db.ForeignKey('user.id'), nullable=False)
	rating = db.Column(db.Integer, nullable=False)
	text = db.Column(db.Text, nullable=True)
	created_at = db.Column(db.Integer, default=lambda: now_ts())


def init_db():
	if not os.path.exists(DB_PATH):
		db.create_all()
		print('Initialized database at', DB_PATH)


def ensure_place_creator_column():
	# Ensure the 'creator_id' column exists on 'place' table (SQLite)
	try:
		res = db.session.execute(text('PRAGMA table_info(place)'))
		cols = [row[1] for row in res]
		if 'creator_id' not in cols:
			db.session.execute(text('ALTER TABLE place ADD COLUMN creator_id TEXT'))
			db.session.commit()
			print("Added 'creator_id' column to 'place' table")
	except Exception as e:
		print('ensure_place_creator_column error:', e)


def ensure_place_description_column():
	# Ensure the 'description' column exists on 'place' table (SQLite)
	try:
		res = db.session.execute(text('PRAGMA table_info(place)'))
		cols = [row[1] for row in res]
		if 'description' not in cols:
			db.session.execute(text('ALTER TABLE place ADD COLUMN description TEXT'))
			db.session.commit()
			print("Added 'description' column to 'place' table")
	except Exception as e:
		print('ensure_place_description_column error:', e)


def serialize_place(place):
	avg = db.session.query(func.avg(Review.rating)).filter(Review.place_id == place.id).scalar() or 0
	creator_name = None
	if getattr(place, 'creator_id', None):
		cu = User.query.get(place.creator_id)
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
		'creatorId': getattr(place, 'creator_id', None),
		'creatorName': creator_name,
		'description': getattr(place, 'description', None)
	}


@app.context_processor
def inject_user():
	uid = session.get('user_id')
	user = None
	if uid:
		user = User.query.get(uid)
	return {'current_user': user, 'place_types': PLACE_TYPES}


@app.route('/')
def home():
	q = request.args.get('q', '')
	tag = request.args.get('tag','')
	places = Place.query.all()
	results = [p for p in places if q.lower() in p.name.lower() and (not tag or (p.tags and tag in p.tags.split(',')))]
	serialized = [serialize_place(p) for p in results]
	# trending: top 3 by review count
	place_counts = []
	for p in places:
		count = Review.query.filter_by(place_id=p.id).count()
		place_counts.append((p, count))
	place_counts.sort(key=lambda x: x[1], reverse=True)
	trending = [serialize_place(p[0]) for p in place_counts[:3]]
	return render_template('home.html', places=serialized, trending=trending, q=q, tag=tag)


@app.route('/register', methods=['GET','POST'])
def register_view():
	if request.method == 'POST':
		email = request.form.get('email')
		name = request.form.get('name')
		if not email or not name:
			flash('email and name required')
			return redirect(url_for('register_view'))
		if User.query.filter_by(email=email).first():
			flash('already exists')
			return redirect(url_for('register_view'))
		role = 'student'
		admin_code = request.form.get('admin_code')
		valid_codes = [os.environ.get('CRITIQUE_ADMIN_CODE'), 'campuseatsadmin2025']
		if admin_code and admin_code in [c for c in valid_codes if c]:
			role = 'admin'
		user = User(id=str(uuid4()), email=email, name=name, university=request.form.get('university',''), password=request.form.get('password','pass'), role=role)
		db.session.add(user)
		db.session.commit()
		session['user_id'] = user.id
		return redirect(url_for('home'))
	return render_template('register.html')


@app.route('/login', methods=['GET','POST'])
def login_view():
	if request.method == 'POST':
		email = request.form.get('email')
		password = request.form.get('password')
		user = User.query.filter_by(email=email).first()
		if not user:
			flash('Account not found')
			return redirect(url_for('login_view'))
		if not password or user.password != password:
			flash('Invalid email or password')
			return redirect(url_for('login_view'))
		session['user_id'] = user.id
		return redirect(url_for('home'))
	return render_template('login.html')


@app.route('/logout')
def logout_view():
	session.pop('user_id', None)
	return redirect(url_for('home'))


@app.route('/places/new', methods=['GET','POST'])
def new_place():
	# Require login to access add place (both GET form and POST submission)
	user_id = session.get('user_id')
	if not user_id:
		flash('Please login to add a place')
		return redirect(url_for('login_view'))
	if request.method == 'POST':
		name = request.form.get('name')
		if not name:
			flash('name required')
			return redirect(url_for('new_place'))
		tags = request.form.get('tags','')
		p = Place(
			name=name,
			type=request.form.get('type',''),
			address=request.form.get('address',''),
			tags=tags,
			description=request.form.get('description',''),
			creator_id=user_id
		)
		db.session.add(p)
		db.session.commit()
		return redirect(url_for('home'))
	return render_template('add_place.html')


@app.route('/places/<int:place_id>', methods=['GET','POST'])
def place_view(place_id):
	p = Place.query.get_or_404(place_id)
	if request.method == 'POST':
		# post review
		user_id = session.get('user_id')
		if not user_id:
			flash('Please login to post reviews')
			return redirect(url_for('login_view'))
		rating = int(request.form.get('rating',5))
		text = request.form.get('text','')
		r = Review(place_id=place_id, user_id=user_id, rating=rating, text=text)
		db.session.add(r)
		user = User.query.get(user_id)
		if user:
			user.total_reviews = (user.total_reviews or 0) + 1
		db.session.commit()
		return redirect(url_for('place_view', place_id=place_id))
	reviews = Review.query.filter_by(place_id=place_id).order_by(Review.created_at.desc()).all()
	reviews_ser = []
	for r in reviews:
		u = User.query.get(r.user_id)
		reviews_ser.append({'id': r.id, 'user': u.name if u else r.user_id, 'rating': r.rating, 'text': r.text, 'createdAt': r.created_at, 'userId': r.user_id})
	return render_template('place.html', place=serialize_place(p), reviews=reviews_ser)


@app.route('/places/<int:place_id>/delete', methods=['POST'])
def delete_place(place_id):
	# Admin-only: delete a place and all its reviews
	user_id = session.get('user_id')
	if not user_id:
		flash('Please login as admin to delete places')
		return redirect(url_for('login_view'))
	current_user = User.query.get(user_id)
	if not current_user or current_user.role != 'admin':
		flash('Admins only')
		return redirect(url_for('place_view', place_id=place_id))

	place = Place.query.get_or_404(place_id)

	# Decrement authors' review counts and delete associated reviews
	reviews = Review.query.filter_by(place_id=place_id).all()
	for r in reviews:
		author = User.query.get(r.user_id)
		if author:
			author.total_reviews = max(0, (author.total_reviews or 0) - 1)
		db.session.delete(r)

	db.session.delete(place)
	db.session.commit()
	flash('Place deleted')
	return redirect(url_for('home'))


@app.route('/reviews/<int:review_id>/edit', methods=['POST'])
def edit_review(review_id):
	r = Review.query.get_or_404(review_id)
	user_id = session.get('user_id')
	if not user_id or user_id != r.user_id:
		flash('Not authorized')
		return redirect(url_for('place_view', place_id=r.place_id))
	r.text = request.form.get('text', r.text)
	r.rating = int(request.form.get('rating', r.rating))
	db.session.commit()
	return redirect(url_for('place_view', place_id=r.place_id))


@app.route('/reviews/<int:review_id>/delete', methods=['POST'])
def delete_review(review_id):
	r = Review.query.get_or_404(review_id)
	user_id = session.get('user_id')
	if not user_id:
		flash('Not authorized')
		return redirect(url_for('place_view', place_id=r.place_id))
	current_user = User.query.get(user_id)
	if not current_user or (current_user.role != 'admin' and user_id != r.user_id):
		flash('Not authorized')
		return redirect(url_for('place_view', place_id=r.place_id))
	user = User.query.get(r.user_id)
	if user:
		user.total_reviews = max(0, (user.total_reviews or 0) - 1)
	db.session.delete(r)
	db.session.commit()
	return redirect(url_for('place_view', place_id=r.place_id))


def generate_reviews_per_day_chart(days):
	dates = [d['date'] for d in days]
	counts = [d['count'] for d in days]
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
	return buf


@app.route('/dashboard')
def dashboard():
	def get_current_user():
		user_id = session.get('user_id')
		if user_id:
			return User.query.filter_by(id=user_id).first()
		return None
	user = get_current_user()
	if not user:
		return redirect(url_for('login_view'))
	if user.role != 'admin':
		return render_template('dashboard.html',
			error='Admins only: metrics are restricted.',
			totalReviewsPerDay=None,
			starOnlyRatio=None,
			averageRatingPerPlace=None,
			activeUsersToday=None)
	days = compute_reviews_per_day(14)

	total = Review.query.count()
	star_only = Review.query.filter((Review.text == None) | (Review.text == '')).count()
	star_only_ratio_pct = (star_only / total) * 100 if total else 0

	# Average rating per place (with review counts)
	avg_rows = (
		db.session.query(
			Place.id,
			Place.name,
			func.avg(Review.rating).label('avg_rating'),
			func.count(Review.id).label('review_count')
		)
		.join(Review, Review.place_id == Place.id)
		.group_by(Place.id)
		.order_by(func.count(Review.id).desc())
		.all()
	)
	average_rating_per_place = [
		{
			'placeId': r[0],
			'name': r[1],
			'avgRating': float(r[2] or 0),
			'count': int(r[3] or 0)
		} for r in avg_rows
	]

	now = datetime.utcnow()
	day24 = int((now - timedelta(days=1)).timestamp() * 1000)
	active_users_today = len(set([r.user_id for r in Review.query.filter(Review.created_at >= day24).all()]))

	# Render with the requested metric names
	return render_template(
		'dashboard.html',
		totalReviewsPerDay=days,
		starOnlyRatio=star_only_ratio_pct,
		averageRatingPerPlace=average_rating_per_place,
		activeUsersToday=active_users_today
	)


@app.route('/chart/reviews.png')
def chart_reviews_png():
	# return latest chart via regenerating
	days = compute_reviews_per_day(14)
	buf = generate_reviews_per_day_chart(days)
	return send_file(buf, mimetype='image/png')


if __name__ == '__main__':
	with app.app_context():
		init_db()
		ensure_place_creator_column()
		ensure_place_description_column()
	app.run(host='0.0.0.0', port=5000, debug=True)
