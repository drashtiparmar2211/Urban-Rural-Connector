"""
Urban Rural Connector - Flask Application
A platform connecting rural producers with urban consumers
Author: Dasu (B.Tech CSE Student)
Features: Functional Auth, Dynamic Location Fields, AI Image Placeholders, Knowledge Hub, Category Filtering, Categorized Flash Messages
"""

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from flask import Flask
from config import Config # Import your new class
from itsdangerous import URLSafeTimedSerializer
from flask_mail import Mail, Message  # <--- ADD THIS LINE
from config import Config  # Make sure this import is correct based on your project structure
from groq import Groq # Import Groq instead of GenAI
from flask import Flask, request, jsonify
import math
import random
import string
import sqlite3
from flask import send_from_directory
from flask import Flask, request, jsonify, g, send_from_directory
from flask_cors import CORS
import os, random, string, math, sqlite3
from datetime import datetime, timedelta

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config) # Load the settings

mail = Mail(app)
# Initialize the serializer using your Secret Key
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

client = Groq(api_key="YOUR_API_KEY")

DATABASE = "instance/urc_transport.db" # Updated to match your instance folder
BASE_FARE = 20.0
RATE_PER_KM = 8.0

TIER_CONFIG = {
    1: {"name": "Instant",  "allow_group": False, "threshold": 1,  "max_wait_hrs": 0},
    2: {"name": "Priority", "allow_group": True,  "threshold": 2,  "max_wait_hrs": 4},
    3: {"name": "Standard", "allow_group": True,  "threshold": 5,  "max_wait_hrs": 12},
}

