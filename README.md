# Image-Generation
It generates the images with excel file.
# 📄 Streamlit Dish Image Generator - CSV Format Guidelines

This Streamlit app is designed to generate dish images based on text prompts from a CSV file.

## 📌 CSV Format Requirement

To ensure the app works correctly, your CSV file **must** contain the following **exact column names**:

| Column Name        | Description                                                 |
|--------------------|-------------------------------------------------------------|
| `dishes`           | The name of the dish (e.g., "Paneer Butter Masala")         |
| `image description`| A textual description of the image to be generated          |
| `dish prompt`      | The actual prompt sent to the image generation model        |

### ✅ Example:

```csv
dishes,image description,dish prompt
Paneer Butter Masala,A creamy tomato-based curry with cubes of paneer,A rich Indian curry with butter and paneer served in a bowl
Idli,A plate of fluffy white idlis with coconut chutney and sambar,South Indian breakfast with soft steamed idlis and colorful sides
