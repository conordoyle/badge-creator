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

def load_font(font_size):
    """Load a TrueType font with proper fallback handling."""
    # Try bundled fonts first (most reliable)
    bundled_font_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans-Bold.ttf"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "DejaVuSans.ttf"),
    ]
    
    # System fonts as fallback
    system_font_paths = [
        "/System/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc", 
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf"
    ]
    
    all_font_paths = bundled_font_paths + system_font_paths
    
    app.logger.info(f"[load_font] Attempting to load font with size {font_size}")
    
    for font_path in all_font_paths:
        try:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
                app.logger.info(f"[load_font] Successfully loaded: {font_path}")
                return font, font_path
            else:
                app.logger.debug(f"[load_font] Font not found: {font_path}")
        except (IOError, OSError) as e:
            app.logger.warning(f"[load_font] Failed to load font '{font_path}': {e}")
            continue
    
    # If all TrueType fonts fail, use default but log warning
    app.logger.error("[load_font] All TrueType fonts failed, using default font")
    return ImageFont.load_default(), "default_bitmap"

def create_badge_image(image_path, name, category, output_path, font_size):
    """Create a badge image with improved font handling and consistent sizing."""
    # Badge dimensions (2x3 inches at 300 dpi)
    width, height = 600, 900
    bg_color = CATEGORY_COLORS.get(category, "white")

    app.logger.info(f"[create_badge_image] Creating badge: name='{name}', category='{category}', font_size={font_size}")
    
    # Create badge background
    badge = Image.new('RGB', (width, height), color=bg_color)
    
    # Load and process user photo
    try:
        user_photo = Image.open(image_path)
        # Convert to RGBA to handle transparency properly
        if user_photo.mode != 'RGBA':
            user_photo = user_photo.convert('RGBA')
    except IOError:
        app.logger.error(f"[create_badge_image] Cannot open user photo at {image_path}")
        return

    # Resize photo to fit nicely (preserve aspect ratio)
    max_photo_size = 750  # Larger photo for better visibility
    user_photo.thumbnail((max_photo_size, max_photo_size), Image.Resampling.LANCZOS)
    
    # Center the photo horizontally and position it in the upper portion
    img_w, img_h = user_photo.size
    img_x = (width - img_w) // 2
    img_y = 0  # Fixed position from top
    
    # Paste the photo (handle transparency)
    if user_photo.mode == 'RGBA':
        badge.paste(user_photo, (img_x, img_y), user_photo)
    else:
        badge.paste(user_photo, (img_x, img_y))

    # Draw text
    draw = ImageDraw.Draw(badge)
    
    # Load font with proper size
    font, font_path = load_font(font_size)
    
    # Determine text color based on background
    text_color = "white" if bg_color.lower() == "black" else "black"
    
    # Calculate text positioning
    # Use textbbox for accurate text measurements
    try:
        bbox = draw.textbbox((0, 0), name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except:
        # Fallback if textbbox fails
        text_w, text_h = draw.textsize(name, font=font)
    
    # Center text horizontally and position near bottom
    text_x = (width - text_w) // 2
    text_y = height - text_h - 60  # 60px from bottom
    
    # Draw text with slight outline for better visibility
    outline_color = "black" if text_color == "white" else "white"
    
    # Draw text outline (optional, for better readability)
    outline_width = 1
    for adj_x in range(-outline_width, outline_width + 1):
        for adj_y in range(-outline_width, outline_width + 1):
            if adj_x != 0 or adj_y != 0:
                draw.text((text_x + adj_x, text_y + adj_y), name, fill=outline_color, font=font)
    
    # Draw main text
    draw.text((text_x, text_y), name, fill=text_color, font=font)
    
    # Save with high quality
    badge.save(output_path, 'JPEG', quality=95, dpi=(300, 300))
    app.logger.info(f"[create_badge_image] Badge saved to {output_path} using font: {font_path}")
    app.logger.info(f"[create_badge_image] Text dimensions: {text_w}x{text_h} at position ({text_x}, {text_y})")

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
    # Bind to PORT if defined, otherwise default to 5000.
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
