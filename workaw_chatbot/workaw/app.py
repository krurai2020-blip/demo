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

# --- 🫧 ฟังก์ชันสร้างฟองอากาศ ---
def create_bubbles(num_bubbles=20):
    bubbles_html = ""
    for _ in range(num_bubbles):
        left = random.randint(1, 99)      
        size = random.randint(10, 30)     
        duration = random.randint(15, 30) # ปรับให้ช้าลงเล็กน้อยให้เข้ากับพาสเทล
        delay = random.randint(0, 15)     
        opacity = random.uniform(0.2, 0.5)# เพิ่มความชัดของฟองนิดนึงบนพื้นหลังสว่าง
        
        bubbles_html += f'<div class="bubble" style="left: {left}%; width: {size}px; height: {size}px; animation-duration: {duration}s; animation-delay: {delay}s; opacity: {opacity};"></div>'
        
    return bubbles_html

bubbles_html_code = create_bubbles()

# --- 🦄 CSS ธีม Pastel Ocean Dream (ม่วง-ชมพู-ฟ้า) 🦄 ---
animated_ocean_css = f"""
<style>
/* 1. Animation พื้นหลังไล่สี (Gradient Flow) */
@keyframes gradient_flow {{
    0% {{ background-position: 0% 50%; }}
    50% {{ background-position: 100% 50%; }}
    100% {{ background-position: 0% 50%; }}
}}

/* 2. Animation ปลาว่ายน้ำ */
@keyframes swim {{
    0% {{ left: -15%; transform: translateY(0px) rotate(0deg); }}
    25% {{ transform: translateY(20px) rotate(5deg); }}
    50% {{ transform: translateY(0px) rotate(0deg); }}
    75% {{ transform: translateY(-20px) rotate(-5deg); }}
    100% {{ left: 110%; transform: translateY(0px) rotate(0deg); }}
}}

/* 3. Animation ฟองอากาศลอยขึ้น */
@keyframes rise {{
    0% {{ bottom: -50px; transform: translateX(0); }}
    50% {{ transform: translateX(15px); }} 
    100% {{ bottom: 110vh; transform: translateX(-15px); }}
}}

/* ปรับแต่ง Container หลัก: Gradient ม่วง-ชมพู-ฟ้า พาสเทล */
[data-testid="stAppViewContainer"] {{
    /* สี: ม่วงอ่อน -> ชมพูนม -> ฟ้าเบบี้บลู -> ม่วงคราม */
    background: linear-gradient(-45deg, #e0c3fc, #ffdee9, #b5fffc, #8ec5fc, #c2e9fb);
    background-size: 400% 400%;
    animation: gradient_flow 15s ease infinite;
}}

/* ส่วนหัวใส */
[data-testid="stHeader"] {{
    background-color: rgba(0,0,0,0);
}}

/* Sidebar สีขาวขุ่น (Milky Glass) เพื่อให้อ่านง่ายบนพาสเทล */
[data-testid="stSidebar"] {{
    background-color: rgba(255, 255, 255, 0.4);
    backdrop-filter: blur(15px);
    border-right: 1px solid rgba(255,255,255,0.6);
    box-shadow: 5px 0 15px rgba(224, 195, 252, 0.1);
}}

/* ปรับสี Text ใน Sidebar ให้ดูนุ่มนวล */
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span {{
    color: #5a4b6e !important; /* สีม่วงเทาเข้ม */
}}

/* Style ของตัวปลา */
.fish-container {{
    position: fixed;
    bottom: 20px;
    z-index: 1; 
    font-size: 50px;
    animation: swim 25s linear infinite;
    pointer-events: none;
    opacity: 0.9;
    filter: saturate(1.2); /* เร่งสีปลาให้สดขึ้นนิดนึงตัดกับพาสเทล */
}}

/* Style ของฟองอากาศ - สีขาวมุก */
.bubble {{
    position: fixed;
    bottom: -50px;
    background: radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.4));
    border-radius: 50%;
    z-index: 0;
    animation: rise infinite ease-in;
    pointer-events: none;
    box-shadow: 0px 0px 10px rgba(255, 255, 255, 0.5);
}}
</style>

<div class="fish-container" style="bottom: 15%; animation-duration: 28s;">🐠</div>
<div class="fish-container" style="bottom: 35%; animation-duration: 20s; animation-delay: 5s; font-size: 30px;">🐡</div>
<div class="fish-container" style="bottom: 65%; animation-duration: 38s; animation-delay: 2s; font-size: 60px;">🐬</div>
<div class="fish-container" style="bottom: 85%; animation-duration: 45s; animation-delay: 10s; font-size: 25px;">🦑</div>

{bubbles_html_code}
"""
st.markdown(animated_ocean_css, unsafe_allow_html=True)

