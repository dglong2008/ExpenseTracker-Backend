from api import create_app, db

app = create_app()

# A simple CLI command to initialize our tables in Neon
# Run this locally using: uv run flask --app api/index.py init-db
@app.cli.command("init-db")
def init_db():
    with app.app_context():
        db.create_all()
        print("Database tables created successfully!")

if __name__ == '__main__':
    app.run(debug=True)