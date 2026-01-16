import os
import re
import fitz  # PyMuPDF
import google.generativeai as genai
import streamlit as st
from google.generativeai.types import HarmCategory, HarmBlockThreshold
import dotenv

# --- พยายาม Import Prompt จากไฟล์ภายนอก (ถ้าไม่มีให้ใช้ค่า Default) ---
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

# --- Model Config (Temperature 0 เพื่อความแม่นยำ) ---
generation_config = {
    "temperature": 0.0,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 2048,
    "response_mime_type": "text/plain",
}

SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE
}

# --- CSS ธีมพาสเทล ---
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: linear-gradient(to bottom right, #E0C3FC, #FFD1DC, #BDE0FE);
}
[data-testid="stHeader"] {
    background-color: rgba(0, 0, 0, 0);
}
[data-testid="stSidebar"] {
    background-color: #F3E5F5;
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

# --- ระบบอ่านไฟล์แบบ Hybrid (Cache ไว้จะได้ไม่อ่านใหม่ทุกครั้ง) ---
@st.cache_resource(show_spinner="กำลังอ่านไฟล์ PDF...")
def load_pdf_data_hybrid(file_path):
    text_content = ""
    page_images_map = {} 
    
    if os.path.exists(file_path):
        try:
            doc = fitz.open(file_path)
            
            for i, page in enumerate(doc):
                page_num = i + 1
                text = page.get_text()
                # ใส่ Marker ชัดๆ ให้ AI เห็นเลขหน้า
                text_content += f"\n[--- Page {page_num} START ---]\n{text}\n[--- Page {page_num} END ---]\n"
                
                # 1. ลองตัดรูป (Crop)
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
                            except:
                                pass
                
                # 2. ถ้าไม่มีรูป ให้ Capture ทั้งหน้า
                if not saved_images:
                    pix_full = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    saved_images.append(pix_full.tobytes("png"))

                if saved_images:
                    page_images_map[page_num] = saved_images
                
            return text_content, page_images_map
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return "", {}
    else:
        return "", {}

# --- เรียกใช้งาน ---
pdf_text, pdf_hybrid_images = load_pdf_data_hybrid(pdf_filename)

if not pdf_text:
    st.warning(f"⚠️ ไม่พบไฟล์ {pdf_filename} หรือไฟล์ว่างเปล่า (ตรวจสอบตำแหน่งไฟล์)")
else:
    pass # ไฟล์ปกติ

# --- Prompt (Strict Mode) ---
FULL_SYSTEM_PROMPT = f"""
{PROMPT_WORKAW}

**CRITICAL INSTRUCTIONS FOR ACCURACY:**
1. Use ONLY the information provided in the CONTEXT below. Do NOT use outside knowledge.
2. **Finding the correct Page Number:** - The context is marked with `[--- Page X START ---]` and `[--- Page X END ---]`.
   - When you find the answer text, look immediately ABOVE it to see which "Page START" tag it belongs to.
   - You MUST use that specific Page number.
3. **Citation Format:**
   - At the end of your answer, you MUST append **[PAGE: number]**.
   - Example: "วงล้อสีประกอบด้วย 12 สี [PAGE: 14]"
   - If the answer spans multiple pages, cite the one with the most relevant image or detail.
4. If the answer is not in the context, state: "ขออภัย ไม่มีข้อมูลในเอกสารครับ".

----------------------------------------
CONTEXT (เนื้อหาจากเอกสาร):
{pdf_text}
----------------------------------------
"""

# --- 🔥 ระบบเลือกโมเดล (อัปเดตตามสิทธิ์ User) 🔥 ---
@st.cache_resource(show_spinner="กำลังเชื่อมต่อสมอง AI...")
def setup_gemini_model():
    # รายชื่อโมเดลเรียงตามลำดับความเก่ง (จากลิสต์ที่คุณเช็คมา)
    candidate_models = [
        "gemini-2.5-flash",         # ตัวเทพ ใหม่ล่าสุด
        "gemini-2.0-flash",         # ตัวเสถียร
        "gemini-flash-latest",      # ตัวสำรอง (Auto Update)
        "gemini-2.0-flash-lite"     # ตัวเล็ก เร็ว
    ]

    for model_name in candidate_models:
        try:
            print(f"🔄 กำลังลองเชื่อมต่อ: {model_name}...")
            test_model = genai.GenerativeModel(
                model_name=model_name,
                safety_settings=SAFETY_SETTINGS,
                generation_config=generation_config,
                system_instruction=FULL_SYSTEM_PROMPT
            )
            # Ping Test
            test_model.generate_content("Hi")
            print(f"✅ เชื่อมต่อสำเร็จ! ใช้โมเดล: {model_name}")
            return test_model, model_name
        except Exception as e:
            print(f"❌ {model_name} Error: {e}")
            continue
            
    return None, None

# เรียกใช้ฟังก์ชัน
model, active_model_name = setup_gemini_model()

if model is None:
    st.error("🚨 ไม่สามารถเชื่อมต่อกับ Gemini ได้เลย (กรุณาเช็ค API Key หรือลองใหม่อีกครั้งใน 1 นาที)")
    st.stop()

# --- UI Streamlit ---
def clear_history():
    st.session_state["messages"] = [
        {"role": "model", "content": "สวัสดีค่ะ น้อง Graphic Bot พร้อมให้บริการความรู้เรื่องกราฟิกแล้วค่า 🎨✨"}
    ]
    st.rerun()

with st.sidebar:
    st.success(f"🤖 Connected: {active_model_name}") 
    if st.button("🗑️ ล้างประวัติการคุย"):
        clear_history()

st.title("✨ น้อง Graphic Bot 🎨")

if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {"role": "model", "content": "สวัสดีค่ะ น้อง Graphic Bot พร้อมให้บริการความรู้เรื่องกราฟิกแล้วค่า 🎨✨"}
    ]