# ==================== CONFIGURATION ====================
app.config['SECRET_KEY'] = 'urc-india-secret-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///urc_database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Upload Configuration
UPLOAD_FOLDER = 'static/images/products'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(os.path.join(app.root_path, UPLOAD_FOLDER), exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

def allowed_file(filename):
    """ Helper to check image extensions """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== DATABASE MODELS ====================

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'rural' or 'urban'
    location = db.Column(db.String(200), nullable=False) # State
    village = db.Column(db.String(100)) # Rural only
    city = db.Column(db.String(100))    # Urban only
    address = db.Column(db.Text)        # Full address
    aadhaar_verified = db.Column(db.Boolean, default=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    products = db.relationship('Product', backref='seller', lazy=True, cascade='all, delete-orphan')
    stories = db.relationship('Story', backref='author', lazy=True, cascade='all, delete-orphan')
    contributions = db.relationship('Contribution', backref='contributor', lazy=True)

    def __repr__(self):
        return f'<User {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    product_biography = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False) # dairy, crops, handicrafts, vegetables
    image_url = db.Column(db.String(300))
    is_available = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Story(db.Model):
    __tablename__ = 'stories'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    media_url = db.Column(db.String(300), nullable=False)
    media_type = db.Column(db.String(10), nullable=False)
    caption = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Contribution(db.Model):
    """ Model for Knowledge Hub: Remedies (Rural) or Tech Ideas (Urban) """
    __tablename__ = 'contributions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20)) # 'remedy' or 'tech_idea'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Order(db.Model):
    __tablename__ = 'orders'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # ADD THIS
    product_name = db.Column(db.String(150), nullable=False)
    price = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Processing') # Current state of the item
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Order {self.product_name}>'

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db

@app.teardown_appcontext
def close_db(exc):
    db = getattr(g, "_database", None)
    if db: db.close()

def init_db():
    with app.app_context():
        db = get_db()
        with open("schema.sql") as f:
            db.executescript(f.read())
        db.commit()
        _seed_demo_data(db)

def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rv  = cur.fetchall()
    return (rv[0] if rv else None) if one else rv

def execute(sql, args=()):
    db  = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid

def row_to_dict(row):
    return dict(row) if row else None



# ==================== AUTH ROUTES ====================

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        email = request.form.get('email')
        role = request.form.get('role')
        location = request.form.get('location')
        village = request.form.get('village')
        city = request.form.get('city')
        address = request.form.get('address')
        password = request.form.get('password')

        # Check if email or phone is already linked to ANY account
        existing_user = User.query.filter((User.phone == phone) | (User.email == email)).first()
        if existing_user:
            # If the user exists with a different role, we explain why they can't sign up again
            if existing_user.role != role:
                flash(f'This identifier is already registered as {existing_user.role.upper()}. To use a different role, please use a different email/phone.', 'error')
            else:
                flash('Account already exists with this Email or Phone!', 'error')
            return redirect(url_for('signup'))

        new_user = User(
            name=name, phone=phone, email=email, role=role,
            location=location, village=village, city=city,
            address=address, password_hash=generate_password_hash(password)
        )
        
        db.session.add(new_user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash("Please login to add items to your cart.", "warning")
        return redirect(url_for('login'))

    # Initialize cart in session if it doesn't exist
    if 'cart' not in session:
        session['cart'] = []

    # Get the current cart list from session
    cart = session.get('cart', [])
    
    # Add the product ID if it's not already there
    if product_id not in cart:
        cart.append(product_id)
        session['cart'] = cart # Save updated list back to session
        flash("Product added to your cart!", "success")
    else:
        flash("Product is already in your cart.", "info")

    # This sends the user back to the page they were just on
    return redirect(request.referrer)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identity = request.form.get('identity')
        password = request.form.get('password')

        user = User.query.filter((User.email == identity) | (User.phone == identity)).first()

        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_role'] = user.role
            
            flash(f'Welcome back, {user.name}!', 'success')
            return redirect(url_for('dashboard', user_id=user.id))
        
        # CATEGORIZED AS ERROR for the dialog box popup
        flash('Invalid Credentials: Wrong Phone/Email or Password.', 'error')
    return render_template('login.html')

@app.route("/forgot_password", methods=['GET', 'POST'])
def forgot_password_request():
    if request.method == 'POST':
        user_email = request.form.get('email')
        
        # Check if user actually exists in your DB
        user = User.query.filter_by(email=user_email).first()
        
        if user:
            # Generate a secure token containing the email
            token = s.dumps(user_email, salt='password-reset-salt')
            link = url_for('reset_token', token=token, _external=True)
            
            msg = Message('Password Reset Request - Urban Rural Connector',
                          sender=app.config['MAIL_DEFAULT_SENDER'],
                          recipients=[user_email])
            msg.body = f"To reset your password, click this link: {link}\nIf you did not request this, ignore this email."
            
            try:
                mail.send(msg)
                flash('Check your email for the reset link!', 'info')
            except Exception as e:
                print(f"Mail Error: {e}")
                flash('Error sending mail. Check your connection.', 'error')
        else:
            flash('No account found with that email.', 'warning')
            
        return redirect(url_for('login'))
    
    return render_template('reset_request.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get('message')
    sec = data.get('section')

    instructions = {
       "rural": """
        You are the Rural Aide for the 'Urban Rural Connector' (URC). 
        FACTS YOU MUST KNOW:
        1. Farmers list products via the 'Add Crop' page.
        2. Products are collected at 'Village Hubs'.
        3. Farmers get paid via the 'Payment Module' after urban delivery is verified.
        4. There is a '3-tier' logistics system: Self-pickup, Group-pickup, and Standard.
    """,
    "urban": """
        You are the Urban Assistant for the 'Urban Rural Connector' (URC). 
        FACTS YOU MUST KNOW:
        1. Consumers can buy fresh village products directly.
        2. 'Group Pickup' saves 20% on delivery costs if 5 neighbors join.
        3. All products are verified with photos before shipping.
        4. Delivery happens via the 'City Warehouse' to the consumer's door.
    """,
    "transport": """
        You are the URC Logistics Expert. 
        FACTS YOU MUST KNOW:
        1. Security uses a 'Dual-OTP' system (one for pickup, one for delivery).
        2. Drivers must take a 'Condition Photo' at the Village Hub.
        3. We use 'Reverse Logistics' (trucks bring city supplies back to villages to save fuel).
        4. If a product is perishable, it follows the 'Priority Route'.
    """,
    "general": "You are the assistant for URC (Urban Rural Connector), a platform linking Indian farmers directly to city shops to remove middlemen."
    }
    
    context = instructions.get(sec, "You are a general URC assistant.")
    
    try:
        # 2. Call the Groq API (The structure is slightly different)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile", # This is a powerful free model on Groq
            messages=[
                {"role": "system", "content": context},
                {"role": "user", "content": msg}
            ]
        )
        return jsonify({"response": completion.choices[0].message.content})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"response": "I'm having trouble connecting right now."}), 500
    
@app.route("/reset_password/<token>", methods=['GET', 'POST'])
def reset_token(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=1800)
    except:
        flash('Link expired.', 'error')
        return redirect(url_for('forgot_password_request'))
    
    if request.method == 'POST':
        new_password = request.form.get('password')
        user = User.query.filter_by(email=email).first()
        if user:
            # FIX: Hashing the new password so login works
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash('Password updated!', 'success')
            return redirect(url_for('login'))
    return render_template('reset_token.html', token=token)

@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(session['user_id'])
    
    if request.method == 'POST':
        # Get data from the form
        user.name = request.form.get('name')
        user.location = request.form.get('location')
        user.address = request.form.get('address')
        user.village = request.form.get('village')
        user.city = request.form.get('city')
        
        # Save to urc_database.db
        try:
            db.session.commit()
            session['user_name'] = user.name  # Update session name too
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            db.session.rollback()
            flash('Error updating profile.', 'error')
            print(f"Update Error: {e}")

    return render_template('edit_profile.html', user=user)

# --- ADD THESE THREE ROUTES ---

@app.route('/cart')
def view_cart():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get product IDs from session
    cart_ids = session.get('cart', [])
    
    # Fetch products from DB
    cart_items = Product.query.filter(Product.id.in_(cart_ids)).all() if cart_ids else []
    total_price = sum(item.price for item in cart_items)
    
    return render_template('cart.html', items=cart_items, total=total_price)

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    cart = session.get('cart', [])
    if product_id in cart:
        cart.remove(product_id)
        session['cart'] = cart
        flash("Item removed from cart.", "info")
    return redirect(url_for('view_cart'))

@app.route('/my_orders')
def my_orders():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get_or_404(session['user_id'])
    orders = Order.query.filter_by(user_id=session['user_id']).all()
    return render_template('my_orders.html', user=user)

@app.route('/complete_order/<int:order_id>')
def complete_order(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order) # REMOVE from My Orders once reached buyer
    db.session.commit()
    flash("Order received! Thank you for supporting rural India.", "success")
    return redirect(url_for('my_orders'))

@app.route('/impact_journey')
def impact_journey():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get_or_404(session['user_id'])
    return render_template('impact_journey.html', user=user, impact=1250)

@app.route('/checkout')
def checkout():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    cart_ids = session.get('cart', [])
    if not cart_ids:
        flash("Your cart is empty!", "warning")
        return redirect(url_for('shop'))

    # Logic: For the project demo, we clear the cart to simulate a purchase.
    # In a real app, you would save these to an 'Order' table in urc_database.db
    session.pop('cart', None) 
    
    flash("Purchase Successful! Your order has been placed with the rural producer.", "success")
    return redirect(url_for('dashboard', user_id=session['user_id']))

@app.route('/logout')
def logout():
    session.clear()
    flash('Successfully logged out.', 'success')
    return redirect(url_for('homepage'))


# ==================== MAIN ROUTES ====================

@app.route('/')
def homepage():
    featured_sellers = User.query.filter_by(role='rural').limit(3).all()
    return render_template('homepage.html', featured_sellers=featured_sellers)


@app.route('/dashboard/<int:user_id>')
def dashboard(user_id):
    if 'user_id' not in session or session['user_id'] != user_id:
        return redirect(url_for('login'))
        
    user = User.query.get_or_404(user_id)
    
    remedies = Contribution.query.filter_by(type='remedy').order_by(Contribution.created_at.desc()).limit(5).all()
    tech_ideas = Contribution.query.filter_by(type='tech_idea').order_by(Contribution.created_at.desc()).limit(5).all()

    if user.role == 'rural':
        products = Product.query.filter_by(seller_id=user_id).all()
        stories = Story.query.filter_by(user_id=user_id).order_by(Story.created_at.desc()).limit(10).all()
        return render_template('seller_dashboard.html', user=user, products=products, stories=stories, tech_ideas=tech_ideas)
    else:
        all_products = Product.query.filter_by(is_available=True).all()
        return render_template('buyer_dashboard.html', user=user, products=all_products, remedies=remedies, total_impact=0.0)

# --- NEW PROFILE ROUTE ADDED HERE ---
@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Fetch current logged-in user data
    user = User.query.get_or_404(session['user_id'])
    return render_template('profile.html', user=user)


@app.route('/submit-contribution', methods=['POST'])
def submit_contribution():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    title = request.form.get('title')
    content = request.form.get('content')
    
    contrib_type = 'remedy' if user.role == 'rural' else 'tech_idea'
    
    new_contrib = Contribution(user_id=user.id, title=title, content=content, type=contrib_type)
    db.session.add(new_contrib)
    db.session.commit()
    
    flash('Thank you for sharing your knowledge!', 'success')
    return redirect(request.referrer)


@app.route('/shop')
def shop():
    if 'user_id' not in session:
        flash("Please login to browse the shop.", "info")
        return redirect(url_for('login'))
    
    category = request.args.get('category')
    if category:
        products = Product.query.filter_by(category=category, is_available=True).all()
    else:
        products = Product.query.filter_by(is_available=True).all()
        
    return render_template('shop.html', products=products)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/reverse-market')
def reverse_market():
    return render_template('reverse_market.html')


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    seller = User.query.get(product.seller_id)
    return render_template('product_detail.html', product=product, seller=seller)


# ==================== PRODUCT MANAGEMENT ====================

@app.route('/add-product', methods=['GET', 'POST'])
def add_product():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form.get('title')
        price = request.form.get('price')
        category = request.form.get('category')
        biography = request.form.get('biography')
        file = request.files.get('product_image')

        ai_placeholders = {
            'crops': 'ai_organic_wheat.jpg',
            'handicrafts': 'ai_artisan_pottery.jpg',
            'dairy': 'ai_fresh_milk.jpg',
            'vegetables': 'ai_fresh_veggies.jpg'
        }
        image_to_save = ai_placeholders.get(category, 'placeholder-product.jpg')

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.root_path, app.config['UPLOAD_FOLDER'], filename))
            image_to_save = 'products/' + filename

        new_product = Product(
            seller_id=session['user_id'], 
            title=title,
            product_biography=biography,
            price=float(price) if price else 0.0,
            category=category,
            image_url=image_to_save
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Product listed successfully!', 'success')
        return redirect(url_for('shop'))

    return render_template('add_product.html')

@app.route('/payment')
def payment_page():
    if 'user_id' not in session: return redirect(url_for('login'))
    
    cart_ids = session.get('cart', [])
    cart_items = Product.query.filter(Product.id.in_(cart_ids)).all()
    total = sum(item.price for item in cart_items)
    
    return render_template('payment.html', total=total)

@app.route('/process_payment', methods=['POST'])
def process_payment():
    cart_ids = session.get('cart', [])
    cart_items = Product.query.filter(Product.id.in_(cart_ids)).all()
    # Inside process_payment loop:
    for item in cart_items:
        item.is_available = False # Or decrease quantity

    for item in cart_items:
        new_order = Order(
            user_id=session['user_id'],
            seller_id=item.user_id, # Link this to the Producer
            product_name=item.title,
            price=item.price,
            status='New Order'
        )
        db.session.add(new_order)
    
    db.session.commit()
    session.pop('cart', None)
    flash("Payment Successful!", "success")
    return redirect(url_for('my_orders'))

@app.route('/seller_orders')
def seller_orders():
    if 'user_id' not in session or session.get('user_role') != 'rural':
        return redirect(url_for('login'))
    
    # Get only the orders where THIS user is the seller
    incoming_orders = Order.query.filter_by(seller_id=session['user_id']).all()
    
    return render_template('seller_orders.html', orders=incoming_orders)


# Add missing edit-product route to prevent errors in Producer Dashboard
@app.route('/edit-product/<int:product_id>')
def edit_product(product_id):
    flash('Edit feature coming soon!', 'info')
    return redirect(url_for('dashboard', user_id=session.get('user_id')))

@app.route('/knowledge-hub')
def knowledge_hub():
    # Fetch all contributions from the database
    remedies = Contribution.query.filter_by(type='remedy').order_by(Contribution.created_at.desc()).all()
    tech_ideas = Contribution.query.filter_by(type='tech_idea').order_by(Contribution.created_at.desc()).all()
    return render_template('knowledge_hub.html', remedies=remedies, tech_ideas=tech_ideas)


@app.route('/upload-story', methods=['POST'])
def upload_story():
    flash('Story shared successfully!', 'success')
    return redirect(request.referrer)

@app.route("/transport")
def transport_page():
    # This serves the transportation HTML file you just moved
    return render_template("transport_module.html")

def haversine_km(lat1, lng1, lat2, lng2):
    """Straight-line distance in km between two GPS points."""
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng/2)**2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calc_delivery_cost(distance_km, vehicle_type="auto"):
    multiplier = {"bike": 0.8, "auto": 1.0, "truck": 1.5}.get(vehicle_type, 1.0)
    return round((BASE_FARE + distance_km * RATE_PER_KM) * multiplier, 2)