# --- ระบบอ่านไฟล์แบบ Hybrid (เหมือนเดิม) ---
@st.cache_resource(show_spinner="กำลังดำน้ำหาข้อมูลในไฟล์ PDF... 🤿")
def load_pdf_data_hybrid(file_path):
    text_content = ""
    page_images_map = {} 
    
    if os.path.exists(file_path):
        try:
            doc = fitz.open(file_path)
            for i, page in enumerate(doc):
                page_num = i + 1
                text = page.get_text()
                text_content += f"\n[--- Page {page_num} START ---]\n{text}\n[--- Page {page_num} END ---]\n"
                
                # Crop Image Logic
                image_blocks = [b for b in page.get_text("blocks") if b[6] == 1]
                saved_images = []
                if image_blocks:
                    for img_block in image_blocks:
                        rect = fitz.Rect(img_block[:4])
                        if rect.width > 50 and rect.height > 50: 
                            rect.x0 -= 5; rect.y0 -= 5; rect.x1 += 5; rect.y1 += 5
                            try:
                                pix_crop = page.get_pixmap(matrix=fitz.Matrix(3, 3), clip=rect)
                                saved_images.append(pix_crop.tobytes("png"))
                            except: pass
                
                if not saved_images:
                    pix_full = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    saved_images.append(pix_full.tobytes("png"))

                if saved_images:
                    page_images_map[page_num] = saved_images
            return text_content, page_images_map
        except Exception as e:
            print(f"Error: {e}")
            return "", {}
    else:
        return "", {}

pdf_text, pdf_hybrid_images = load_pdf_data_hybrid(pdf_filename)

if not pdf_text:
    st.warning(f"⚠️ ไม่พบไฟล์ {pdf_filename} กรุณาตรวจสอบว่ามีไฟล์ Graphic.pdf อยู่ในโฟลเดอร์เดียวกับโค้ด")

# --- Prompt System ---
FULL_SYSTEM_PROMPT = f"""
1. **DO NOT use your own knowledge.** (ห้ามใช้ความรู้ส่วนตัวของคุณเด็ดขาด)
2. **Answer ONLY from the 'CONTEXT INFORMATION'.** (ตอบโดยอ้างอิงจากข้อมูลที่ให้ไปเท่านั้น)
3. **If the answer is NOT in the context:** (ถ้าหาคำตอบในข้อมูลที่ให้ไม่เจอ)
   - You MUST reply: "ขออภัยค่ะ ไม่มีข้อมูลเรื่องนี้ในเอกสารแนบค่ะ 🥺"
   - Do NOT try to make up an answer. (ห้ามพยายามแต่งคำตอบขึ้นมาเอง)
- You MUST cite the page number at the end of the answer.
- FORMAT: Use exactly this format: [PAGE: number]
- Example: "จิตวิทยาของสีคือ... [PAGE: 12]"
SPECIAL INSTRUCTIONS:
- **Language:** Use clear and easy-to-understand Thai language.
- **Format:** Format your answers with bullet points or numbered lists where appropriate.
- **Tone:** Friendly, cheerful, and cute (Pastel theme). ตอบด้วยน้ำเสียงสดใส น่ารัก เป็นกันเอง
- **Emoji Usage:** Use cute emojis in your response to make it lively. ใส่อิโมจิน่ารักๆ ประกอบคำตอบเสมอ เช่น:
    - หมวดศิลปะ/กราฟิก: 🎨 🖌️ ✏️ 📐 💻 🖥️ 🖼️ ✨
    - หมวดน่ารัก/สัตว์: 🐰 🐱 🐻 🦄 🐥 🧸 🦋 🌸
    - หมวดหัวใจ/สี: 💖 💜 💙 🤍 🌈 🍭 🍬 🎀

[CONTEXT]:
{pdf_text}
"""

