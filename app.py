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

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config) # Load the settings

mail = Mail(app)
# Initialize the serializer using your Secret Key
s = URLSafeTimedSerializer(app.config['SECRET_KEY'])

client = Groq(api_key="Enter_Groq_API_KEY")

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
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)