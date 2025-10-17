#from app import app, db

#with app.app_context():
#   db.create_all()
#    print("Database initialized.")
# init_db.py (Corrected)

from app import app, db

# Creates the application context for SQLAlchemy
with app.app_context():
    # This import makes your models visible to SQLAlchemy
    import models

    # Now, this command will find your models and create the tables
    db.create_all()
    print("Database initialized.")