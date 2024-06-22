from flask import render_template, redirect, request, url_for, send_from_directory
import sqlalchemy as sa
from sqlalchemy import or_, case
from app import app, db
from app.forms import SearchForm
from app.models import Recipe
from config import Config
import os.path
from ultralytics import YOLO
import cv2
from PIL import Image
import io

@app.route('/index')
@app.route('/')
def index():
    # Recipe count + amt of predictions for dynamic numbers on index page
    recipe_amt = len(Recipe.query.all())
    predictions= len([name for name in os.listdir('./runs/detect') if os.path.isfile(os.path.join('./runs/detect', name))])
    return render_template('index.html', title='Home', recipe_amt=recipe_amt, predictions=predictions)

@app.route('/demo', methods=['GET', 'POST'])
def demo():
    """
    Search form which can handle multiple searches seperated by a comma. Currently only takes jpg.
    Returns HTML ready code to view predictions plotted on image, confidence scores and predicted classes.
    """
    form = SearchForm()

    # Dictionary to map numbers (int) to class names, based on .yaml file from YOLO model
    class_mapping = {
        0: 'apple',1: 'avocado',2: 'carrot',3: 'cauliflower',4: 'celery',5: 'chili pepper',6: 'corn',7: 'cucumber',8: 'eggplant',9: 'garlic',
        10: 'ginger',11: 'grapes',12: 'banana',13: 'kiwi',14: 'lemon',15: 'lettuce',16: 'lime',17: 'mango',18: 'onion',19: 'orange',20: 'pear',
        21: 'pineapple',22: 'pomegranate',23: 'beet',24: 'potato',25: 'pumpkin',26: 'radish',27: 'raspberry',28: 'spinach',29: 'spring onion',
        30: 'strawberry',31: 'sweet potato',32: 'tomato',33: 'watermelon',34: 'bell pepper',35: 'zucchini',36: 'blackberry',37: 'blueberry',
        38: 'broccoli',39: 'brussels sprout',40: 'cabbage'}

    # Page-filler (non-essential, showcase filler)
    filler_classes=['bell pepper', 'bell pepper', 'apple', 'tomato', 'apple', 'bell pepper', 'tomato', 'tomato'] 
    filler_conf_scores=[91,84,81,76,68,59,55,46]

    # Upload + Inference for image. Print checkpoints in terminal to see progress status.
    if request.method == 'POST':
        if 'file' in request.files:
            f = request.files['file']
            basepath = os.path.dirname(__file__)
            filepath = os.path.join(basepath, 'uploads', f.filename)
            print("upload name", filepath)
            f.save(filepath)
            global imgpath
            demo.imgpath = f.filename
            print("printing predict image: ", demo)

            # Ensure file extension is jpg, print to confirm in terminal.
            # Convert to png if possible
            file_extension = f.filename.rsplit('.', 1)[1].lower()
            if file_extension == 'jpg':
                print("Filepath approved")
                jpg_filepath = filepath
                pass
            elif file_extension == 'png':
                print("Converting PNG to JPG...")
                # Open the PNG file and convert it to JPG
                with Image.open(filepath) as img:
                    jpg_filepath = os.path.splitext(filepath)[0] + '.jpg'
                    img.convert('RGB').save(jpg_filepath)
                    print("PNG converted to JPG. New filepath:", jpg_filepath)
                    pass
            # Update filepath to point to the new JPG file
            filepath = jpg_filepath
            
            # Read image with opencv
            img = cv2.imread(filepath)
            frame = cv2.imencode('.jpg', cv2.UMat(img))[1].tobytes()
            image = Image.open(io.BytesIO(frame))

            # Load pre-trained weights as yolo model
            model_path = os.path.join(basepath, 'best.pt')
            model = YOLO(model_path)

            # Predict on encoded image, save predictions in runs/detect folder
            # Time inference for display
            results = model(image, save=True, conf=0.4)

            # Initialize lists to store class and confidence data
            conf_scores = []
            classes = []
            for result in results[0].boxes.data:
                # Tensor, confidence is stored in index 4, class number is stored in index 5
                # Extract them here and append to list of confidence scores and classes
                    conf_scores.append(result[4])
                    classes.append(result[5])

            # Change confidence score to integer after rounding and multiplying by 100 for percentual representation
            conf_scores = [int(round(tensor.item() * 100)) for tensor in conf_scores]

            # Change tensor to int, then apply class mapping using class_mapping dictionary
            classes = [class_mapping.get(int(tensor.item()), 'unknown') for tensor in classes]

            # Create string for search query with unique classes detected in image
            unique_classes = ", ".join(set(classes))

            # Get preprocess, inference and postprocess times
            preprocess = int(round(results[0].speed['preprocess'], 0))
            inference = int(round(results[0].speed['inference'], 0))
            postprocess = int(round(results[0].speed['postprocess'], 0))
            
            # Get image from detect folder to display on HTML page
            folder_path = './runs/detect'
            files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
            latest_img = max(files, key=lambda x: os.path.getctime(os.path.join(folder_path, x)))

            return render_template('demo.html', form=form, filename = latest_img, results=results[0].boxes.data, 
                conf_scores=conf_scores, classes=classes, output_len=len(classes), inf_time = inference, pre_time = preprocess, pos_time=postprocess,
                unique_classes = unique_classes)
                               
    return render_template('demo.html', form=form, filename=None, conf_scores=filler_conf_scores, classes=filler_classes, 
        output_len=len(filler_classes), inf_time=None, pre_time=None, pos_time=None, unique_classes=", ".join(set(filler_classes)))

