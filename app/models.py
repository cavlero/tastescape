from sqlalchemy import Column, Integer, String
from app import db

# Recipe table SQLite
class Recipe(db.Model):
    __tablename__ = 'recipe_data'
    id = Column("id", Integer, primary_key=True)
    nyt_recipe_id = Column("nyt_recipe_id", Integer)
    recipe_title = Column('recipe_title', String)
    description = Column('description', String)
    recipe_yield = Column('recipe_yield', String)
    total_time = Column('total_time', String)
    rating= Column('rating', Integer)
    author = Column('author', String)
    image = Column('image', String)
    ingredients_full = Column('ingredients_full', String)
    steps = Column('steps', String)
    tags = Column('tags', String)

    def __repr__(self):
        return '<Recipe {}>'.format(self.recipe_title)
 