def gen_otp(length=6):
    return "".join(random.choices(string.digits, k=length))

def gen_pickup_id():
    return "PID-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=8))

def ok(data=None, msg="success", code=200):
    return jsonify({"status": "ok", "message": msg, "data": data}), code

def err(msg="error", code=400):
    return jsonify({"status": "error", "message": msg}), code

def _seed_demo_data(db):
    existing = db.execute("SELECT COUNT(*) FROM producers").fetchone()[0]
    if existing: return

    producers = [
        ("Ramesh Patel",  "+919876543210", 22.8462, 73.1641, "Anand Village, Vadodara", "Near Mango Farm"),
        ("Sunita Devi",   "+919876543211", 22.7927, 73.1923, "Padra, Vadodara",         "Main Bus Stand"),
        ("Gopal Singh",   "+919876543212", 22.9142, 73.0891, "Karjan, Vadodara",        "Old Banyan Tree"),
    ]
    db.executemany(
        "INSERT INTO producers(name,phone,gps_lat,gps_lng,address,landmark) VALUES(?,?,?,?,?,?)",
        producers
    )

    buyers = [
        ("Anita Shah",   "+917654321098", "12 Race Course, Vadodara", "Vadodara"),
        ("Mihir Joshi",  "+917654321099", "Alkapuri, Vadodara",       "Vadodara"),
    ]
    db.executemany(
        "INSERT INTO buyers(name,phone,address,city) VALUES(?,?,?,?)", buyers
    )

    drivers = [
        ("Vijay Kumar",  "+918765432109", "auto",  "GJ-06-XY-1234", 22.8500, 73.1700),
        ("Raju Bhai",    "+918765432108", "bike",  "GJ-06-AB-9999", 22.7900, 73.1950),
        ("Karan Malik",  "+918765432107", "truck", "GJ-06-TR-5555", 22.9000, 73.0900),
    ]
    db.executemany(
        "INSERT INTO drivers(name,phone,vehicle_type,vehicle_num,gps_lat,gps_lng) VALUES(?,?,?,?,?,?)",
        drivers
    )

    products = [
        (1, "Fresh Milk",       "dairy",      1, 55.0,  "litre", 50),
        (1, "Alphonso Mangoes", "fruit",      2, 120.0, "kg",    200),
        (2, "Organic Wheat",    "grain",      3, 28.0,  "kg",    500),
        (2, "Mixed Vegetables", "vegetable",  2, 40.0,  "kg",    100),
        (3, "Basmati Rice",     "grain",      3, 65.0,  "kg",    300),
        (3, "Handmade Baskets", "handicraft", 3, 250.0, "piece",  30),
    ]
    db.executemany(
        "INSERT INTO products(producer_id,name,category,perishability,price_per_unit,unit,stock) VALUES(?,?,?,?,?,?,?)",
        products
    )

    db.commit()
    print("[SEED] Demo data inserted.")

