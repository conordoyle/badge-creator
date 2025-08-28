import os
from flask import Flask, render_template, request, jsonify, send_from_directory, make_response, url_for
from werkzeug.utils import secure_filename
from remove_bg import remove_background_from_image
from PIL import Image, ImageDraw, ImageFont
from fpdf import FPDF

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
GENERATED_FOLDER = 'generated_badges'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['GENERATED_FOLDER'] = GENERATED_FOLDER

# Color mapping for categories
CATEGORY_COLORS = {
    "AX7": "Yellow",
    "Deftones": "Yellow",
    "Korn": "Yellow",
    "LNT": "White",
    "System of a Down Crew": "black",
    "Polyphia": "white",
    "Wisp": "white",
    "Locals": "lightblue",
}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_badge', methods=['POST'])
def create_badge():
    if 'photo' not in request.files:
        return "No photo part", 400
    file = request.files['photo']
    if file.filename == '':
        return "No selected file", 400

    name = request.form['name']
    category = request.form['category']
    fontSize = int(request.form.get('fontSize', 75))  # Default to 75 if not provided

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)

        # Remove background
        no_bg_filename = "no_bg_" + os.path.splitext(filename)[0] + ".png" # Ensure png for transparency
        no_bg_path = os.path.join(app.config['UPLOAD_FOLDER'], no_bg_filename)
        success, message = remove_background_from_image(input_path, no_bg_path)

        if not success:
            return jsonify({"error": f"Failed to remove background: {message}"}), 500
        
        # Get background color
        bg_color = CATEGORY_COLORS.get(category, "white")

        return jsonify({
            "processed_image_url": url_for('uploaded_file', filename=no_bg_filename),
            "processed_filename": no_bg_filename, # Send back the filename for later use
            "background_color": bg_color
        })

def create_badge_image(image_path, name, category, output_path, font_size):
    # Badge dimensions (2x3 inches at 300 dpi)
    width, height = 600, 900
    bg_color = CATEGORY_COLORS.get(category, "white")
    
    badge = Image.new('RGB', (width, height), color=bg_color)
    
    try:
        user_photo = Image.open(image_path)
    except IOError:
        print("Cannot open user photo")
        return

    # Resize photo to fit nicely
    user_photo.thumbnail((700, 700))
    
    img_w, img_h = user_photo.size
    img_pos = ((width - img_w) // 2, height - img_h - 200)
    badge.paste(user_photo, img_pos, user_photo)

    draw = ImageDraw.Draw(badge)
    
    font = None
    font_paths = [
        "/System/Library/Fonts/Arial.ttf", "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "arial.ttf", "C:/Windows/Fonts/arial.ttf"
    ]
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except (IOError, OSError):
            continue
    
    if font is None:
        font = ImageFont.load_default()

    text_color = "white" if bg_color == "black" else "black"
    
    bbox = draw.textbbox((0, 0), name, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    text_pos = ((width - text_w) // 2, height - text_h - 40)
    
    draw.text(text_pos, name, fill=text_color, font=font)
    
    badge.save(output_path, 'jpeg', quality=95, dpi=(300, 300))

@app.route('/generate_final_badge', methods=['POST'])
def generate_final_badge():
    data = request.json
    processed_filename = data['processed_filename']
    name = data['name']
    category = data['category']
    font_size = int(data['font_size'])

    input_path = os.path.join(app.config['UPLOAD_FOLDER'], processed_filename)
    
    final_filename = f"badge_{os.path.splitext(processed_filename)[0]}.jpg"
    output_path = os.path.join(app.config['GENERATED_FOLDER'], final_filename)

    create_badge_image(input_path, name, category, output_path, font_size)

    return send_from_directory(app.config['GENERATED_FOLDER'], final_filename, as_attachment=True)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/generated_badges/<filename>')
def generated_badge(filename):
    return send_from_directory(app.config['GENERATED_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
