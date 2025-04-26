from app import app, db, Product
from sqlalchemy import or_, func
import re

# Test user message
test_message = "Show me phones between 10000 and 20000"

# Use the app context
with app.app_context():
    # Try to match the pattern
    phones_price_pattern = re.search(r'show\s+(?:me\s+)?phones\s+(under|above|between)\s+(\d+)(?:\s+and\s+(\d+))?', test_message.lower())
    
    if phones_price_pattern:
        print("Pattern matched!")
        price_operator = phones_price_pattern.group(1).lower()
        price1 = float(phones_price_pattern.group(2))
        price2 = float(phones_price_pattern.group(3)) if phones_price_pattern.group(3) else None
        
        print(f"Extracted: operator={price_operator}, price1={price1}, price2={price2}")
        
        # Query for phones with the specified price range
        query = Product.query.filter(
            or_(
                func.lower(Product.category) == "phone",
                func.lower(Product.category) == "phones",
                func.lower(Product.category).like("phone%"),
                func.lower(Product.category).like("%phone%")
            )
        )
        
        # Get all phones first to see if we have any
        all_phones = query.all()
        print(f"Total phones found: {len(all_phones)}")
        for p in all_phones:
            print(f"  ID: {p.id}, Name: {p.name}, Price: ₹{p.price}, Category: {p.category}")
        
        # Add price range filter
        if price_operator == 'under':
            query = query.filter(Product.price < price1)
            price_description = f"under ₹{price1:,.0f}"
        elif price_operator == 'above':
            query = query.filter(Product.price > price1)
            price_description = f"above ₹{price1:,.0f}"
        else:  # between
            print(f"Filtering for phones between ₹{price1} and ₹{price2}")
            query = query.filter(Product.price >= price1, Product.price <= price2)
            price_description = f"between ₹{price1:,.0f} and ₹{price2:,.0f}"
        
        # Get the products and order by price
        products = query.order_by(Product.price.asc()).all()
        
        print(f"\nFiltered phones {price_description}: {len(products)}")
        for p in products:
            print(f"  ID: {p.id}, Name: {p.name}, Price: ₹{p.price}, Category: {p.category}")
    else:
        print("Pattern didn't match!") 