# แสดงผลประวัติ
for msg in st.session_state["messages"]:
    avatar_icon = "🐰" if msg["role"] == "user" else "🦄"
    with st.chat_message(msg["role"], avatar=avatar_icon):
        st.write(msg["content"])
        if "image_list" in msg and msg["image_list"]:
             for idx, img_data in enumerate(msg["image_list"]):
                st.image(img_data, caption=f"🖼️ ภาพประกอบจากหน้า {msg.get('page_num_ref')}", use_container_width=True)

# รับข้อความ
if prompt := st.chat_input():
    st.session_state["messages"].append({"role": "user", "content": prompt})
    st.chat_message("user", avatar="🐰").write(prompt)

    def generate_response():
        history_api = [
            {"role": msg["role"], "parts": [{"text": msg["content"]}]}
            for msg in st.session_state["messages"] if "content" in msg
        ]

        try:
            # ย้ำคำสั่งในทุกข้อความ
            strict_prompt = f"{prompt}\n(คำสั่งลับ: ค้นหาคำตอบจาก Context เท่านั้น และต้องระบุเลขหน้า [PAGE: x] ให้ถูกต้อง)"
            
            chat_session = model.start_chat(history=history_api)
            response = chat_session.send_message(strict_prompt)
            response_text = response.text
            
            # ดึงเลขหน้า
            page_match = re.search(r"\[PAGE:\s*(\d+)\]", response_text)
            images_to_show = []
            ref_page_num = None
            p_num = None 
            
            if page_match:
                try:
                    p_num = int(page_match.group(1))
                    ref_page_num = p_num
                    if p_num in pdf_hybrid_images:
                        images_to_show = pdf_hybrid_images[p_num]
                except:
                    pass

            with st.chat_message("model", avatar="🦄"):
                st.write(response_text)
                if images_to_show:
                    for idx, img_data in enumerate(images_to_show):
                        st.image(img_data, caption=f"🖼️ ภาพประกอบจากหน้า {p_num}", use_container_width=True)
            
            msg_data = {"role": "model", "content": response_text}
            if images_to_show:
                msg_data["image_list"] = images_to_show 
                msg_data["page_num_ref"] = ref_page_num
                
            st.session_state["messages"].append(msg_data)

        except Exception as e:
            st.error(f"ระบบขัดข้อง: {e}")

    generate_response()