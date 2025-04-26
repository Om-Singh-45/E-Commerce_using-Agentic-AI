from app import app, db, Product
from sqlalchemy import or_, func

# Use the app context
with app.app_context():
    # Query for phones using various patterns
    phones = Product.query.filter(
        or_(
            func.lower(Product.category) == "phone",
            func.lower(Product.category) == "phones",
            func.lower(Product.category).like("phone%"),
            func.lower(Product.category).like("%phone%")
        )
    ).all()
    
    # Display results
    print(f"Found {len(phones)} phone products:")
    
    if phones:
        for p in phones:
            print(f"ID: {p.id}, Name: {p.name}, Price: ₹{p.price}, Category: {p.category}")
        
        # Check price ranges
        phones_under_10k = [p for p in phones if p.price < 10000]
        phones_10k_to_20k = [p for p in phones if 10000 <= p.price <= 20000]
        phones_20k_to_50k = [p for p in phones if 20000 <= p.price <= 50000]
        phones_above_50k = [p for p in phones if p.price > 50000]
        
        print(f"\nPhones under ₹10,000: {len(phones_under_10k)}")
        print(f"Phones ₹10,000 - ₹20,000: {len(phones_10k_to_20k)}")
        print(f"Phones ₹20,000 - ₹50,000: {len(phones_20k_to_50k)}")
        print(f"Phones above ₹50,000: {len(phones_above_50k)}")
    else:
        print("No phones found in the database.") 