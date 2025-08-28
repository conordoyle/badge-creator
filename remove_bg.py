import requests
import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file for standalone script usage

# --- Configuration ---
# ⚠️ Replace "YOUR_API_KEY" with your actual API key.
API_KEY = "replace" 
# The image you want to process.
INPUT_IMAGE_PATH = "my_image.jpg"
# The name for the output image with the transparent background.
OUTPUT_IMAGE_PATH = "my_image_no_bg.png"

# The API endpoint URL.
API_ENDPOINT = "https://api.withoutbg.com/v1.0/image-without-background"

def remove_background_from_image(input_path, output_path):
    """
    Sends an image to the withoutbg.com API to remove its background
    and saves the resulting image.
    """
    API_KEY = os.environ.get("WITHOUTBG_API_KEY") # It's better to use environment variables for API keys
    API_ENDPOINT = "https://api.withoutbg.com/v1.0/image-without-background"
    
    if not API_KEY or API_KEY == "replace":
        print("🚨 Please set the WITHOUTBG_API_KEY environment variable in your .env file.")
        return False, "API Key not set."

    # Check if the input image file exists.
    if not os.path.exists(input_path):
        print(f"❌ Error: Input file not found at '{input_path}'")
        return False, f"Input file not found at '{input_path}'"

    print(f"Processing '{input_path}'...")

    # Open the image file in binary read mode.
    with open(input_path, 'rb') as image_file:
        # Prepare the request headers with your API key.
        headers = {
            "X-Api-Key": API_KEY
        }

        # Prepare the file for multipart/form-data upload.
        # The API error message specifies the field name must be 'file'.
        files = {
            "file": (os.path.basename(input_path), image_file)
        }
        
        # Send the POST request to the API.
        try:
            response = requests.post(API_ENDPOINT, headers=headers, files=files, timeout=30)

            # Check if the request was successful (HTTP status code 200).
            if response.status_code == 200:
                # Save the returned image data to the output file.
                with open(output_path, 'wb') as out_file:
                    out_file.write(response.content)
                print(f"✅ Success! Background removed image saved as '{output_path}'")
                return True, "Background removed successfully."
            else:
                # Print an error message if the request failed.
                print(f"❌ Error: API request failed with status code {response.status_code}")
                print(f"   Response: {response.text}")
                return False, f"API request failed with status code {response.status_code}"

        except requests.exceptions.RequestException as e:
            print(f"❌ Error: An issue occurred with the network request: {e}")
            return False, f"An issue occurred with the network request: {e}"


if __name__ == "__main__":
    # Example usage:
    # Make sure to set your API key in a .env file:
    # WITHOUTBG_API_KEY='your_api_key'
    if os.environ.get("WITHOUTBG_API_KEY"):
        # Create a dummy image for testing if it doesn't exist
        if not os.path.exists("my_image.jpg"):
            from PIL import Image
            img = Image.new('RGB', (100, 100), color = 'red')
            img.save('my_image.jpg')

        success, message = remove_background_from_image("my_image.jpg", "my_image_no_bg.png")
        if not success:
            print(message)
    else:
        print("🚨 Please set the WITHOUTBG_API_KEY environment variable in your .env file to run this example.")