from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from sqlalchemy import or_, func, and_
import pymysql
import re
from werkzeug.utils import secure_filename
import os
import json
import random
import uuid
import datetime
import time
pymysql.install_as_MySQLdb()

app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:root@localhost:3306/ecommerce'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# --- Helper Functions ---
def usd_to_inr(amount):
    """No longer converts USD to INR as all prices are directly in INR now"""
    # Just return the amount as-is since it's already in INR
    return float(amount)

# Register template filter
@app.template_filter('to_inr')
def to_inr_filter(amount):
    """Display INR amount (no conversion needed)"""
    return usd_to_inr(amount)

# --- Login Required Decorator ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this feature.', 'error')
            # Store the requested URL in session
            session['next_url'] = request.url
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Role Required Decorator ---
def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                flash('Please log in first.', 'error')
                return redirect(url_for('login'))
            if session['role'] not in roles:
                flash('Unauthorized access.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Models ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'user', 'seller', 'admin'

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    image = db.Column(db.String(255))
    category = db.Column(db.String(50))
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller = db.relationship('User', backref='products')
    view_count = db.Column(db.Integer, default=0)  # Added view_count column
    cart_count = db.Column(db.Integer, default=0)  # Added cart_count column
    
    def to_dict(self):
        """Convert product object to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'price': self.price,  # Price is already in INR
            'image': self.image,
            'category': self.category,
            'url': f'/product/{self.id}',
            'view_count': self.view_count,
            'cart_count': self.cart_count
        }

class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    product = db.relationship('Product')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())
    read = db.Column(db.Boolean, default=False)  # Whether the message has been read
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_date = db.Column(db.DateTime, server_default=db.func.now())
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')  # Pending, Paid, Delivered, Cancelled
    order_number = db.Column(db.String(20), unique=True)
    
    user = db.relationship('User', backref='orders')
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')
    
    def __init__(self, user_id, total_amount):
        self.user_id = user_id
        self.total_amount = total_amount
        # Generate a unique order number
        self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)  # Store price at time of purchase
    
    product = db.relationship('Product')

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    transaction_date = db.Column(db.DateTime, server_default=db.func.now())
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)
    transaction_id = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(20), default='Completed')  # Completed, Failed, Refunded
    
    order = db.relationship('Order', backref='transactions')

@app.route('/')
def home():
    # Get featured products (top 4 products by view count)
    featured_products = Product.query.order_by(Product.view_count.desc()).limit(4).all()
    
    return render_template('home.html', featured_products=featured_products)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        role = request.form['role']
        password = generate_password_hash(request.form['password'])
        if User.query.filter_by(email=email).first():
            flash('Email already exists!', 'error')
            return render_template('register.html')
        new_user = User(username=username, email=email, password=password, role=role)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username
            flash(f'Welcome back, {user.username}!', 'success')
            # Redirect to stored URL or dashboard
            next_url = session.pop('next_url', None)
            return redirect(next_url or url_for('dashboard'))
        flash('Invalid credentials!', 'error')
        return render_template('login.html')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))

# --- Dashboard ---
@app.route('/dashboard')
@login_required
def dashboard():
    user = User.query.get(session['user_id'])
    
    # Count unread messages for the current user
    unread_message_count = Message.query.filter_by(
        receiver_id=user.id,
        read=False
    ).count()
    
    if user.role == 'seller':
        products = Product.query.filter_by(seller_id=user.id).all()
        return render_template('dashboard.html', user=user, products=products, 
                              unread_message_count=unread_message_count)
    elif user.role == 'user':
        cart_items = CartItem.query.filter_by(user_id=user.id).all()
        # Get popular products based on view count
        popular_products = Product.query.order_by(Product.view_count.desc()).limit(3).all()
        # Get trending products based on cart count
        trending_products = Product.query.order_by(Product.cart_count.desc()).limit(3).all()
        
        return render_template('dashboard.html', user=user, cart_items=cart_items, 
                              popular_products=popular_products,
                              trending_products=trending_products,
                              unread_message_count=unread_message_count)
    else:  # admin
        users = User.query.all()
        products = Product.query.all()
        return render_template('dashboard.html', user=user, users=users, products=products, 
                              unread_message_count=unread_message_count)

# --- Product Management (Seller & Admin) ---
@app.route('/add_product', methods=['GET', 'POST'])
@login_required
@role_required('seller', 'admin')
def add_product():
    # Define product categories
    categories = [
        'Phone', 'Laptop', 'Tablet', 'Headphone', 'Earbuds', 
        'Camera', 'Watch', 'TV', 'Home Appliance', 'Gaming', 
        'Fashion', 'Beauty', 'Books', 'Sports', 'Other'
    ]
    
    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = float(request.form['price'])
        category = request.form['category']
        image_file = request.files.get('image')
        image_filename = None
        if image_file and image_file.filename:
            import os
            upload_folder = os.path.join('static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            image_filename = image_file.filename
            image_path = os.path.join(upload_folder, image_filename)
            image_file.save(image_path)
        new_product = Product(
            name=name, 
            description=description, 
            price=price, 
            seller_id=session['user_id'], 
            image=image_filename,
            category=category
        )
        db.session.add(new_product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_product.html', categories=categories)

@app.route('/edit_product/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    if 'user_id' not in session or session.get('role') != 'seller':
        return redirect('/login')
    product = Product.query.get_or_404(product_id)
    if product.seller_id != session['user_id']:
        return 'Unauthorized', 403
    
    # Define product categories
    categories = [
        'Phone', 'Laptop', 'Tablet', 'Headphone', 'Earbuds', 
        'Camera', 'Watch', 'TV', 'Home Appliance', 'Gaming', 
        'Fashion', 'Beauty', 'Books', 'Sports', 'Other'
    ]
    
    if request.method == 'POST':
        product.name = request.form['name']
        product.description = request.form['description']
        product.price = float(request.form['price'])
        product.category = request.form['category']
        image_file = request.files.get('image')
        if image_file and image_file.filename:
            import os
            upload_folder = os.path.join('static', 'uploads')
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            image_filename = image_file.filename
            image_path = os.path.join(upload_folder, image_filename)
            image_file.save(image_path)
            product.image = image_filename
        db.session.commit()
        return redirect('/dashboard')
    return render_template('edit_product.html', product=product, categories=categories)

@app.route('/delete_product/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    if 'user_id' not in session or session.get('role') != 'seller':
        return redirect('/login')
    product = Product.query.get_or_404(product_id)
    if product.seller_id != session['user_id']:
        return 'Unauthorized', 403
    db.session.delete(product)
    db.session.commit()
    return redirect('/dashboard')

# --- Product Browsing (Public) ---
@app.route('/products')
def products():
    # Get search query and category filter from query parameters
    search_query = request.args.get('search', '')
    category = request.args.get('category', '')
    min_price = request.args.get('min_price', '')
    max_price = request.args.get('max_price', '')
    sort_by = request.args.get('sort_by', 'popularity')  # Default to popularity (view_count)
    
    # Define all available categories
    categories = [
        'Phone', 'Laptop', 'Tablet', 'Headphone', 'Earbuds', 
        'Camera', 'Watch', 'TV', 'Home Appliance', 'Gaming', 
        'Fashion', 'Beauty', 'Books', 'Sports', 'Other'
    ]
    
    # Start with base query
    query = Product.query
    
    # Apply search if provided
    if search_query:
        query = query.filter(
            or_(
                Product.name.ilike(f'%{search_query}%'),
                Product.description.ilike(f'%{search_query}%'),
                Product.category.ilike(f'%{search_query}%')
            )
        )
    
    # Apply category filter if provided
    if category and category != 'All':
        query = query.filter(Product.category == category)
    
    # Apply price range filters if provided
    if min_price and min_price.isdigit():
        query = query.filter(Product.price >= float(min_price))
    
    if max_price and max_price.isdigit():
        query = query.filter(Product.price <= float(max_price))
    
    # Apply sorting
    if sort_by == 'price_low_high':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high_low':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'newest':
        query = query.order_by(Product.id.desc())  # Assuming newer products have higher IDs
    elif sort_by == 'rating':
        # For simplicity, we'll sort by ID since we don't have ratings
        # In a real app, you would sort by an actual rating field
        query = query.order_by(Product.id.asc())
    elif sort_by == 'trending':
        # Sort by cart_count (trending products)
        query = query.order_by(Product.cart_count.desc())
    else:  # Default 'popularity' sorting - by view_count
        query = query.order_by(Product.view_count.desc())
    
    # Get results
    products = query.all()
    
    return render_template('products.html', 
                         products=products, 
                         categories=categories,
                         selected_category=category,
                         search_query=search_query,
                         min_price=min_price,
                         max_price=max_price,
                         sort_by=sort_by,
                         user_role=session.get('role'),
                         is_logged_in='user_id' in session)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    
    # Get similar products from the same category, excluding current product
    if product.category:
        similar_products = Product.query.filter(
            Product.category == product.category,
            Product.id != product.id
        ).limit(4).all()
    else:
        # If no category, get random products
        similar_products = Product.query.filter(Product.id != product.id).order_by(func.random()).limit(4).all()
    
    # Get seller information
    seller = User.query.get(product.seller_id)
    
    return render_template('product_detail.html', 
                         product=product, 
                         similar_products=similar_products,
                         user_role=session.get('role'),
                         is_logged_in='user_id' in session,
                         seller=seller)

# --- Cart Management (User) ---
@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
@login_required
@role_required('user')
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))
    
    # Get the product and increment its cart counter
    product = Product.query.get_or_404(product_id)
    product.cart_count += 1
    db.session.commit()
    
    cart_item = CartItem.query.filter_by(user_id=session['user_id'], product_id=product_id).first()
    if cart_item:
        cart_item.quantity += quantity
        flash('Cart updated successfully!', 'success')
    else:
        cart_item = CartItem(user_id=session['user_id'], product_id=product_id, quantity=quantity)
        db.session.add(cart_item)
        flash('Item added to cart!', 'success')
    db.session.commit()
    return redirect(url_for('cart'))

@app.route('/cart')
@login_required
@role_required('user')
def cart():
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

@app.route('/remove_from_cart/<int:cart_item_id>', methods=['POST'])
def remove_from_cart(cart_item_id):
    if 'user_id' not in session or session.get('role') != 'user':
        return redirect('/login')
    cart_item = CartItem.query.get_or_404(cart_item_id)
    if cart_item.user_id != session['user_id']:
        return 'Unauthorized', 403
    db.session.delete(cart_item)
    db.session.commit()
    return redirect('/cart')

@app.route('/checkout', methods=['GET'])
@login_required
@role_required('user')
def checkout():
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    if not cart_items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('cart'))
    
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    user = User.query.get(session['user_id'])
    
    return render_template('checkout.html', cart_items=cart_items, total_price=total_price, user=user)

@app.route('/payment', methods=['POST'])
@login_required
@role_required('user')
def payment():
    # Get cart items to create an order
    cart_items = CartItem.query.filter_by(user_id=session['user_id']).all()
    if not cart_items:
        flash('Your cart is empty.', 'error')
        return redirect(url_for('cart'))
    
    # Calculate total
    total_amount = sum(item.product.price * item.quantity for item in cart_items)
    
    # Get payment details from form
    payment_method = request.form.get('payment_method', 'Credit Card')
    
    # Create the order
    order = Order(user_id=session['user_id'], total_amount=total_amount)
    db.session.add(order)
    # Commit the order to get its ID
    db.session.commit()
    
    # Add order items
    for cart_item in cart_items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=cart_item.product_id,
            quantity=cart_item.quantity,
            price=cart_item.product.price
        )
        db.session.add(order_item)
    
    # Create a transaction record
    transaction = Transaction(
        order_id=order.id,
        amount=total_amount,
        payment_method=payment_method,
        transaction_id=f"TXN-{uuid.uuid4().hex[:10].upper()}"
    )
    db.session.add(transaction)
    
    # Clear the cart
    for cart_item in cart_items:
        db.session.delete(cart_item)
    
    # Mark the order as paid
    order.status = 'Paid'
    
    # Commit all remaining changes
    db.session.commit()
    
    return redirect(url_for('order_confirmation', order_id=order.id))

@app.route('/order/confirmation/<int:order_id>')
@login_required
def order_confirmation(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Check if the order belongs to the current user
    if order.user_id != session['user_id'] and session.get('role') != 'admin':
        flash('Unauthorized access', 'error')
        return redirect(url_for('dashboard'))
    
    # Get the transaction
    transaction = Transaction.query.filter_by(order_id=order.id).first()
    
    return render_template('order_confirmation.html', order=order, transaction=transaction)

# --- Order History Pages ---
@app.route('/order_history')
@login_required
def order_history():
    user = User.query.get(session['user_id'])
    
    if user.role == 'user':
        # For users: Show orders they've placed
        orders = Order.query.filter_by(user_id=user.id).order_by(Order.order_date.desc()).all()
        return render_template('order_history.html', orders=orders, user=user)
    
    elif user.role == 'seller':
        # For sellers: Show orders containing their products
        # First, get all products by this seller
        seller_products = Product.query.filter_by(seller_id=user.id).all()
        seller_product_ids = [product.id for product in seller_products]
        
        # Then find order items containing these products
        order_items = OrderItem.query.filter(OrderItem.product_id.in_(seller_product_ids)).all()
        
        # Get the unique orders
        order_ids = set(item.order_id for item in order_items)
        orders = Order.query.filter(Order.id.in_(order_ids)).order_by(Order.order_date.desc()).all()
        
        return render_template('seller_order_history.html', orders=orders, order_items=order_items, user=user)
    
    else:  # admin
        # For admin: Show all orders
        orders = Order.query.order_by(Order.order_date.desc()).all()
        return render_template('order_history.html', orders=orders, user=user)

@app.route('/order_detail/<int:order_id>')
@login_required
def order_detail(order_id):
    order = Order.query.get_or_404(order_id)
    user = User.query.get(session['user_id'])
    
    # For users: Check if the order belongs to them
    if user.role == 'user' and order.user_id != user.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('order_history'))
    
    # For sellers: Check if any products in the order belong to them
    elif user.role == 'seller':
        seller_products = Product.query.filter_by(seller_id=user.id).all()
        seller_product_ids = [product.id for product in seller_products]
        
        # Check if any order items contain seller's products
        seller_items = [item for item in order.items if item.product_id in seller_product_ids]
        
        if not seller_items:
            flash('Unauthorized access', 'error')
            return redirect(url_for('order_history'))
    
    # Get the transaction
    transaction = Transaction.query.filter_by(order_id=order.id).first()
    
    return render_template('order_detail.html', order=order, transaction=transaction, user=user)

@app.route('/update_order_status/<int:order_id>', methods=['POST'])
@login_required
@role_required('seller', 'admin')
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    
    if new_status in ['Pending', 'Paid', 'Shipped', 'Delivered', 'Cancelled']:
        order.status = new_status
        db.session.commit()
        flash('Order status updated successfully!', 'success')
    else:
        flash('Invalid status value', 'error')
    
    return redirect(url_for('order_detail', order_id=order.id))

# --- Chat System (User & Seller) ---
@app.route('/chat/<int:other_user_id>', methods=['GET', 'POST'])
def chat(other_user_id):
    if 'user_id' not in session:
        return redirect('/login')
    user_id = session['user_id']
    user = User.query.get(user_id)
    other_user = User.query.get_or_404(other_user_id)
    if request.method == 'POST':
        content = request.form['content']
        message = Message(sender_id=user_id, receiver_id=other_user_id, content=content)
        db.session.add(message)
        db.session.commit()
    
    # Mark all messages from the other user as read
    unread_messages = Message.query.filter_by(sender_id=other_user_id, receiver_id=user_id, read=False).all()
    for message in unread_messages:
        message.read = True
    db.session.commit()
    
    # Count total unread messages for the navbar
    unread_message_count = Message.query.filter_by(
        receiver_id=user_id,
        read=False
    ).count()
    
    messages = Message.query.filter(
        ((Message.sender_id == user_id) & (Message.receiver_id == other_user_id)) |
        ((Message.sender_id == other_user_id) & (Message.receiver_id == user_id))
    ).order_by(Message.timestamp).all()
    
    return render_template('chat.html', messages=messages, other_user=other_user, user=user, 
                          unread_message_count=unread_message_count)

# --- List Users for Chat (for buyers and sellers) ---
@app.route('/users_for_chat')
def users_for_chat():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    # Get all users that the current user has had a conversation with
    chat_partners = db.session.query(User).join(
        Message, 
        or_(
            and_(Message.sender_id == user_id, Message.receiver_id == User.id),
            and_(Message.receiver_id == user_id, Message.sender_id == User.id)
        )
    ).distinct().all()
    
    # If there are no chat partners but the user wants to see available users
    if not chat_partners:
        if user.role == 'user':
            # Buyers can chat with sellers
            chat_partners = User.query.filter_by(role='seller').all()
        elif user.role == 'seller':
            # Sellers can chat with buyers
            chat_partners = User.query.filter_by(role='user').all()
    
    # Get unread message counts for each user
    unread_counts = {}
    for partner in chat_partners:
        unread_count = Message.query.filter_by(
            sender_id=partner.id, 
            receiver_id=user_id,
            read=False
        ).count()
        unread_counts[partner.id] = unread_count
    
    return render_template('users_for_chat.html', users=chat_partners, unread_counts=unread_counts)

# --- Chatbot System ---
@app.route('/api/compare_products', methods=['GET'])
def compare_products():
    product1_id = request.args.get('product1_id', '')
    product2_id = request.args.get('product2_id', '')
    
    if not product1_id or not product2_id:
        return jsonify({'error': 'Both product IDs are required'})
    
    # Get both products
    product1 = Product.query.get(product1_id)
    product2 = Product.query.get(product2_id)
    
    if not product1 or not product2:
        return jsonify({'error': 'One or both products not found'})
    
    # Convert to dictionaries
    product1_dict = product1.to_dict()
    product2_dict = product2.to_dict()
    
    return jsonify({
        'product1': product1_dict,
        'product2': product2_dict
    })

@app.route('/chatbot_query', methods=['POST'])
def chatbot_query():
    data = request.get_json()
    user_message = data.get('query', '')
    context = data.get('context', [])
    
    print(f"DEBUG: Received user message: '{user_message}'")
    
    # Initialize response
    response = {
        'answer': '',
        'suggested_products': []
    }
    
    # Extract category from context if present
    category_context = None
    for ctx in context:
        if isinstance(ctx, dict) and ctx.get('type') == 'category':
            category_context = ctx.get('value')
            break
    
    # Handle ALL sorting patterns upfront, regardless of category or format
    # This is the most reliable approach since we're checking for any sorting-related patterns first
    
    # Check for low to high sorting patterns
    if any(pattern in user_message.lower() for pattern in ['low to high', 'price low']):
        query = Product.query
        
        # Apply category filter if we have one from context
        if category_context:
            query = query.filter(Product.category == category_context)
            category_name = category_context.lower() + 's' if not category_context.lower().endswith('s') else category_context.lower()
            response['answer'] = f"Here are {category_name} sorted by price (low to high):"
        else:
            response['answer'] = "Here are products sorted by price (low to high):"
            
        # Apply the sorting
        products = query.order_by(Product.price.asc()).limit(5).all()
        response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    # Check for high to low sorting patterns
    if any(pattern in user_message.lower() for pattern in ['high to low', 'price high']):
        query = Product.query
        
        # Apply category filter if we have one from context
        if category_context:
            query = query.filter(Product.category == category_context)
            category_name = category_context.lower() + 's' if not category_context.lower().endswith('s') else category_context.lower()
            response['answer'] = f"Here are {category_name} sorted by price (high to low):"
        else:
            response['answer'] = "Here are products sorted by price (high to low):"
            
        # Apply the sorting
        products = query.order_by(Product.price.desc()).limit(5).all()
        response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    # Check if we have product context (from product detail page)
    product_context = None
    for ctx in context:
        if isinstance(ctx, dict) and ctx.get('type') == 'product':
            product_context = ctx
            break
    
    # If this is a product-specific query, add some specialized responses
    if product_context:
        product_id = product_context.get('id')
        product_name = product_context.get('name')
        product_category = product_context.get('category')
        
        # Handle questions about the current product
        if re.search(r'(features|specs|details|about)\s+(this|the|current)\s+product', user_message.lower()):
            product = Product.query.get(product_id)
            if product:
                response['answer'] = f"Here are the details about {product.name}:\n"
                response['answer'] += f"Category: {product.category}\n"
                response['answer'] += f"Price: ₹{product.price:.2f}\n"
                response['answer'] += f"Description: {product.description}"
                return jsonify(response)
        
        # Handle questions about similar products
        if re.search(r'(similar|alternatives|like this|related)', user_message.lower()):
            if product_category:
                similar_products = Product.query.filter(
                    Product.category == product_category,
                    Product.id != product_id
                ).limit(4).all()
                
                if similar_products:
                    response['answer'] = f"Here are some similar products in the {product_category} category:"
                    response['suggested_products'] = [p.to_dict() for p in similar_products]
                    return jsonify(response)
                else:
                    # If no similar products found, show some random products
                    response['answer'] = f"I couldn't find other products in the {product_category} category. Here are some popular products you might like:"
                    random_products = Product.query.order_by(func.random()).limit(3).all()
                    response['suggested_products'] = [p.to_dict() for p in random_products]
                    return jsonify(response)
        
        # Handle questions about price comparison
        if re.search(r'(cheaper|expensive|cost less|better price|compare price)', user_message.lower()):
            product = Product.query.get(product_id)
            if product:
                cheaper_products = Product.query.filter(
                    Product.category == product_category,
                    Product.price < product.price,
                    Product.id != product_id
                ).order_by(Product.price.desc()).limit(3).all()
                
                more_expensive_products = Product.query.filter(
                    Product.category == product_category,
                    Product.price > product.price,
                    Product.id != product_id
                ).order_by(Product.price.asc()).limit(3).all()
                
                if cheaper_products or more_expensive_products:
                    response['answer'] = f"Here's a price comparison with other {product_category} products:"
                    all_comparable = []
                    
                    if cheaper_products:
                        response['answer'] += f"\n\nCheaper alternatives to {product_name}:"
                        all_comparable.extend(cheaper_products)
                    
                    if more_expensive_products:
                        response['answer'] += f"\n\nMore premium options than {product_name}:"
                        all_comparable.extend(more_expensive_products)
                    
                    response['suggested_products'] = [p.to_dict() for p in all_comparable]
                    return jsonify(response)
                else:
                    # If no price comparisons found, show some random products
                    response['answer'] = f"I couldn't find products to compare with {product_name}. Here are some other products you might be interested in:"
                    random_products = Product.query.filter(Product.id != product_id).order_by(func.random()).limit(3).all()
                    response['suggested_products'] = [p.to_dict() for p in random_products]
                    return jsonify(response)
        
        # For category-specific queries, prioritize the current product's category
        for category_pattern in [r'show me (\w+)s', r'(\w+)s? low to high', r'(\w+)s? high to low', r'newest (\w+)s?']:
            category_match = re.search(category_pattern, user_message.lower())
            if category_match:
                category = category_match.group(1).lower()
                # If asking about the current product's category or a generic term
                if category in ['product', 'item'] and product_category:
                    # Replace generic terms with the actual product category
                    modified_message = user_message.lower().replace(category, product_category.lower())
                    # Process the modified message - but don't call the function directly to avoid recursion
                    # Instead handle this case right here
                    modified_category = product_category
                    
                    # Check which pattern matched and handle accordingly
                    if 'low to high' in modified_message:
                        products = Product.query.filter(
                            Product.category == modified_category
                        ).order_by(Product.price.asc()).limit(5).all()
                        
                        if products:
                            response['answer'] = f"Here are {modified_category}s sorted by price (low to high):"
                            response['suggested_products'] = [p.to_dict() for p in products]
                        else:
                            response['answer'] = f"I couldn't find any products in the {modified_category} category. Here are some popular products instead:"
                            random_products = Product.query.order_by(func.random()).limit(3).all()
                            response['suggested_products'] = [p.to_dict() for p in random_products]
                        return jsonify(response)
                        
                    elif 'high to low' in modified_message:
                        products = Product.query.filter(
                            Product.category == modified_category
                        ).order_by(Product.price.desc()).limit(5).all()
                        
                        if products:
                            response['answer'] = f"Here are {modified_category}s sorted by price (high to low):"
                            response['suggested_products'] = [p.to_dict() for p in products]
                        else:
                            response['answer'] = f"I couldn't find any products in the {modified_category} category. Here are some popular products instead:"
                            random_products = Product.query.order_by(func.random()).limit(3).all()
                            response['suggested_products'] = [p.to_dict() for p in random_products]
                        return jsonify(response)
                        
                    elif 'show me' in modified_message:
                        products = Product.query.filter(
                            Product.category == modified_category
                        ).limit(5).all()
                        
                        if products:
                            response['answer'] = f"Here are some {modified_category}s I found for you:"
                            response['suggested_products'] = [p.to_dict() for p in products]
                        else:
                            response['answer'] = f"I couldn't find any products in the {modified_category} category. Here are some popular products instead:"
                            random_products = Product.query.order_by(func.random()).limit(3).all()
                            response['suggested_products'] = [p.to_dict() for p in random_products]
                        return jsonify(response)
    
    # Add more comprehensive pattern matching for sorting
    sort_patterns = [
        # Direct sorting commands
        (r'^low to high$', 'asc', None),
        (r'^high to low$', 'desc', None),
        (r'^price low to high$', 'asc', None),
        (r'^price high to low$', 'desc', None),
        (r'^products low to high$', 'asc', None),
        (r'^products high to low$', 'desc', None),
        (r'^sort by price low to high$', 'asc', None),
        (r'^sort by price high to low$', 'desc', None),
        (r'^sort by price \(low to high\)$', 'asc', None),
        (r'^sort by price \(high to low\)$', 'desc', None),
        
        # Category specific sorting
        (r'(\w+)s?\s+low\s+to\s+high', 'asc', 1),
        (r'(\w+)s?\s+high\s+to\s+low', 'desc', 1),
        (r'sort\s+(\w+)s?\s+by\s+price\s+low', 'asc', 1),
        (r'sort\s+(\w+)s?\s+by\s+price\s+high', 'desc', 1),
        
        # Additional patterns
        (r'sort\s+by\s+price\s+low\s+to\s+high\s+(\w+)', 'asc', 1),
        (r'sort\s+by\s+price\s+high\s+to\s+low\s+(\w+)', 'desc', 1),
    ]
    
    # Search patterns for direct category queries
    category_patterns = [
        (r'show me (\w+)s?', 1),
        (r'find (\w+)s?', 1),
        (r'search for (\w+)s?', 1),
        (r'looking for (\w+)s?', 1),
        (r'get (\w+)s?', 1),
        (r'(\w+)s?\s+products', 1),
    ]
    
    # Check sort patterns FIRST (before category patterns)
    for pattern, sort_order, category_group in sort_patterns:
        match = re.search(pattern, user_message.lower())
        if match:
            # If category group is None, it's a general sort
            if category_group is None:
                products = Product.query.order_by(
                    Product.price.asc() if sort_order == 'asc' else Product.price.desc()
                ).limit(5).all()
                
                if products:
                    sort_description = "low to high" if sort_order == 'asc' else "high to low"
                    response['answer'] = f"Here are products sorted by price ({sort_description}):"
                    response['suggested_products'] = [product.to_dict() for product in products]
                    return jsonify(response)
            else:
                # Extract category if it exists in the pattern
                category = match.group(category_group).capitalize()
                category_lower = category.lower()
                
                print(f"Sort pattern detected: '{pattern}' with category '{category_lower}'")
                
                # Try exact category match
                products = Product.query.filter(
                    or_(
                        func.lower(Product.category) == category_lower,
                        func.lower(Product.category) == f"{category_lower}s",
                        func.lower(Product.category).like(f"{category_lower}%")
                    )
                ).order_by(
                    Product.price.asc() if sort_order == 'asc' else Product.price.desc()
                ).limit(5).all()
                
                # Try substring match if no exact match
                if not products:
                    products = Product.query.filter(
                        func.lower(Product.category).like(f"%{category_lower}%")
                    ).order_by(
                        Product.price.asc() if sort_order == 'asc' else Product.price.desc()
                    ).limit(5).all()
                
                # Fallback to all products for generic terms
                if not products and category_lower in ["product", "item", "all"]:
                    products = Product.query.order_by(
                        Product.price.asc() if sort_order == 'asc' else Product.price.desc()
                    ).limit(5).all()
                
                # Special case handling for common categories with no products
                if not products and category_lower in ["phone", "phones", "mobile", "mobiles"]:
                    # Instead of always saying "I couldn't find any phones", let's check if we have phones
                    # First check if there's any price range mentioned in the message
                    phone_price_pattern = re.search(r'(\w+)s?\s+(under|above|between)\s+(\d+)(?:\s+and\s+(\d+))?', user_message.lower())
                    
                    if phone_price_pattern and phone_price_pattern.group(1).lower() in ["phone", "phones", "mobile", "mobiles"]:
                        # We have a price range mentioned, apply it
                        price_operator = phone_price_pattern.group(2).lower()
                        price1 = float(phone_price_pattern.group(3))
                        price2 = float(phone_price_pattern.group(4)) if phone_price_pattern.group(4) else None
                        
                        print(f"DEBUG: Found price pattern in category pattern: {price_operator} {price1} {price2}")
                        
                        # Query with price filter
                        query = Product.query.filter(
                            or_(
                                func.lower(Product.category) == "phone",
                                func.lower(Product.category) == "phones",
                                func.lower(Product.category).like("phone%"),
                                func.lower(Product.category).like("%phone%")
                            )
                        )
                        
                        # Apply price filter
                        if price_operator == 'under':
                            query = query.filter(Product.price < price1)
                            price_description = f"under ₹{price1:,.0f}"
                        elif price_operator == 'above':
                            query = query.filter(Product.price > price1)
                            price_description = f"above ₹{price1:,.0f}"
                        else:  # between
                            query = query.filter(Product.price >= price1, Product.price <= price2)
                            price_description = f"between ₹{price1:,.0f} and ₹{price2:,.0f}"
                        
                        # Get products with price filter
                        filtered_phones = query.order_by(Product.price.asc()).limit(5).all()
                        
                        print(f"DEBUG: Found {len(filtered_phones)} phones with price filter {price_description}")
                        
                        if filtered_phones:
                            response['answer'] = f"Here are phones {price_description}:"
                            response['suggested_products'] = [phone.to_dict() for phone in filtered_phones]
                        else:
                            response['answer'] = f"I couldn't find any phones {price_description}. Here are some popular products instead:"
                            products = Product.query.order_by(func.random()).limit(5).all()
                            response['suggested_products'] = [product.to_dict() for product in products]
                        
                        return jsonify(response)
                    
                    # No price filter, just show all phones
                    phones = Product.query.filter(
                        or_(
                            func.lower(Product.category) == "phone",
                            func.lower(Product.category) == "phones",
                            func.lower(Product.category).like("phone%"),
                            func.lower(Product.category).like("%phone%")
                        )
                    ).limit(5).all()
                    
                    if phones:
                        response['answer'] = f"Here are some phones I found for you:"
                        response['suggested_products'] = [product.to_dict() for product in phones]
                    else:
                        response['answer'] = "I couldn't find any phones in our inventory. Here are some other products that might interest you:"
                        products = Product.query.order_by(func.random()).limit(5).all()
                        response['suggested_products'] = [product.to_dict() for product in products]
                    return jsonify(response)
                
                if not products and category_lower in ["laptop", "laptops", "computer", "computers"]:
                    response['answer'] = "I couldn't find any laptops in our inventory. Here are some other products that might interest you:"
                    products = Product.query.order_by(func.random()).limit(5).all()
                    response['suggested_products'] = [product.to_dict() for product in products]
                    return jsonify(response)
                
                if products:
                    sort_description = "low to high" if sort_order == 'asc' else "high to low"
                    response['answer'] = f"Here are {category}s sorted by price ({sort_description}):"
                    response['suggested_products'] = [product.to_dict() for product in products]
                else:
                    response['answer'] = f"I couldn't find any products in the {category} category. Here are some popular products instead:"
                    random_products = Product.query.order_by(func.random()).limit(5).all()
                    response['suggested_products'] = [product.to_dict() for product in random_products]
                
                return jsonify(response)
    
    # THEN check category patterns (after checking sort patterns)
    for pattern, category_group in category_patterns:
        match = re.search(pattern, user_message.lower())
        if match:
            category = match.group(category_group).capitalize()
            category_lower = category.lower()
            
            print(f"Category search pattern detected: '{pattern}' with category '{category_lower}'")
            
            # Special handling for common categories with no products
            if category_lower in ["phone", "phones", "mobile", "mobiles"]:
                # Instead of always saying "I couldn't find any phones", let's check if we have phones
                # First check if there's any price range mentioned in the message
                phone_price_pattern = re.search(r'(\w+)s?\s+(under|above|between)\s+(\d+)(?:\s+and\s+(\d+))?', user_message.lower())
                
                if phone_price_pattern and phone_price_pattern.group(1).lower() in ["phone", "phones", "mobile", "mobiles"]:
                    # We have a price range mentioned, apply it
                    price_operator = phone_price_pattern.group(2).lower()
                    price1 = float(phone_price_pattern.group(3))
                    price2 = float(phone_price_pattern.group(4)) if phone_price_pattern.group(4) else None
                    
                    print(f"DEBUG: Found price pattern in category pattern: {price_operator} {price1} {price2}")
                    
                    # Query with price filter
                    query = Product.query.filter(
                        or_(
                            func.lower(Product.category) == "phone",
                            func.lower(Product.category) == "phones",
                            func.lower(Product.category).like("phone%"),
                            func.lower(Product.category).like("%phone%")
                        )
                    )
                    
                    # Apply price filter
                    if price_operator == 'under':
                        query = query.filter(Product.price < price1)
                        price_description = f"under ₹{price1:,.0f}"
                    elif price_operator == 'above':
                        query = query.filter(Product.price > price1)
                        price_description = f"above ₹{price1:,.0f}"
                    else:  # between
                        query = query.filter(Product.price >= price1, Product.price <= price2)
                        price_description = f"between ₹{price1:,.0f} and ₹{price2:,.0f}"
                    
                    # Get products with price filter
                    filtered_phones = query.order_by(Product.price.asc()).limit(5).all()
                    
                    print(f"DEBUG: Found {len(filtered_phones)} phones with price filter {price_description}")
                    
                    if filtered_phones:
                        response['answer'] = f"Here are phones {price_description}:"
                        response['suggested_products'] = [phone.to_dict() for phone in filtered_phones]
                    else:
                        response['answer'] = f"I couldn't find any phones {price_description}. Here are some popular products instead:"
                        products = Product.query.order_by(func.random()).limit(5).all()
                        response['suggested_products'] = [product.to_dict() for product in products]
                    
                    return jsonify(response)
                
                # No price filter, just show all phones
                phones = Product.query.filter(
                    or_(
                        func.lower(Product.category) == "phone",
                        func.lower(Product.category) == "phones",
                        func.lower(Product.category).like("phone%"),
                        func.lower(Product.category).like("%phone%")
                    )
                ).limit(5).all()
                
                if phones:
                    response['answer'] = f"Here are some phones I found for you:"
                    response['suggested_products'] = [product.to_dict() for product in phones]
                else:
                    response['answer'] = "I couldn't find any phones in our inventory. Here are some other products that might interest you:"
                    products = Product.query.order_by(func.random()).limit(5).all()
                    response['suggested_products'] = [product.to_dict() for product in products]
                return jsonify(response)
            
            if category_lower in ["laptop", "laptops", "computer", "computers"]:
                response['answer'] = "I couldn't find any laptops in our inventory. Here are some other products that might interest you:"
                products = Product.query.order_by(func.random()).limit(5).all()
                response['suggested_products'] = [product.to_dict() for product in products]
                return jsonify(response)
            
            # Try exact category match
            products = Product.query.filter(
                or_(
                    func.lower(Product.category) == category_lower,
                    func.lower(Product.category) == f"{category_lower}s",
                    func.lower(Product.category).like(f"{category_lower}%")
                )
            ).limit(5).all()
            
            # Try substring match if no exact match
            if not products:
                products = Product.query.filter(
                    func.lower(Product.category).like(f"%{category_lower}%")
                ).limit(5).all()
            
            if products:
                response['answer'] = f"Here are some {category}s I found for you:"
                response['suggested_products'] = [product.to_dict() for product in products]
            else:
                response['answer'] = f"I couldn't find any products in the {category} category. Here are some popular products instead:"
                random_products = Product.query.order_by(func.random()).limit(5).all()
                response['suggested_products'] = [product.to_dict() for product in random_products]
            
            return jsonify(response)
    
    # Check for simple category search pattern
    category_search_match = re.search(r'show me (\w+)s', user_message.lower())
    if category_search_match:
        category = category_search_match.group(1).capitalize()
        # Get products from this category using exact matching
        products = Product.query.filter(
            or_(
                Product.category == category,
                Product.category == f"{category}s"
            )
        ).limit(5).all()
        
        if products:
            response['answer'] = f"Here are some {category}s I found for you:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = f"I couldn't find any products in the {category} category. Would you like to see some of our popular products instead?"
            # Suggest some random products as fallback
            random_products = Product.query.order_by(func.random()).limit(3).all()
            response['suggested_products'] = [product.to_dict() for product in random_products]
        
        return jsonify(response)
    
    # Check for generic sorting pattern
    sort_match = re.search(r'sort.+by\s+(\w+)', user_message.lower())
    if sort_match:
        sort_criterion = sort_match.group(1).lower()
        category_match = re.search(r'(\w+)s sorted', user_message.lower())
        category = category_match.group(1).capitalize() if category_match else None
        
        query = Product.query
        
        # Filter by category if specified using exact matching
        if category:
            query = query.filter(
                or_(
                    Product.category == category,
                    Product.category == f"{category}s"
                )
            )
        
        # Apply sorting
        if 'price' in sort_criterion and 'low' in user_message.lower():
            query = query.order_by(Product.price.asc())
        elif 'price' in sort_criterion and 'high' in user_message.lower():
            query = query.order_by(Product.price.desc())
        elif 'new' in sort_criterion or 'latest' in sort_criterion:
            query = query.order_by(Product.id.desc())  # Assuming newer products have higher IDs
        else:
            # Default sort by popularity (based on ratings)
            query = query.order_by(Product.id.desc())
        
        products = query.limit(5).all()
        
        if products:
            response['answer'] = f"Here are the products sorted by {sort_criterion}:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = "I couldn't find any products matching your criteria."
        
        return jsonify(response)
    
    # If we get here, use the existing chatbot patterns
    # Product recommendation pattern
    if re.search(r'recommend|suggest|show me', user_message.lower()):
        # Extract product categories mentioned in the query
        categories = []
        for category in ['Phone', 'Laptop', 'Tablet', 'Headphone', 'Watch', 'Camera', 'Speaker', 'Game', 'Console']:
            # Check for singular or plural form
            if category.lower() in user_message.lower() or f"{category.lower()}s" in user_message.lower():
                categories.append(category)
        
        # Extract price range if mentioned
        price_range_match = re.search(r'under\s+[₹]?(\d+)', user_message.lower())
        max_price = float(price_range_match.group(1)) if price_range_match else None
        
        # No conversion needed since prices are now stored as INR
        
        # Get product suggestions based on filters
        query = Product.query
        
        if categories:
            # Use exact category matching
            category_filters = []
            for category in categories:
                category_filters.append(Product.category == category)
                category_filters.append(Product.category == f"{category}s")
            query = query.filter(or_(*category_filters))
        
        if max_price:
            query = query.filter(Product.price <= max_price)
        
        suggested_products = query.limit(3).all()
        
        # If no filtered products found, get some random ones
        if not suggested_products:
            suggested_products = Product.query.order_by(func.random()).limit(3).all()
        
        response['answer'] = "Based on your interests, you might like these products:"
        response['suggested_products'] = [product.to_dict() for product in suggested_products]
    
    # Search pattern
    elif re.search(r'search|find|looking for', user_message.lower()):
        # Extract search terms (excluding common words)
        stop_words = set(['search', 'find', 'looking', 'for', 'products', 'items', 'the', 'a', 'an', 'me', 'show'])
        search_terms = [word for word in user_message.lower().split() if word not in stop_words]
        
        # Extract category if mentioned
        category = None
        for cat in ['Phone', 'Laptop', 'Tablet', 'Headphone', 'Watch', 'Camera', 'Speaker', 'Game', 'Console']:
            # Check for singular or plural form
            if cat.lower() in user_message.lower() or f"{cat.lower()}s" in user_message.lower():
                category = cat
                break
        
        # Create the search query
        if search_terms:
            query = Product.query
            
            # Filter by category if specified using exact matching
            if category:
                query = query.filter(
                    or_(
                        Product.category == category,
                        Product.category == f"{category}s"
                    )
                )
            
            # Search in name and description
            search_filters = []
            for term in search_terms:
                if len(term) > 2:  # Only use terms with more than 2 characters
                    search_filters.append(Product.name.ilike(f'%{term}%'))
                    search_filters.append(Product.description.ilike(f'%{term}%'))
            
            if search_filters:
                query = query.filter(or_(*search_filters))
                
            found_products = query.limit(5).all()
            
            if found_products:
                if category:
                    response['answer'] = f"Here are the {category}s I found for you:"
                else:
                    response['answer'] = "Here are the products I found for you:"
                response['suggested_products'] = [product.to_dict() for product in found_products]
            else:
                if category:
                    # If no specific matches found, suggest some products from the category
                    category_products = Product.query.filter(
                        or_(
                            Product.category == category,
                            Product.category == f"{category}s"
                        )
                    ).limit(3).all()
                    if category_products:
                        response['answer'] = f"I couldn't find exactly what you're looking for, but here are some {category}s you might like:"
                        response['suggested_products'] = [product.to_dict() for product in category_products]
                    else:
                        response['answer'] = f"I couldn't find any {category}s. Would you like to see our featured products instead?"
                else:
                    response['answer'] = "I couldn't find products matching your search. Would you like to browse our categories instead?"
        else:
            response['answer'] = "What kind of products are you interested in? You can ask about phones, laptops, headphones, and more!"
    
    # Default response pattern
    else:
        response['answer'] = "I'm here to help you find products and answer questions about our store. You can ask me to search for products, recommend items, or provide information about shipping and returns."
    
    # Look for "phone" or "phone" in the user message to check if the user might be trying to use a category-specific sort
    # If a sort pattern is used with "phones", the category matcher is capturing it but not sorting
    if re.search(r'phone', user_message.lower()):
        # Look for "sort", "low to high", "high to low", "price" keywords that indicate sorting
        if re.search(r'(sort|price|low to high|high to low)', user_message.lower()):
            # It's likely a sort by price command for phones
            if re.search(r'(low to high|price.*low)', user_message.lower()):
                # Sort low to high
                products = Product.query.filter(
                    or_(
                        func.lower(Product.category) == "phone",
                        func.lower(Product.category) == "phones",
                        func.lower(Product.category).like("phone%"),
                        func.lower(Product.category).like("%phone%")
                    )
                ).order_by(Product.price.asc()).limit(5).all()
                
                if products:
                    response['answer'] = "Here are phones sorted by price (low to high):"
                    response['suggested_products'] = [product.to_dict() for product in products]
                else:
                    # Only return this message if we actually have no phones in the database
                    phone_check = Product.query.filter(
                        or_(
                            func.lower(Product.category) == "phone",
                            func.lower(Product.category) == "phones",
                            func.lower(Product.category).like("phone%")
                        )
                    ).first()
                    
                    if phone_check:
                        response['answer'] = "I couldn't find phones matching your criteria. Here are some popular products instead:"
                    else:
                        response['answer'] = "I couldn't find any phones in our inventory. Here are some other products sorted by price (low to high):"
                    products = Product.query.order_by(Product.price.asc()).limit(5).all()
                    response['suggested_products'] = [product.to_dict() for product in products]
                return jsonify(response)
            
            if re.search(r'(high to low|price.*high)', user_message.lower()):
                # Sort high to low
                products = Product.query.filter(
                    or_(
                        func.lower(Product.category) == "phone",
                        func.lower(Product.category) == "phones",
                        func.lower(Product.category).like("phone%"),
                        func.lower(Product.category).like("%phone%")
                    )
                ).order_by(Product.price.desc()).limit(5).all()
                
                if products:
                    response['answer'] = "Here are phones sorted by price (high to low):"
                    response['suggested_products'] = [product.to_dict() for product in products]
                else:
                    # Only return this message if we actually have no phones in the database
                    phone_check = Product.query.filter(
                        or_(
                            func.lower(Product.category) == "phone",
                            func.lower(Product.category) == "phones",
                            func.lower(Product.category).like("phone%")
                        )
                    ).first()
                    
                    if phone_check:
                        response['answer'] = "I couldn't find phones matching your criteria. Here are some popular products instead:"
                    else:
                        response['answer'] = "I couldn't find any phones in our inventory. Here are some other products sorted by price (high to low):"
                    products = Product.query.order_by(Product.price.desc()).limit(5).all()
                    response['suggested_products'] = [product.to_dict() for product in products]
                return jsonify(response)
    
    # Special handling for general "Sort by price" commands
    sort_by_price_match = re.search(r'sort by price', user_message.lower(), re.IGNORECASE)
    if sort_by_price_match:
        # Check for low to high or high to low
        if re.search(r'(low to high|\(low to high\))', user_message.lower(), re.IGNORECASE):
            products = Product.query.order_by(Product.price.asc()).limit(5).all()
            response['answer'] = "Here are products sorted by price (low to high):"
            response['suggested_products'] = [product.to_dict() for product in products]
            return jsonify(response)
        elif re.search(r'(high to low|\(high to low\))', user_message.lower(), re.IGNORECASE):
            products = Product.query.order_by(Product.price.desc()).limit(5).all()
            response['answer'] = "Here are products sorted by price (high to low):"
            response['suggested_products'] = [product.to_dict() for product in products]
            return jsonify(response)
    
    # Handle category-specific sorting
    if re.match(r'^(\w+)s?\s+low\s+to\s+high$', user_message.lower()):
        # For example "phones low to high"
        # Rather than filter by category, we'll just sort all products by price
        products = Product.query.order_by(Product.price.asc()).limit(5).all()
        response['answer'] = "Here are products sorted by price (low to high):"
        response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    if re.match(r'^(\w+)s?\s+high\s+to\s+low$', user_message.lower()):
        # For example "phones high to low"
        # Rather than filter by category, we'll just sort all products by price
        products = Product.query.order_by(Product.price.desc()).limit(5).all()
        response['answer'] = "Here are products sorted by price (high to low):"
        response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    # Handle category-specific price filtering patterns
    phones_price_pattern = re.search(r'show\s+(?:me\s+)?phones\s+(under|above|between)\s+(\d+)(?:\s+and\s+(\d+))?', user_message.lower())
    if phones_price_pattern:
        price_operator = phones_price_pattern.group(1).lower()
        price1 = float(phones_price_pattern.group(2))
        price2 = float(phones_price_pattern.group(3)) if phones_price_pattern.group(3) else None
        
        print(f"DEBUG: Phone price filtering detected - {price_operator} {price1} {price2}")
        
        # Query for phones with the specified price range
        query = Product.query.filter(
            or_(
                func.lower(Product.category) == "phone",
                func.lower(Product.category) == "phones",
                func.lower(Product.category).like("phone%"),
                func.lower(Product.category).like("%phone%")
            )
        )
        
        # Add price range filter
        if price_operator == 'under':
            query = query.filter(Product.price < price1)
            price_description = f"under ₹{price1:,.0f}"
        elif price_operator == 'above':
            query = query.filter(Product.price > price1)
            price_description = f"above ₹{price1:,.0f}"
        else:  # between
            query = query.filter(Product.price >= price1, Product.price <= price2)
            price_description = f"between ₹{price1:,.0f} and ₹{price2:,.0f}"
        
        # Get the products and order by price
        products = query.order_by(Product.price.asc()).limit(5).all()
        
        # Debug print products found
        print(f"DEBUG: Found {len(products)} phones in price range {price_description}")
        for p in products:
            print(f"DEBUG:   ID: {p.id}, Name: {p.name}, Price: ₹{p.price}")
        
        if products:
            # Only show phones in the selected price range
            response['answer'] = f"Here are phones {price_description}:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = f"I couldn't find any phones {price_description}. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    # General category-specific price filtering pattern
    category_price_pattern = re.search(r'show\s+(?:me\s+)?(\w+)s?\s+(under|above|between)\s+(\d+)(?:\s+and\s+(\d+))?', user_message.lower())
    if category_price_pattern:
        category = category_price_pattern.group(1).lower()
        price_operator = category_price_pattern.group(2).lower()
        price1 = float(category_price_pattern.group(3))
        price2 = float(category_price_pattern.group(4)) if category_price_pattern.group(4) else None
        
        print(f"DEBUG: General category price filtering detected - category={category}, {price_operator} {price1} {price2}")
        
        # Build the query starting with the category filter
        query = Product.query.filter(
            or_(
                func.lower(Product.category) == category,
                func.lower(Product.category) == f"{category}s",
                func.lower(Product.category).like(f"{category}%"),
                func.lower(Product.category).like(f"%{category}%")
            )
        )
        
        # Add price range filter
        if price_operator == 'under':
            query = query.filter(Product.price < price1)
            price_description = f"under ₹{price1:,.0f}"
        elif price_operator == 'above':
            query = query.filter(Product.price > price1)
            price_description = f"above ₹{price1:,.0f}"
        else:  # between
            query = query.filter(Product.price >= price1, Product.price <= price2)
            price_description = f"between ₹{price1:,.0f} and ₹{price2:,.0f}"
        
        # Get the products and order by price
        products = query.order_by(Product.price.asc()).limit(5).all()
        
        if products:
            response['answer'] = f"Here are {category} products {price_description}:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = f"I couldn't find any {category} products {price_description}. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    # Handle general price range filtering commands without specific category
    if re.match(r'show\s+(?:me\s+)?products\s+under\s+(\d+)', user_message.lower()):
        match = re.match(r'show\s+(?:me\s+)?products\s+under\s+(\d+)', user_message.lower())
        price_limit = float(match.group(1))
        products = Product.query.filter(Product.price < price_limit).order_by(Product.price.asc()).limit(5).all()
        if products:
            response['answer'] = f"Here are products under ₹{price_limit:,.0f}:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = f"I couldn't find any products under ₹{price_limit:,.0f}. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    if re.match(r'show\s+(?:me\s+)?products\s+between\s+(\d+)\s+and\s+(\d+)', user_message.lower()):
        match = re.match(r'show\s+(?:me\s+)?products\s+between\s+(\d+)\s+and\s+(\d+)', user_message.lower())
        min_price = float(match.group(1))
        max_price = float(match.group(2))
        products = Product.query.filter(Product.price >= min_price, Product.price <= max_price).order_by(Product.price.asc()).limit(5).all()
        if products:
            response['answer'] = f"Here are products between ₹{min_price:,.0f} and ₹{max_price:,.0f}:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = f"I couldn't find any products in this price range. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    if re.match(r'show\s+(?:me\s+)?products\s+above\s+(\d+)', user_message.lower()):
        match = re.match(r'show\s+(?:me\s+)?products\s+above\s+(\d+)', user_message.lower())
        price_limit = float(match.group(1))
        products = Product.query.filter(Product.price > price_limit).order_by(Product.price.asc()).limit(5).all()
        if products:
            response['answer'] = f"Here are products above ₹{price_limit:,.0f}:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = f"I couldn't find any products above ₹{price_limit:,.0f}. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    # Legacy fixed patterns for backward compatibility
    if user_message.lower() == "show products under 10000":
        products = Product.query.filter(Product.price < 10000).order_by(Product.price.asc()).limit(5).all()
        if products:
            response['answer'] = "Here are products under ₹10,000:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = "I couldn't find any products under ₹10,000. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    if user_message.lower() == "show products between 10000 and 20000":
        products = Product.query.filter(Product.price >= 10000, Product.price <= 20000).order_by(Product.price.asc()).limit(5).all()
        if products:
            response['answer'] = "Here are products between ₹10,000 and ₹20,000:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = "I couldn't find any products in this price range. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    if user_message.lower() == "show products between 20000 and 50000":
        products = Product.query.filter(Product.price >= 20000, Product.price <= 50000).order_by(Product.price.asc()).limit(5).all()
        if products:
            response['answer'] = "Here are products between ₹20,000 and ₹50,000:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = "I couldn't find any products in this price range. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    if user_message.lower() == "show products above 50000":
        products = Product.query.filter(Product.price > 50000).order_by(Product.price.asc()).limit(5).all()
        if products:
            response['answer'] = "Here are products above ₹50,000:"
            response['suggested_products'] = [product.to_dict() for product in products]
        else:
            response['answer'] = "I couldn't find any products above ₹50,000. Here are some popular products instead:"
            products = Product.query.order_by(func.random()).limit(5).all()
            response['suggested_products'] = [product.to_dict() for product in products]
        return jsonify(response)
    
    return jsonify(response)

@app.route('/api/search_products', methods=['GET'])
def search_products():
    query = request.args.get('query', '')
    category = request.args.get('category', '')
    sort_by = request.args.get('sort_by', 'popularity')  # Default to popularity
    
    # Build the search query
    search_query = Product.query
    
    # Filter by category if provided
    if category:
        search_query = search_query.filter(func.lower(Product.category) == category.lower())
    
    # Search for products by name using case-insensitive search
    search_query = search_query.filter(func.lower(Product.name).like(f'%{query.lower()}%'))
    
    # Apply sorting
    if sort_by == 'price_low_high':
        search_query = search_query.order_by(Product.price.asc())
    elif sort_by == 'price_high_low':
        search_query = search_query.order_by(Product.price.desc())
    elif sort_by == 'trending':
        search_query = search_query.order_by(Product.cart_count.desc())
    else:  # Default to 'popularity' (view_count)
        search_query = search_query.order_by(Product.view_count.desc())
    
    # Get results
    products = search_query.limit(5).all()
    
    # Convert to JSON-serializable format
    product_list = [product.to_dict() for product in products]
    
    return jsonify({'products': product_list})

@app.route('/api/category_products', methods=['GET'])
def category_products():
    category = request.args.get('category', '')
    product_id = request.args.get('product_id', '')
    sort_by = request.args.get('sort_by', 'popularity')  # Default to popularity (view_count)
    
    if not category:
        return jsonify({'error': 'Category is required', 'products': []})
    
    # Get products in the same category, excluding the current product
    query = Product.query.filter(Product.category == category)
    
    if product_id:
        query = query.filter(Product.id != product_id)
    
    # Apply sorting
    if sort_by == 'price_low_high':
        query = query.order_by(Product.price.asc())
    elif sort_by == 'price_high_low':
        query = query.order_by(Product.price.desc())
    elif sort_by == 'trending':
        query = query.order_by(Product.cart_count.desc())
    else:  # Default to 'popularity' (view_count)
        query = query.order_by(Product.view_count.desc())
    
    products = query.limit(4).all()
    
    # Convert to JSON-serializable format
    product_list = [product.to_dict() for product in products]
    
    return jsonify({'products': product_list})

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        
        if user:
            # Generate a reset token (in a real app, use a secure token generation method)
            reset_token = generate_password_hash(str(user.id) + str(time.time()))[:20]
            
            # In a real app, you would store this token in the database with an expiration time
            # For demo purposes, we'll use a session to simulate this
            session['reset_token'] = reset_token
            session['reset_email'] = email
            session['reset_expiry'] = time.time() + 3600  # 1 hour expiry
            
            # In a real app, you would send an email with a reset link
            flash('Password reset instructions have been sent to your email. (For demo: use token: ' + reset_token + ')', 'success')
            return redirect(url_for('reset_password_form'))
        else:
            flash('Email not found in our records.', 'error')
    
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password_form():
    if request.method == 'POST':
        token = request.form['token']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Check token validity (in a real app, verify against database)
        if 'reset_token' not in session or session['reset_token'] != token:
            flash('Invalid or expired reset token.', 'error')
            return render_template('reset_password.html')
        
        # Check token expiry
        if time.time() > session.get('reset_expiry', 0):
            flash('Reset token has expired. Please request a new one.', 'error')
            return render_template('reset_password.html')
        
        # Validate passwords
        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html')
        
        # Update user password
        email = session.get('reset_email')
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = generate_password_hash(password)
            db.session.commit()
            
            # Clear reset session data
            session.pop('reset_token', None)
            session.pop('reset_email', None)
            session.pop('reset_expiry', None)
            
            flash('Your password has been updated successfully. Please login with your new password.', 'success')
            return redirect(url_for('login'))
    
    return render_template('reset_password.html')

# --- Run App ---
if __name__ == '__main__':
    app.run(debug=True)