# E-Commerce Platform

A full-featured e-commerce web application built with Flask and MySQL. This platform provides a comprehensive online shopping experience with multiple user roles, product management, shopping cart functionality, a smart shopping assistant, and behavioral product recommendations.

## Features

### User Management
- User registration and login with role-based authorization (buyer, seller, admin)
- Secure password management with hashing
- User profile management
- Password reset functionality

### Product Management
- Product listings with detailed information (name, description, price, images)
- Category-based organization
- Product search with multiple filtering options
- Sorting by popularity, price, and trends
- Product comparison functionality

### Shopping Features
- Shopping cart system
- Secure checkout process
- Order tracking and history
- Transaction management

### Seller Dashboard
- Product listing management (add, edit, delete)
- Order management for sold items
- Sales analytics

### Behavioral Product Recommendations
- Dynamic product sorting based on user behavior
- View count tracking for popularity ranking
- Cart addition tracking for trend analysis
- Automatic highlighting of trending products

### Smart Shopping Assistant
- Interactive chatbot for product discovery
- Natural language processing for user queries
- Product recommendations based on preferences
- Category and price-based filtering
- Information about shipping, payment, and returns

### Communication System
- Direct messaging between buyers and sellers
- Message read status tracking
- Unread message indicators

## Technology Stack

### Backend
- Flask web framework
- SQLAlchemy ORM
- MySQL database
- Flask-Migrate for database migrations
- Werkzeug for security utilities

### Frontend
- HTML5, CSS3, JavaScript
- Bootstrap 5 for responsive design
- Font Awesome for icons
- Custom responsive UI components

### Security
- Password hashing
- CSRF protection
- Session management
- Role-based access control

## Installation and Setup

### Prerequisites
- Python 3.9 or higher
- MySQL 8.0 or higher
- pip package manager

### Environment Setup

1. Clone the repository
```bash
git clone https://github.com/yourusername/ecommerce-platform.git
cd ecommerce-platform
```

2. Create and activate virtual environment
```bash
python -m venv venv
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Configure MySQL database
```bash
# Create a MySQL database named 'ecommerce'
mysql -u root -p
CREATE DATABASE ecommerce;
EXIT;
```

5. Initialize the database
```bash
flask db init
flask db migrate -m "Initial migration"
flask db upgrade
```

6. Run the application
```bash
flask run
```

7. Access the application at http://localhost:5000

## Project Structure

```
ecommerce-platform/
├── app.py                 # Main application file
├── requirements.txt       # Python dependencies
├── static/                # Static files (CSS, JS, images)
│   ├── uploads/           # Product images uploaded by sellers
│   ├── img/               # Static image assets
│   └── models/            # Frontend model files
├── templates/             # HTML templates
│   ├── home.html          # Homepage template
│   ├── products.html      # Product listing template
│   ├── product_detail.html# Product detail template
│   ├── dashboard.html     # User dashboard template
│   └── ...                # Other templates
├── migrations/            # Database migration files
└── README.md              # Project documentation
```

## User Roles

### Buyer
- Browse products
- Add products to cart
- Checkout and place orders
- View order history
- Message sellers

### Seller
- Manage products (add, edit, delete)
- View and manage orders for their products
- Message buyers
- Track product performance

### Admin
- Manage all products and users
- View all orders
- Access administrative features

## Behavioral Product Sorter

The platform includes a lightweight behavioral product recommendation system:

- **Popularity Tracking**: Products viewed more frequently are ranked higher
- **Trend Analysis**: Products added to carts more often are highlighted as trending
- **Dynamic Reshuffling**: Product listings automatically reorder based on user behavior
- **Featured Products**: Homepage highlights the most popular products

This system creates a personalized shopping experience similar to major e-commerce platforms but with a lightweight implementation that doesn't require complex machine learning models.

## License

[MIT License](LICENSE)

## Contact

Email- omsingh859122@gmail.com

![Screenshot 2025-04-26 193313](https://github.com/user-attachments/assets/5a5c178e-7bb9-47e7-90f9-7cc71150b441)
![Screenshot 2025-04-26 193231](https://github.com/user-attachments/assets/ea1c51a7-5b4c-4878-ad0f-8d5adc66bf44)
![Screenshot 2025-04-26 193201](https://github.com/user-attachments/assets/44f60116-b3a4-4df4-b1a8-3945b7411486)
![Screenshot 2025-04-26 193132](https://github.com/user-attachments/assets/41eadfeb-bfbb-4569-9f4f-af7e9bb99aca)
![Screenshot 2025-04-26 193108](https://github.com/user-attachments/assets/cd202604-e2c0-462e-a368-d74ac0536ef6)
![Screenshot 2025-04-26 193006](https://github.com/user-attachments/assets/d3d94252-e77f-4b33-8ab8-6d2816ffbed0)
![Screenshot 2025-04-26 192937](https://github.com/user-attachments/assets/b37e515b-acf9-454e-b880-3c72da500d04)
![Screenshot 2025-04-26 192906](https://github.com/user-attachments/assets/1ea159e3-ed91-4d41-843a-386d652a1814)
![Screenshot 2025-04-26 192814](https://github.com/user-attachments/assets/212d5bbf-64b3-48bc-8b0f-bbde7c2b1e72)
![Screenshot 2025-04-26 192739](https://github.com/user-attachments/assets/d0129b93-38c9-4060-8238-8613a1466f7a)
![Screenshot 2025-04-26 192712](https://github.com/user-attachments/assets/2d826d53-e174-4888-9c00-013cc7157d07)
![Screenshot 2025-04-26 192641](https://github.com/user-attachments/assets/3ac49ef8-efc3-40bd-ba51-ccaf392bed4c)
![Screenshot 2025-04-26 192529](https://github.com/user-attachments/assets/a2544c6d-4d66-4aff-9f43-c2909c40c428)
![Screenshot 2025-04-26 192452](https://github.com/user-attachments/assets/461f1503-15eb-4b15-a58b-0d10e56fbce4)
![Screenshot 2025-04-26 192400](https://github.com/user-attachments/assets/5ddc9ce2-c450-4176-96c5-d69bbc27da6a)