@app.get("/api/products")
def list_products():
    rows = query("""
        SELECT p.*, pr.name as producer_name, pr.gps_lat, pr.gps_lng,
               pr.address, pr.landmark, pr.rating as producer_rating
        FROM products p
        JOIN producers pr ON p.producer_id = pr.id
        WHERE p.stock > 0
    """)
    return ok([row_to_dict(r) for r in rows])

@app.get("/api/products/<int:pid>")
def get_product(pid):
    row = query("""
        SELECT p.*, pr.name as producer_name, pr.phone as producer_phone,
               pr.gps_lat, pr.gps_lng, pr.address, pr.landmark, pr.rating as producer_rating
        FROM products p JOIN producers pr ON p.producer_id = pr.id
        WHERE p.id = ?
    """, (pid,), one=True)
    if not row: return err("Product not found", 404)
    return ok(row_to_dict(row))


@app.get("/api/producers")
def list_producers():
    rows = query("SELECT * FROM producers")
    return ok([row_to_dict(r) for r in rows])

@app.get("/api/delivery/options/<int:product_id>")
def delivery_options(product_id):
    """Return available delivery methods based on product perishability."""
    prod = query("SELECT * FROM products WHERE id=?", (product_id,), one=True)
    if not prod: return err("Product not found", 404)

    tier    = prod["perishability"]
    config  = TIER_CONFIG[tier]
    options = []

    options.append({
        "type": "self",
        "label": "Self Pickup (Direct-from-Farm)",
        "cost": 0,
        "description": "Collect directly from the farm. Free!",
        "available": True,
    })

    if config["allow_group"]:
        group = query("""
            SELECT * FROM active_groups
            WHERE product_id=? AND status='open'
            ORDER BY created_at DESC LIMIT 1
        """, (product_id,), one=True)
        options.append({
            "type": "group",
            "label": "Group Pickup (Community Economy)",
            "cost": "Shared cost",
            "description": f"Join with neighbors. {config['threshold']} orders trigger a driver.",
            "available": True,
            "group_info": row_to_dict(group) if group else None,
            "threshold": config["threshold"],
            "max_wait_hrs": config["max_wait_hrs"],
        })

    options.append({
        "type": "standard",
        "label": "Standard Delivery (Door-to-Door)",
        "cost": "Based on distance",
        "description": "Dedicated driver. Live GPS tracking.",
        "available": True,
    })

    return ok({
        "product_id": product_id,
        "perishability_tier": tier,
        "tier_name": config["name"],
        "options": options,
    })


