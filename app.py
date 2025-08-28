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

def create_badge_image(image_path, name, category, output_path, font_size):
    # Badge dimensions (2x3 inches at 300 dpi)
    width, height = 600, 900
    bg_color = CATEGORY_COLORS.get(category, "white")

    app.logger.info(f"[create_badge_image] Start: name='{name}', category='{category}', font_size={font_size}")
    
    badge = Image.new('RGB', (width, height), color=bg_color)
    
    try:
        user_photo = Image.open(image_path)
    except IOError:
        app.logger.error("[create_badge_image] Cannot open user photo at %s", image_path)
        return

    # Resize photo to fit nicely
    user_photo.thumbnail((700, 700))
    
    img_w, img_h = user_photo.size
    img_pos = ((width - img_w) // 2, height - img_h - 200)
    badge.paste(user_photo, img_pos, user_photo)

    draw = ImageDraw.Draw(badge)
    
    # Try to load a truetype font, fall back to default with proper size handling
    font = None
    font_paths = [
        "DejaVuSans.ttf",  # Pillow-bundled font, usually available
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "Arial.ttf"),
        "/System/Library/Fonts/Arial.ttf", 
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf"
    ]

    app.logger.info(f"[create_badge_image] Trying font paths in order: {font_paths}")
    
    chosen_font_path = None
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            chosen_font_path = font_path
            app.logger.info(f"[create_badge_image] Using font: {font_path}")
            break
        except (IOError, OSError) as e:
            app.logger.warning(f"[create_badge_image] Failed to load font '{font_path}': {e}")
            continue
    
    # If no truetype font found, create a scaled bitmap font
    if font is None:
        app.logger.warning("[create_badge_image] No truetype font found; falling back to bitmap default font.")
        try:
            default_font = ImageFont.load_default()
            font = default_font
        except Exception as e:
            app.logger.error(f"[create_badge_image] load_default failed: {e}")
            font = ImageFont.load_default()

    text_color = "white" if bg_color == "black" else "black"
    
    # Handle text drawing with proper font size scaling
    try:
        is_ttf = isinstance(font, ImageFont.FreeTypeFont)
    except Exception:
        is_ttf = False

    if is_ttf:
        # This is a truetype font, use it normally
        bbox = draw.textbbox((0, 0), name, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        text_pos = ((width - text_w) // 2, height - text_h - 40)
        app.logger.info(f"[create_badge_image] TTF font bbox={bbox}, text_w={text_w}, text_h={text_h}")
        draw.text(text_pos, name, fill=text_color, font=font)
    else:
        # Fallback: Render with bitmap font, then scale to requested size
        app.logger.info("[create_badge_image] Using bitmap fallback with mask scaling.")
        default_font = font
        # First render at native bitmap size to measure
        temp_img = Image.new('L', (width, height), 0)
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), name, font=default_font)
        native_w = bbox[2] - bbox[0]
        native_h = bbox[3] - bbox[1]
        if native_w <= 0 or native_h <= 0:
            native_w, native_h = 1, 1
        # Create a tight mask at native size
        mask_img = Image.new('L', (native_w, native_h), 0)
        mask_draw = ImageDraw.Draw(mask_img)
        mask_draw.text((0, 0), name, fill=255, font=default_font)
        # Compute scale to target font_size height
        scale = max(1.0, float(font_size) / float(native_h))
        scaled_w = max(1, int(round(native_w * scale)))
        scaled_h = max(1, int(round(native_h * scale)))
        scaled_mask = mask_img.resize((scaled_w, scaled_h), resample=Image.NEAREST)
        # Center horizontally; position 40px from bottom like TTF path
        pos_x = (width - scaled_w) // 2
        pos_y = height - scaled_h - 40
        # Build a colored text image and composite via mask
        color_rgb = (255, 255, 255) if text_color == 'white' else (0, 0, 0)
        text_img = Image.new('RGB', (scaled_w, scaled_h), color_rgb)
        badge.paste(text_img, (pos_x, pos_y), scaled_mask)
        app.logger.info(f"[create_badge_image] Bitmap fallback bbox_native=({native_w}x{native_h}) -> scaled=({scaled_w}x{scaled_h}) at ({pos_x},{pos_y})")

    badge.save(output_path, 'jpeg', quality=95, dpi=(300, 300))
    app.logger.info(f"[create_badge_image] Saved badge to {output_path}. Chosen font: {chosen_font_path or 'bitmap_default'}")

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
