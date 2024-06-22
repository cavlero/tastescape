from app import app, db
import sqlalchemy.orm as so
import sqlalchemy as sa

@app.shell_context_processor
def make_shell_context():
    return {'sa' : sa, 'so' : so, 'db' : db}