@app.post("/api/delivery/quote")
def delivery_quote():
    """Calculate delivery cost for a buyer–producer pair."""
    data = request.json or {}
    prod_id    = data.get("product_id")
    buyer_lat  = data.get("buyer_lat")
    buyer_lng  = data.get("buyer_lng")
    dtype      = data.get("delivery_type", "standard")

    if not all([prod_id, buyer_lat, buyer_lng]):
        return err("product_id, buyer_lat, buyer_lng required")

    prod = query("""
        SELECT p.*, pr.gps_lat, pr.gps_lng FROM products p
        JOIN producers pr ON p.producer_id = pr.id WHERE p.id = ?
    """, (prod_id,), one=True)
    if not prod: return err("Product not found", 404)

    dist = haversine_km(prod["gps_lat"], prod["gps_lng"], buyer_lat, buyer_lng)

    if dtype == "self":
        cost = 0.0
    elif dtype == "group":
       
        cost = calc_delivery_cost(dist)
    else:
        cost = calc_delivery_cost(dist)

    return ok({
        "distance_km": round(dist, 2),
        "delivery_cost": cost,
        "formula": f"₹{BASE_FARE} base + {dist:.1f}km × ₹{RATE_PER_KM}/km",
    })


@app.post("/api/orders")
def create_order():
    data = request.json or {}
    required = ["buyer_id", "product_id", "quantity", "delivery_type"]
    if not all(k in data for k in required):
        return err(f"Missing fields: {required}")

    buyer_id      = data["buyer_id"]
    product_id    = data["product_id"]
    quantity      = int(data["quantity"])
    delivery_type = data["delivery_type"]   
    buyer_lat     = data.get("buyer_lat")
    buyer_lng     = data.get("buyer_lng")

    prod = query("""
        SELECT p.*, pr.gps_lat as farm_lat, pr.gps_lng as farm_lng, pr.id as farm_id
        FROM products p JOIN producers pr ON p.producer_id = pr.id
        WHERE p.id = ?
    """, (product_id,), one=True)
    if not prod: return err("Product not found", 404)
    if prod["stock"] < quantity: return err("Insufficient stock")

    tier = prod["perishability"]
    if delivery_type == "group" and not TIER_CONFIG[tier]["allow_group"]:
        return err("Group delivery not allowed for Tier-1 (Instant) products")

    total_price   = round(prod["price_per_unit"] * quantity, 2)
    distance_km   = 0.0
    delivery_cost = 0.0
    driver_id     = None
    group_id      = None
    pickup_id     = None

    if delivery_type == "self":
        pickup_id = gen_pickup_id()

    elif delivery_type == "standard":
        if not (buyer_lat and buyer_lng):
            return err("buyer_lat and buyer_lng required for standard delivery")
        distance_km   = haversine_km(prod["farm_lat"], prod["farm_lng"], buyer_lat, buyer_lng)
        delivery_cost = calc_delivery_cost(distance_km)
    
        drv = query("SELECT * FROM drivers WHERE is_available=1 ORDER BY RANDOM() LIMIT 1", one=True)
        if drv: driver_id = drv["id"]

    elif delivery_type == "group":
        cfg  = TIER_CONFIG[tier]
        grp  = query("""
            SELECT * FROM active_groups WHERE product_id=? AND status='open'
            ORDER BY created_at DESC LIMIT 1
        """, (product_id,), one=True)

        if not grp:
            expires = datetime.utcnow() + timedelta(hours=cfg["max_wait_hrs"] or 12)
           
            if buyer_lat and buyer_lng:
                distance_km = haversine_km(prod["farm_lat"], prod["farm_lng"], buyer_lat, buyer_lng)
            est_cost = calc_delivery_cost(distance_km or 10)
            grp_id = execute("""
                INSERT INTO active_groups(product_id, delivery_zone, threshold, joined,
                                          total_cost, expires_at, status)
                VALUES(?, ?, ?, 1, ?, ?, 'open')
            """, (product_id, "Vadodara", cfg["threshold"], est_cost,
                  expires.strftime("%Y-%m-%d %H:%M:%S")))
            group_id = grp_id
        else:
            group_id  = grp["id"]
            new_joined = grp["joined"] + 1
           
            delivery_cost = round(grp["total_cost"] / new_joined, 2)
            execute("UPDATE active_groups SET joined=? WHERE id=?", (new_joined, group_id))
            
            if new_joined >= grp["threshold"]:
                drv = query("SELECT * FROM drivers WHERE is_available=1 ORDER BY RANDOM() LIMIT 1", one=True)
                if drv:
                    driver_id = drv["id"]
                execute("UPDATE active_groups SET status='full' WHERE id=?", (group_id,))

    order_id = execute("""
        INSERT INTO orders(buyer_id, producer_id, product_id, driver_id, group_id,
                            delivery_type, quantity, total_price, delivery_cost,
                            distance_km, status, pickup_id)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
    """, (buyer_id, prod["farm_id"], product_id, driver_id, group_id,
          delivery_type, quantity, total_price, delivery_cost,
          round(distance_km, 2), "confirmed", pickup_id))

   
    execute("UPDATE products SET stock = stock - ? WHERE id=?", (quantity, product_id))

   
    if delivery_type != "self":
        now = datetime.utcnow()
        exp = (now + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
        for otp_type in ("pickup", "delivery"):
            execute("""
                INSERT INTO verification_otps(order_id, otp_type, otp_code, expires_at)
                VALUES(?,?,?,?)
            """, (order_id, otp_type, gen_otp(), exp))

    order = query("SELECT * FROM orders WHERE id=?", (order_id,), one=True)
    return ok(row_to_dict(order), "Order created successfully", 201)


@app.get("/api/orders/<int:order_id>")
def get_order(order_id):
    order = query("""
        SELECT o.*, b.name as buyer_name, b.phone as buyer_phone,
               pr.name as producer_name, pr.address as farm_address,
               pr.gps_lat as farm_lat, pr.gps_lng as farm_lng,
               d.name as driver_name, d.phone as driver_phone,
               d.vehicle_num, d.vehicle_type, d.rating as driver_rating,
               d.gps_lat as driver_lat, d.gps_lng as driver_lng,
               p.name as product_name
        FROM orders o
        JOIN buyers b   ON o.buyer_id    = b.id
        JOIN producers pr ON o.producer_id = pr.id
        LEFT JOIN drivers d ON o.driver_id  = d.id
        JOIN products p ON o.product_id  = p.id
        WHERE o.id = ?
    """, (order_id,), one=True)
    if not order: return err("Order not found", 404)
    return ok(row_to_dict(order))


@app.get("/api/orders")
def list_orders():
    buyer_id = request.args.get("buyer_id")
    if buyer_id:
        rows = query("SELECT * FROM orders WHERE buyer_id=? ORDER BY created_at DESC", (buyer_id,))
    else:
        rows = query("SELECT * FROM orders ORDER BY created_at DESC LIMIT 50")
    return ok([row_to_dict(r) for r in rows])



@app.get("/api/orders/<int:order_id>/otps")
def get_otps(order_id):
    """Return OTPs for an order (dev/demo endpoint — restrict in production)."""
    rows = query("SELECT * FROM verification_otps WHERE order_id=?", (order_id,))
    return ok([row_to_dict(r) for r in rows])


@app.post("/api/orders/<int:order_id>/verify-otp")
def verify_otp(order_id):
    data     = request.json or {}
    otp_type = data.get("otp_type")   
    otp_code = data.get("otp_code")

    if not otp_type or not otp_code:
        return err("otp_type and otp_code required")

    record = query("""
        SELECT * FROM verification_otps
        WHERE order_id=? AND otp_type=? AND is_used=0
        ORDER BY created_at DESC LIMIT 1
    """, (order_id, otp_type), one=True)

    if not record: return err("OTP not found or already used", 404)
    if record["otp_code"] != otp_code: return err("Invalid OTP", 401)
    if datetime.strptime(record["expires_at"], "%Y-%m-%d %H:%M:%S") < datetime.utcnow():
        return err("OTP expired", 410)

    execute("UPDATE verification_otps SET is_used=1 WHERE id=?", (record["id"],))

    new_status = "in_transit" if otp_type == "pickup" else "delivered"
    execute("UPDATE orders SET status=? WHERE id=?", (new_status, order_id))
    if new_status == "delivered":
        execute("UPDATE orders SET delivered_at=? WHERE id=?",
                (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"), order_id))

    return ok({"verified": True, "order_status": new_status})


@app.post("/api/orders/<int:order_id>/proof")
def upload_proof(order_id):
    data     = request.json or {}
    driver_id = data.get("driver_id")
    photo_url = data.get("photo_url")
    notes     = data.get("notes", "")

    if not driver_id or not photo_url:
        return err("driver_id and photo_url required")

    proof_id = execute("""
        INSERT INTO condition_proofs(order_id, driver_id, photo_url, notes)
        VALUES(?,?,?,?)
    """, (order_id, driver_id, photo_url, notes))

    execute("UPDATE orders SET status='pickup_otp_sent' WHERE id=?", (order_id,))
    return ok({"proof_id": proof_id}, "Proof uploaded", 201)



@app.get("/api/groups")
def list_groups():
    rows = query("""
        SELECT ag.*, p.name as product_name, p.perishability
        FROM active_groups ag
        JOIN products p ON ag.product_id = p.id
        WHERE ag.status = 'open'
        ORDER BY ag.created_at DESC
    """)
    return ok([row_to_dict(r) for r in rows])


@app.get("/api/groups/<int:group_id>")
def get_group(group_id):
    row = query("""
        SELECT ag.*, p.name as product_name, p.perishability,
               pr.name as producer_name
        FROM active_groups ag
        JOIN products p  ON ag.product_id   = p.id
        JOIN producers pr ON p.producer_id  = pr.id
        WHERE ag.id = ?
    """, (group_id,), one=True)
    if not row: return err("Group not found", 404)
    grp = row_to_dict(row)
    grp["progress_pct"] = min(100, int((grp["joined"] / grp["threshold"]) * 100))
    grp["cost_per_person"] = round(grp["total_cost"] / max(grp["joined"], 1), 2)
    return ok(grp)



@app.get("/api/backhaul/drivers")
def returning_drivers():
    """List drivers returning from city to village today."""
    today = datetime.utcnow().date().isoformat()
    rows  = query("""
        SELECT DISTINCT d.id, d.name, d.phone, d.vehicle_type, d.vehicle_num,
               d.rating, d.gps_lat, d.gps_lng
        FROM drivers d
        WHERE d.is_available = 1
    """)
    return ok([row_to_dict(r) for r in rows])


@app.post("/api/backhaul")
def book_backhaul():
    data = request.json or {}
    required = ["driver_id", "requester_id", "item_desc",
                "origin_city", "destination", "scheduled_date"]
    if not all(k in data for k in required):
        return err(f"Required: {required}")

   
    weight      = float(data.get("weight_kg", 10))
    base_cost   = calc_delivery_cost(15, "auto")   
    discount    = data.get("discount_pct", 40)
    final_cost  = round(base_cost * (1 - discount / 100), 2)

    bid = execute("""
        INSERT INTO backhaul_bookings(driver_id, requester_id, item_desc, origin_city,
                                       destination, weight_kg, original_cost, discount_pct,
                                       final_cost, scheduled_date)
        VALUES(?,?,?,?,?,?,?,?,?,?)
    """, (data["driver_id"], data["requester_id"], data["item_desc"],
          data["origin_city"], data["destination"], weight,
          base_cost, discount, final_cost, data["scheduled_date"]))

    return ok({
        "booking_id": bid,
        "original_cost": base_cost,
        "discount_pct": discount,
        "final_cost": final_cost,
    }, "Back-haul booking confirmed", 201)


@app.get("/api/backhaul")
def list_backhaul():
    requester_id = request.args.get("requester_id")
    if requester_id:
        rows = query("SELECT * FROM backhaul_bookings WHERE requester_id=?", (requester_id,))
    else:
        rows = query("SELECT * FROM backhaul_bookings ORDER BY created_at DESC LIMIT 30")
    return ok([row_to_dict(r) for r in rows])


@app.get("/api/drivers")
def list_drivers():
    rows = query("SELECT * FROM drivers")
    return ok([row_to_dict(r) for r in rows])


@app.put("/api/drivers/<int:driver_id>/location")
def update_driver_location(driver_id):
    data = request.json or {}
    lat, lng = data.get("lat"), data.get("lng")
    if not lat or not lng: return err("lat and lng required")
    execute("UPDATE drivers SET gps_lat=?, gps_lng=? WHERE id=?", (lat, lng, driver_id))
    return ok({"driver_id": driver_id, "lat": lat, "lng": lng})

@app.get("/api/stats")
def dashboard_stats():
    total_orders    = query("SELECT COUNT(*) as c FROM orders", one=True)["c"]
    delivered       = query("SELECT COUNT(*) as c FROM orders WHERE status='delivered'", one=True)["c"]
    active_groups   = query("SELECT COUNT(*) as c FROM active_groups WHERE status='open'", one=True)["c"]
    active_drivers  = query("SELECT COUNT(*) as c FROM drivers WHERE is_available=1", one=True)["c"]
    backhaul_count  = query("SELECT COUNT(*) as c FROM backhaul_bookings", one=True)["c"]
    revenue         = query("SELECT SUM(total_price) as s FROM orders WHERE status='delivered'", one=True)["s"] or 0

    return ok({
        "total_orders": total_orders,
        "delivered_orders": delivered,
        "active_groups": active_groups,
        "active_drivers": active_drivers,
        "backhaul_bookings": backhaul_count,
        "total_revenue": round(revenue, 2),
    })







# ==================== DB INITIALIZATION ====================

def init_db():
    with app.app_context():
        db.create_all()
        print("Database initialized. Ready for fresh users!")


# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    else:
       
        with app.app_context():
            db = get_db()
            with open("schema.sql") as f:
                db.executescript(f.read())
            db.commit()
            _seed_demo_data(db)
    app.run(debug=True, host='0.0.0.0', port=5000)
