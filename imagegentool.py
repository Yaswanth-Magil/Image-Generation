import base64
import os
import mimetypes
import time
import google
from google import genai
from google.genai import types
from PIL import Image
from io import BytesIO
import pandas as pd
import streamlit as st
import shutil
from tqdm import tqdm  # Import tqdm

# 🔧 Hardcoded output directories (inside a temp directory for download)
TEMP_DIR = "temp_output"  # Create a temporary directory
TOP_VIEW_DIR = os.path.join(TEMP_DIR, "top_view_tool")
FRONT_VIEW_DIR = os.path.join(TEMP_DIR, "front_view_tool")

# API Key (Replace with your actual key, ideally get from Streamlit secrets)
API_KEY = "AIzaSyAxk2Wog2ylp7wuQgTGdQCakzJXMoRHzO8"  # Using Streamlit Secrets

# Quota Management (adjust based on your actual quota)
REQUESTS_PER_MINUTE = 10
DELAY_BETWEEN_REQUESTS = 60 / REQUESTS_PER_MINUTE

def save_and_resize_image(file_name, data, size=(1080, 550)):
    image = Image.open(BytesIO(data))
    image = image.resize(size, Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    image.save(file_name)
    print(f"✅ Image saved and resized to {size[0]}x{size[1]} at: {file_name}")

def generate_images(excel_file_content): # Accept file content directly
    client = genai.Client(api_key=API_KEY)

    model = "gemini-2.0-flash-exp-image-generation"
    generate_content_config = types.GenerateContentConfig(
        response_modalities=["image", "text"],
        response_mime_type="text/plain",
    )

    # Read dishes and prompts from Excel content
    try:
        df = pd.read_excel(BytesIO(excel_file_content))  # Read from the content
        dish_names = df["dishes"].tolist()
        dish_prompts = df["dish prompt"].tolist()
    except KeyError as e:
        st.error(f"Error: Column '{e}' not found in Excel file. Please check your column names.")
        return None  # Indicate failure
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return None #Indicate Failure

    dishes_data = list(zip(dish_names, dish_prompts))

    def generate_with_backoff(contents, file_path):
        max_retries = 10
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                for chunk in client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=generate_content_config,
                ):
                    if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                        continue

                    part = chunk.candidates[0].content.parts[0]
                    if part.inline_data:
                        inline_data = part.inline_data
                        file_extension = mimetypes.guess_extension(inline_data.mime_type)
                        file_name = f"{file_path}{file_extension}"
                        save_and_resize_image(file_name, inline_data.data, size=(1080, 550))
                    else:
                        print("💬 Text response:", chunk.text)
                return True # Indicate Success
            except google.genai.errors.ClientError as e:
                st.error(f"Gemini API ClientError: {e}")  # Display ClientError
                if e.code == 429:
                    retry_info = next((detail for detail in e.details if detail.get('@type') == 'type.googleapis.com/google.rpc.RetryInfo'), None)

                    if retry_info and retry_info.get('retryDelay'):
                        retry_delay = int(retry_info['retryDelay'][:-1])
                        print(f"Rate limited.  Waiting {retry_delay} seconds before retrying.")
                        time.sleep(retry_delay)
                    else:
                        print(f"Attempt {attempt + 1} failed with rate limit error. Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
                else:
                    st.error(f"Failed after {max_retries} attempts. Error: {e}")
                    return False #Indicate Failure
                return False #Indicate Failure
            except google.genai.errors.ServerError as e:
                st.error(f"Gemini API ServerError: {e}")  # Display ServerError
                if e.code == 503 or e.code == 500 and attempt < max_retries - 1:
                    print(f"Attempt {attempt + 1} failed with {e.code} error. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    st.error(f"Failed after {max_retries} attempts. Error: {e}")
                    return False #Indicate Failure
                return False #Indicate Failure
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                return False #Indicate Failure
        return False #Indicate failure because max retries reached.

    # Create output directories
    os.makedirs(TOP_VIEW_DIR, exist_ok=True)
    os.makedirs(FRONT_VIEW_DIR, exist_ok=True)

    # Use tqdm for progress bar
    for dish_name, base_description in tqdm(dishes_data, desc="Generating Images"):
        # Top View
        top_view_filename = os.path.join(TOP_VIEW_DIR, f"{dish_name.replace(' ', '_')}_1")
        contents_top_view = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"{base_description} Now, show this image from a top-down view, directly above the plate. Image should not be too close to the plate, but not too far away either. The plate should be the main focus of the image. The subject should be in the center of the image, do not crop ou the plate, I want entire plate. Do not elonate the subject, I want the subject to be in the center of the image."),
                ],
            ),
        ]
        if not generate_with_backoff(contents_top_view, top_view_filename): #check for failure
            return None

        time.sleep(DELAY_BETWEEN_REQUESTS)

        # Front View
        front_view_filename = os.path.join(FRONT_VIEW_DIR, f"{dish_name.replace(' ', '_')}_3")
        contents_front_view = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=f"{base_description} Now, show this image from a front view, as if someone is sitting at the table looking at the plate. Image should not be too close to the plate, but not too far away either. The plate should be the main focus of the image. The subject should be in the center of the image, do not crop ou the plate, I want entire plate. Do not elonate the subject, I want the subject to be in the center of the image."),
                ],
            ),
        ]
        if not generate_with_backoff(contents_front_view, front_view_filename): #check for failure
            return None
        time.sleep(DELAY_BETWEEN_REQUESTS)

    print("Completed image generation.")
    return TEMP_DIR  # Return the directory containing the images

def zip_and_download(directory):
    """Create a zip archive of a directory and offer it for download."""
    shutil.make_archive(directory, 'zip', directory)
    with open(f"{directory}.zip", "rb") as f:
        zip_data = f.read()
    b64 = base64.b64encode(zip_data).decode()
    href = f'<a href="data:file/zip;base64,{b64}" download="{directory}.zip">Download Image Folders</a>'
    return href

# Streamlit app
st.title("Image Generation from Excel")

uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    if st.button("Generate Images"):
        with st.spinner("Generating images..."):
            output_dir = generate_images(uploaded_file.read())

            if output_dir:
                st.success("Images generated successfully!")

                # Create a download link
                zip_href = zip_and_download(output_dir)
                st.markdown(zip_href, unsafe_allow_html=True)

                # Clean up the temporary directory after the download link is displayed (optional)
                #time.sleep(5)  # Give the user time to click the link
                #shutil.rmtree(output_dir)
                #os.remove(f"{output_dir}.zip")  # Remove the zip file

            else:
                st.error("Image generation failed. See error messages above.")