# --- 🔥 ฟังก์ชันเช็ค Error (Debug Mode)  🔥 ---
@st.cache_resource(show_spinner="กำลังเชื่อมต่อสมอง AI...")
def setup_gemini_model():
    # รายชื่อโมเดลตามที่คุณเช็คสิทธิ์มา
    candidate_models = [
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-flash-latest"
    ]  
    error_logs = [] # เก็บ Error ไว้โชว์
    for model_name in candidate_models:
        try:
            # สร้าง Object โมเดล (ยังไม่ใส่ System Prompt ตอนเทส เพื่อลดภาระ)
            test_model = genai.GenerativeModel(
                model_name=model_name,
                safety_settings=SAFETY_SETTINGS,
                generation_config=generation_config            )
            # Ping Test: ส่งข้อความสั้นๆ
            test_model.generate_content("Hi")           
            # ถ้าผ่าน ให้สร้างโมเดลตัวจริงพร้อม System Prompt
            real_model = genai.GenerativeModel(
                model_name=model_name,
                safety_settings=SAFETY_SETTINGS,
                generation_config=generation_config,
                system_instruction=FULL_SYSTEM_PROMPT
            )           
            return real_model, model_name  
        except Exception as e:
            # เก็บข้อความ Error ไว้
            error_msg = f"❌ {model_name}: {str(e)}"
            print(error_msg)
            error_logs.append(error_msg)
            continue 
    # ถ้าหลุดมาถึงตรงนี้ แสดงว่าพังหมด ให้โชว์ Error บนหน้าจอแอปเลย
    st.error("⚠️ เชื่อมต่อไม่ได้ ดูรายละเอียดด้านล่าง:")
    for err in error_logs:
        st.code(err, language='text') # โชว์ Error ให้เห็นชัดๆ    
    return None, None

# เรียกใช้ฟังก์ชัน
model, active_model_name = setup_gemini_model()

if model is None:
    st.error("🚨 ไม่สามารถเชื่อมต่อกับ Gemini ได้เลย (กรุณาเช็ค API Key หรือลองใหม่อีกครั้งใน 1 นาที)")
    st.stop()

# --- UI & Chat Logic ---
def clear_history():
    st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมา AI พร้อมให้บริการแล้วค่า 🐬"}]
    st.rerun()

with st.sidebar:
    st.success(f"⚓ Connected: {active_model_name}")
    if st.button("🗑️ ล้างประวัติ"): clear_history()

st.title("✨ น้องโลมา Graphic Bot 🐬🫧")

if "messages" not in st.session_state:
    st.session_state["messages"] = [{"role": "model", "content": "บุ๋งๆๆ 🫧 สวัสดีค่ะ น้องโลมา AI พร้อมให้บริการแล้วค่า 🐬"}]

# แสดงประวัติการแชท
for msg in st.session_state["messages"]:
    avatar_icon = "🐠" if msg["role"] == "user" else "🐬"
    with st.chat_message(msg["role"], avatar=avatar_icon):
        st.write(msg["content"])
        if "image_list" in msg:
             for img_data in msg["image_list"]:
                st.image(img_data, caption=f"🖼️ ภาพประกอบจากหน้า {msg.get('page_num_ref')}", use_container_width=True)

# ช่องรับข้อความ
if prompt := st.chat_input("พิมพ์คำถามที่นี่..."):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    st.chat_message("user", avatar="🐠").write(prompt)

    try:
        history_api = [{"role": m["role"], "parts": [{"text": m["content"]}]} for m in st.session_state["messages"] if "content" in m]
        strict_prompt = f"{prompt}\n(คำสั่งลับ: ค้นหาคำตอบจาก Context เท่านั้น และระบุเลขหน้า [PAGE: x])"
        
        response = model.start_chat(history=history_api).send_message(strict_prompt)
        response_text = response.text
        
        # Extract Images
        page_match = re.search(r"\[PAGE:\s*(\d+)\]", response_text)
        images_to_show = []
        p_num = None
        if page_match:
            try:
                p_num = int(page_match.group(1))
                if p_num in pdf_hybrid_images: images_to_show = pdf_hybrid_images[p_num]
            except: pass

        with st.chat_message("model", avatar="🐬"):
            st.write(response_text)
            if images_to_show:
                for img in images_to_show: st.image(img, caption=f"หน้า {p_num}", use_container_width=True)
        
        msg_data = {"role": "model", "content": response_text}
        if images_to_show:
            msg_data["image_list"] = images_to_show
            msg_data["page_num_ref"] = p_num
        st.session_state["messages"].append(msg_data)

    except Exception as e:
        st.error(f"Error: {e}")