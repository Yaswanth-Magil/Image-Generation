import base64
import os
import mimetypes
import time
import google.generativeai as genai
from PIL import Image
from io import BytesIO
import pandas as pd
import streamlit as st
import shutil
from tqdm import tqdm

# Output folders
TEMP_DIR = "temp_output"
TOP_VIEW_DIR = os.path.join(TEMP_DIR, "top_view_tool")
FRONT_VIEW_DIR = os.path.join(TEMP_DIR, "front_view_tool")

# API key is configured as the very first thing
API_KEY = "AIzaSyAxk2Wog2ylp7wuQgTGdQCakzJXMoRHzO8"
genai.configure(api_key=API_KEY)

REQUESTS_PER_MINUTE = 10
DELAY_BETWEEN_REQUESTS = 60 / REQUESTS_PER_MINUTE

def save_and_resize_image(file_name, data, size=(1080, 550)):
    try:
        image = Image.open(BytesIO(data))
        image = image.resize(size, Image.Resampling.LANCZOS)
        os.makedirs(os.path.dirname(file_name), exist_ok=True)
        image.save(file_name)
        print(f"✅ Image saved at {file_name}")
    except Exception as e:
        print(f"❌ Error saving image: {e}")

def generate_images(excel_file_content):
    model = genai.GenerativeModel("gemini-2.0-flash-exp-image-generation")

    try:
        df = pd.read_excel(BytesIO(excel_file_content))
        dishes_data = list(zip(df["dishes"], df["dish prompt"]))
    except KeyError as e:
        st.error(f"Missing column: {e}")
        return None
    except Exception as e:
        st.error(f"Excel read error: {e}")
        return None

    os.makedirs(TOP_VIEW_DIR, exist_ok=True)
    os.makedirs(FRONT_VIEW_DIR, exist_ok=True)

    def generate_and_save(prompt, file_path):
        try:
            response = model.generate_content(
                prompt,  # Pass the prompt directly as a string
                mime_type="image/png" # Specify mime_type as a top-level parameter
            )

            if hasattr(response, 'parts') and response.parts: #Check that parts exits and is not empty
                image_data = response.parts[0].data
                ext = mimetypes.guess_extension("image/png") or ".png"
                save_and_resize_image(file_path + ext, image_data)
                return True
            else:
                st.error(f"Empty response parts for prompt: {prompt}")
                return False
        except Exception as e:
            st.error(f"Error generating image: {e}")
            return False

    for dish_name, base_prompt in tqdm(dishes_data, desc="Generating Images"):
        safe_name = dish_name.replace(" ", "_")

        # Top View Prompt
        top_view_prompt = f"""{base_prompt} Now, show this image from a top-down view. The plate should be centered, not cropped or elongated."""
        if not generate_and_save(top_view_prompt, os.path.join(TOP_VIEW_DIR, f"{safe_name}_top")):
            return None
        time.sleep(DELAY_BETWEEN_REQUESTS)

        # Front View Prompt
        front_view_prompt = f"""{base_prompt} Now, show this image from a front view as if seated at a table. Ensure the entire plate is visible and centered."""
        if not generate_and_save(front_view_prompt, os.path.join(FRONT_VIEW_DIR, f"{safe_name}_front")):
            return None
        time.sleep(DELAY_BETWEEN_REQUESTS)

    return TEMP_DIR

def zip_and_download(directory):
    shutil.make_archive(directory, 'zip', directory)
    with open(f"{directory}.zip", "rb") as f:
        zip_data = f.read()
    b64 = base64.b64encode(zip_data).decode()
    href = f'<a href="data:file/zip;base64,{b64}" download="{directory}.zip">📦 Download All Images</a>'
    return href

# Streamlit App
st.title("🍽️ Gemini Dish Image Generator")

uploaded_file = st.file_uploader("📁 Upload your Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    if st.button("🚀 Generate Images"):
        with st.spinner("🔄 Generating images..."):
            output_dir = generate_images(uploaded_file.read())

            if output_dir:
                st.success("✅ All images generated!")
                st.markdown(zip_and_download(output_dir), unsafe_allow_html=True)
            else:
                st.error("❌ Generation failed. Check logs or Excel file format.")
