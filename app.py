# app.py
import stripe
from flask import Flask, jsonify, request, session
from flask_login import login_user, logout_user, current_user, login_required, LoginManager
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
# Use an in-memory SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
app.config['SECRET_KEY'] = 'secret_key'
db = SQLAlchemy(app)
login_manager = LoginManager(app)

# Configure Stripe
app.config['STRIPE_SECRET_KEY'] = 'your_stripe_secret_key'
stripe.api_key = app.config['STRIPE_SECRET_KEY']

# Define database models
class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    price = db.Column(db.Float)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    address = db.Column(db.String(200))
    phone_number = db.Column(db.String(20))
    payment_info = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean)

class Cart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'))
    quantity = db.Column(db.Integer)

with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def welcome():
    return "Welcome to the Demo Marketplace"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/login', methods=['POST'])
def user_login():
    # User login implementation
    username = request.json['username']
    password = request.json['password']

    user = User.query.filter_by(username=username).first()

    if user and user.password == password:
        login_user(user)
        return jsonify({'message': 'Login successful'})
    else:
        return jsonify({'message': 'Invalid username or password'})

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logout successful'})

@app.route('/catalog')
def view_catalog():
    products = Product.query.all()
    product_data = []
    for product in products:
        product_info = {
            'id': product.id,
            'name': product.name,
            'category': Category.query.get(product.category_id).name,
            'price': product.price
        }
        product_data.append(product_info)
    return jsonify(product_data)

@app.route('/add_to_cart', methods=['POST'])
@login_required
def add_to_cart():
    product_id = int(request.json['product_id'])
    quantity = int(request.json['quantity'])

    product = Product.query.get(product_id)
    user = User.query.get(current_user.id)

    if product and not user.is_admin:
        cart_item = Cart(product_id=product_id, quantity=quantity, user_id=current_user.id)
        db.session.add(cart_item)
        db.session.commit()
        return jsonify({"message": "Product added to the cart successfully"})
    else:
        return jsonify({"error": "Product not found"}), 404

@app.route('/remove_from_cart/<int:cart_id>', methods=['POST'])
@login_required
def remove_from_cart(cart_id):
    cart_item = Cart.query.get(cart_id)
    user = User.query.get(current_user.id)

    if cart_item and not user.is_admin:
        db.session.delete(cart_item)
        db.session.commit()
        return jsonify({"message": "Product removed from the cart successfully"})
    else:
        return jsonify({"error": "Cart item not found"}), 404

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart_items = get_cart_items()
    line_items = []
    for item in cart_items:
        line_item = {
            'price_data': {
                'currency': 'inr',  # Set the currency to INR
                'unit_amount': int(item['price']),
                'product_data': {
                    'name': item['name'],
                },
            },
            'quantity': item['quantity'],
        }
        line_items.append(line_item)

    payment_methods = request.json.get('payment_methods', [])
    payment_intent_data = {
        'amount': calculate_order_amount(cart_items),
        'currency': 'inr',
        'payment_method_types': payment_methods,
    }

    payment_intent = stripe.PaymentIntent.create(**payment_intent_data)

    if payment_intent.status == 'succeeded':
        clear_cart()
        return jsonify({'client_secret': payment_intent.client_secret, 'status': 'successful payment'})
    else:
        return jsonify({'client_secret': payment_intent.client_secret, 'status': 'payment failed'})

@app.route('/add_product', methods=['POST'])
@login_required
def add_product():
    if current_user.is_admin:
        product_name = request.json['product_name']
        price = request.json['price']
        category_id = request.json['category_id']
        product = Product(name=product_name, price=price, category_id=category_id)
        db.session.add(product)
        db.session.commit()
        return jsonify({'message': 'Product added successfully'})
    else:
        return jsonify({'error': 'Only admin users can add products'})

@app.route('/remove_product/<int:product_id>', methods=['POST'])
@login_required
def remove_product(product_id):
    if current_user.is_admin:
        product = Product.query.get(product_id)
        if product:
            db.session.delete(product)
            db.session.commit()
            return jsonify({'message': 'Product removed successfully'})
        else:
            return jsonify({'error': 'Product not found'})
    else:
        return jsonify({'error': 'Only admin users can remove products'})

@app.route('/register', methods=['POST'])
def user_register():
    username = request.json['username']
    email = request.json['email']
    password = request.json['password']
    first_name = request.json['first_name']
    last_name = request.json['last_name']
    address = request.json['address']
    phone_number = request.json['phone_number']
    payment_info = request.json['payment_info']

    user = User(username=username, email=email, password=password, first_name=first_name, last_name=last_name, address=address, phone_number=phone_number, payment_info=payment_info, is_admin=False)
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully'})

@app.route('/admin_register', methods=['POST'])
def admin_register():
    username = request.json['username']
    email = request.json['email']
    password = request.json['password']
    first_name = request.json['first_name']
    last_name = request.json['last_name']
    address = request.json['address']
    phone_number = request.json['phone_number']
    payment_info = request.json['payment_info']

    user = User(username=username, email=email, password=password, first_name=first_name, last_name=last_name, address=address, phone_number=phone_number, payment_info=payment_info, is_admin=True)
    db.session.add(user)
    db.session.commit()

    return jsonify({'message': 'Admin registered successfully'})

# Helper functions
def get_cart_items():
    cart_items = Cart.query.filter_by(user_id=current_user.id).all()
    items = []
    for item in cart_items:
        product = Product.query.get(item.product_id)
        items.append({
            'id': item.id,
            'name': product.name,
            'price': product.price,
            'quantity': item.quantity,
        })
    return items

def calculate_order_amount(cart_items):
    total_amount = 0
    for item in cart_items:
        total_amount += item['price'] * item['quantity']
    return int(total_amount * 100)

def clear_cart():
    Cart.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()

if __name__ == '__main__':
    app.run(debug=True)
