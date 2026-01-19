import os
import re
import random
import fitz  # PyMuPDF
import google.generativeai as genai
import streamlit as st
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import dotenv

# --- พยายาม Import Prompt จากไฟล์ภายนอก ---
try:
    from prompt import PROMPT_WORKAW
except ImportError:
    PROMPT_WORKAW = "คุณคือผู้ช่วย AI ผู้เชี่ยวชาญด้านกราฟิก ตอบคำถามจากเอกสารที่แนบมาเท่านั้น"

# --- โหลด Config ---
dotenv.load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

if not GOOGLE_API_KEY:
    st.error("❌ ไม่พบ API Key กรุณาตรวจสอบไฟล์ .env")
    st.stop()

genai.configure(api_key=GOOGLE_API_KEY)

# --- Path Config ---
current_dir = os.path.dirname(os.path.abspath(__file__))
pdf_filename = os.path.join(current_dir, "Graphic.pdf")

# --- Model Config ---
generation_config = {
    "temperature": 0.0,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 2048,
    "response_mime_type": "text/plain",
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

# --- 🫧 ฟังก์ชันสร้างฟองอากาศ (One-line HTML) 🫧 ---
def create_bubbles(num_bubbles=20):
    bubbles_html = ""
    for _ in range(num_bubbles):
        left = random.randint(1, 99)      # สุ่มตำแหน่งแนวนอน
        size = random.randint(10, 30)     # สุ่มขนาด
        duration = random.randint(10, 25) # สุ่มความเร็ว
        delay = random.randint(0, 15)     # สุ่มเวลาเริ่ม
        opacity = random.uniform(0.1, 0.4)# สุ่มความจาง
        
        # เขียน HTML เป็นบรรทัดเดียว
        bubbles_html += f'<div class="bubble" style="left: {left}%; width: {size}px; height: {size}px; animation-duration: {duration}s; animation-delay: {delay}s; opacity: {opacity};"></div>'
        
    return bubbles_html

# สร้าง HTML ของฟองอากาศเตรียมไว้
bubbles_html_code = create_bubbles()

# --- 🌊 CSS ธีมท้องทะเล + Gradient Text 🌊 ---
animated_ocean_css = f"""
<style>
/* 1. Animation พื้นหลังไล่สี */
@keyframes gradient_flow {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}

/* 2. Animation ปลาว่ายน้ำ */
@keyframes swim {{
    0% {{ left: -15%; transform: translateY(0px) rotate(0deg); }}
    25% {{ transform: translateY(30px) rotate(5deg); }}
    50% {{ transform: translateY(0px) rotate(0deg); }}
    75% {{ transform: translateY(-30px) rotate(-5deg); }}
    100% {{ left: 110%; transform: translateY(0px) rotate(0deg); }}
}}

/* 3. Animation ฟองอากาศลอยขึ้น */
@keyframes rise {{
    0% {{ bottom: -50px; transform: translateX(0); }}
    50% {{ transform: translateX(20px); }} 
    100% {{ bottom: 110vh; transform: translateX(-20px); }}
}}

/* ปรับแต่ง Container หลัก */
[data-testid="stAppViewContainer"] {{
    background: linear-gradient(-45deg, #00c6fb, #005bea, #00c6fb, #0072ff);
    background-size: 400% 400%;
    animation: gradient_flow 20s ease infinite;
}}

/* ส่วนหัวใส */
[data-testid="stHeader"] {{
    background-color: rgba(0,0,0,0);
}}

/* --- ✨ ตกแต่งหัวข้อ (H1) เป็นสีไล่ระดับโทนเข้มพาสเทล ✨ --- */
h1 {{
    /* กำหนดสีไล่ระดับ: ม่วงเข้มพาสเทล -> น้ำเงินเข้มอมเขียว */
    background: linear-gradient(to right, #7F5A83, #0D324D);
    
    /* เทคนิคทำให้พื้นหลังไปอยู่ในตัวหนังสือ */
    background-clip: text;
    -webkit-background-clip: text;
    color: transparent;
    -webkit-text-fill-color: transparent;
    
    /* เพิ่มความหนาและเงาเล็กน้อยให้ดูมีมิติ */
    font-weight: 900 !important;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.15);
}}

/* Sidebar ใสแบบกระจก */
[data-testid="stSidebar"] {{
    background-color: rgba(255, 255, 255, 0.15);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255,255,255,0.3);
}}

/* Style ของตัวปลา */
.fish-container {{
    position: fixed;
    bottom: 20px;
    z-index: 1;
    font-size: 50px;
    animation: swim 20s linear infinite;
    pointer-events: none;
}}

/* Style ของฟองอากาศ */
.bubble {{
    position: fixed;
    bottom: -50px;
    background: rgba(255, 255, 255, 0.6);
    border-radius: 50%;
    z-index: 0;
    animation: rise infinite ease-in;
    pointer-events: none;
    box-shadow: inset -2px -2px 5px rgba(0,0,0,0.1);
}}
</style>

<div class="fish-container" style="bottom: 10%; animation-duration: 2