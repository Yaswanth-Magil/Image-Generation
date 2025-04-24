import base64
import os
import mimetypes
import time
import google.generativeai as genai
from google.generativeai.types import Content, Part
from google.generativeai.types import Image as GenAIImage
from PIL import Image
from io import BytesIO
import pandas as pd
import streamlit as st
import shutil
from tqdm import tqdm

# 🔧 Hardcoded output directories (inside a temp directory for download)
TEMP_DIR = "temp_output"
TOP_VIEW_DIR = os.path.join(TEMP_DIR, "top_view_tool")
FRONT_VIEW_DIR = os.path.join(TEMP_DIR, "front_view_tool")

# API Key (ideally load from secrets in production)
API_KEY = st.secrets.get("GEMINI_API_KEY", "your-fallback-api-key")

# Quota Management
REQUESTS_PER_MINUTE = 10
DELAY_BETWEEN_REQUESTS = 60 / REQUESTS_PER_MINUTE

def save_and_resize_image(file_name, data, size=(1080, 550)):
    image = Image.open(BytesIO(data))
    image = image.resize(size, Image.Resampling.LANCZOS)
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    image.save(file_name)
    print(f"✅ Image saved and resized to {size[0]}x{size[1]} at: {file_name}")

def generate_images(excel_file_content):
    client = genai.Client(api_key=API_KEY)
    model = "gemini-2.0-flash-exp-image-generation"

    generate_content_config = genai.types.GenerateContentConfig(
        response_modalities=["image", "text"],
        response_mime_type="text/plain",
    )

    try:
        df = pd.read_excel(BytesIO(excel_file_content))
        dish_names = df["dishes"].tolist()
        dish_prompts = df["dish prompt"].tolist()
    except KeyError as e:
        st.error(f"Error: Column '{e}' not found in Excel file. Please check your column names.")
        return None
    except Exception as e:
        st.error(f"Error reading Excel file: {e}")
        return None

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
                return True
            except Exception as e:
                st.error(f"Error during generation attempt {attempt + 1}: {e}")
                time.sleep(retry_delay)
                retry_delay *= 2
        return False

    os.makedirs(TOP_VIEW_DIR, exist_ok=True)
    os.makedirs(FRONT_VIEW_DIR, exist_ok=True)

    for dish_name, base_description in tqdm(dishes_data, desc="Generating Images"):
        top_view_filename = os.path.join(TOP_VIEW_DIR, f"{dish_name.replace(' ', '_')}_1")
        contents_top_view = [
            Content(
                role="user",
                parts=[
                    Part.from_text(
                        f"{base_description} Now, show this image from a top-down view, directly above the plate. The plate should be centered and fully visible.")
                ]
            )
        ]
        if not generate_with_backoff(contents_top_view, top_view_filename):
            return None
        time.sleep(DELAY_BETWEEN_REQUESTS)

        front_view_filename = os.path.join(FRONT_VIEW_DIR, f"{dish_name.replace(' ', '_')}_3")
        contents_front_view = [
            Content(
                role="user",
                parts=[
                    Part.from_text(
                        f"{base_description} Now, show this image from a front view, as if someone is sitting at the table looking at the plate.")
                ]
            )
        ]
        if not generate_with_backoff(contents_front_view, front_view_filename):
            return None
        time.sleep(DELAY_BETWEEN_REQUESTS)

    print("Completed image generation.")
    return TEMP_DIR

def zip_and_download(directory):
    shutil.make_archive(directory, 'zip', directory)
    with open(f"{directory}.zip", "rb") as f:
        zip_data = f.read()
    b64 = base64.b64encode(zip_data).decode()
    href = f'<a href="data:file/zip;base64,{b64}" download="{directory}.zip">Download Image Folders</a>'
    return href

st.title("Image Generation from Excel")

uploaded_file = st.file_uploader("Upload your Excel file", type=["xlsx", "xls"])

if uploaded_file is not None:
    if st.button("Generate Images"):
        with st.spinner("Generating images..."):
            output_dir = generate_images(uploaded_file.read())

            if output_dir:
                st.success("Images generated successfully!")
                zip_href = zip_and_download(output_dir)
                st.markdown(zip_href, unsafe_allow_html=True)
            else:
                st.error("Image generation failed. See error messages above.")