@app.route('/<path:filename>')
def get_image(filename):
    """ Serves image with inference for display on demo page """
    
    return send_from_directory("../runs/detect", filename)

@app.route('/search', methods=["GET", "POST"])
def search():
    """ Search form which can handle multiple searches separated by a comma """
    
    form = SearchForm()
    page = request.args.get('page', 1, type=int)
    per_page = 10   

    search_term = form.search.data
    directed_query = request.args.get('q')
        
    if directed_query is not None and search_term is None:
        # Retrieve search query and split multiple items by comma
        directed_query = request.args.get('q')
        ingredients = directed_query.split(', ') 
        # like conditions for each item in query
        ilike_conditions = [Recipe.ingredients_full.ilike(f'%____{ingredient.strip()}____%') for ingredient in ingredients]
        # case condition to set up order-by based on count of matches from search query with recipe
        case_conditions = [case((Recipe.ingredients_full.ilike(f'%{ingredient}%'), 1), else_=0) for ingredient in ingredients]
        order_by_expression = sum(case_conditions).desc()

        # Apply the filter and order by conditions
        results = (
            Recipe.query
            .filter(or_(*ilike_conditions))
            .order_by(order_by_expression)
            .paginate(page=page, per_page=per_page)
        )
        # Pagination
        next_url = url_for('search', page=results.next_num, q=directed_query) \
            if results.has_next else None        

        prev_url = url_for('search', page=results.prev_num, q=directed_query) \
            if results.has_prev else None
        
        # Get count of how many ingredients from query match the recipe for display on page
        matching_ingredients_counts = []
        for recipe in results.items:
            matching_count = sum(ingredient.strip() in recipe.ingredients_full for ingredient in ingredients)
            matching_ingredients_counts.append(matching_count)

        return render_template('search.html', form=form, query=directed_query, 
        results=results, prev_url=prev_url, next_url=next_url, matching_ingredients_counts=matching_ingredients_counts)

    results = None
    return render_template('search.html', form=form, results=results)

@app.route('/submit_search', methods=["POST"])
def submit_search():
    query = request.form['search']
    return redirect(url_for('search', q=query))

@app.route('/about')
def about():
    # Compact list of classes for HTML page
    class_list = [
    "Apple", "Avocado", "Banana", "Beet", "Bell Pepper", "Blackberry", "Blueberry", "Broccoli", "Brussels Sprout", 
    "Cabbage", "Carrot", "Cauliflower", "Celery", "Chili Pepper", "Corn", "Cucumber", "Eggplant", "Garlic", 
    "Ginger", "Grapes", "Kiwi", "Lemon", "Lettuce", "Lime", "Mango", "Onion", "Orange", "Pear", "Pineapple", 
    "Pomegranate", "Potato", "Pumpkin", "Radish", "Raspberry", "Spinach", "Spring Onion", "Strawberry",
    "Sweet Potato", "Tomato", "Watermelon", "Zucchini"]
    return render_template('about.html', class_list = class_list)

@app.route('/recipes/<search_id>', methods=['POST', 'GET'])
def show_recipe(search_id):
    # Selects recipe based on id
    selected_recipe = db.first_or_404(sa.select(Recipe).where(Recipe.id == search_id))
    # Recipe steps in list format for displaying on HTML page
    steps_list = selected_recipe.steps.split('____') if selected_recipe.steps else []
    # Recipe ingredients in list format for displaying on HTML page
    ingredients_list = selected_recipe.ingredients_full.split('____') if selected_recipe.ingredients_full else []
    # Query all recipes for 'recommended recipes' filler
    recipes = Recipe.query
   
    return render_template("recipe_single.html", recipe=selected_recipe, steps_list=steps_list, ingredients_list=ingredients_list, recipes=recipes)



