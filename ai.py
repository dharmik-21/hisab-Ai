import pytesseract
import cv2
import numpy as np
from PIL import Image
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\barot\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"


# OCR
def extract_text(file):
    img = np.array(Image.open(file))

    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5,5), 0)

    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )

    text = pytesseract.image_to_string(thresh, config="--psm 6")
    return text


# Extract items
def extract_items(text):
    import re

    lines = text.split("\n")
    items = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # detect negative numbers also
        nums = re.findall(r'-?\d+', line)

        if nums:
            price = int(nums[-1])  # last number

            name = re.sub(r'[^A-Za-z ]', '', line).strip()

            if len(name) > 2:
                items.append({
                    "name": name,
                    "price": price
                })

    return items


# Calculate totals
def calculate_totals(items):
    total = sum(item["price"] for item in items)

    # GST only on positive sales
    positive_total = sum(i["price"] for i in items if i["price"] > 0)

    subtotal = positive_total / 1.18
    gst = positive_total - subtotal

    return {
        "subtotal": round(subtotal,2),
        "gst": round(gst,2),
        "cgst": round(gst/2,2),
        "sgst": round(gst/2,2),
        "total": round(total,2)   # includes negative
    }
    