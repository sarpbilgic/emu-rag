import requests
from bs4 import BeautifulSoup
import html2text
import os
import time
from urllib.parse import urljoin


BASE_URL = "https://mevzuat.emu.edu.tr/"

LINKS = [
    "1-Statute-EmuStatute.pdf",
    "3-1_YabDilIngHzrOkul_en.htm",
    "5-1-0-Regulation-Education_Examination_Success.htm",
    "5-1-1-Rules-Entrance_exam.htm",
    "5-1-2-Rules-Scholarship_regulations.htm",
    "5-1-3-Rules-Vertical_transfer.htm",
    "5-1-4-Rules-examinations_and_evaluations.htm",
    "5-1-5-Rules-Course_Registration.htm",
    "5-1-6-Rules-Taking_courses_outside_the_university.htm",
    "5-1-7-Rules-Doublemajorprgs.htm",
    "5-1-8-Rules-Minorbylaw.htm",
    "5-1-9-Regulations%20for%20Summer%20Semester.htm",
    "5-1-10-Regulations-RegulationsforTutionFees.htm",
    "5-2-0-Rules-student_disciplinary.htm",
    "5-4-1-Rules-GraduateRegistrationandAdmissions.htm",
    "5-5-Disabled_Std_Principles.htm",
    "8_1_0_RegulationsPrinciplesStudentDormitories.htm",
    "REGULATIONS%20FOR%20BENEFITING%20FROM%20UNIVERSITY%20HOUSING%20AND%20GUEST%20HOUSE%20FACILITIES%20.htm"
]

# 2. Setup Markdown Converter
converter = html2text.HTML2Text()
converter.ignore_links = False
converter.body_width = 0  # Prevents mid-sentence line breaks
converter.tables = True   # Critical for Grade and GPA tables

os.makedirs("emu_rag_data", exist_ok=True)

def scrape_clean():
    for link in LINKS:
        full_url = urljoin(BASE_URL, link)
        file_name = link.replace('.htm', '.md').replace('%20', '_')
        
        print(f"Processing: {link}...")
        
        try:
            response = requests.get(full_url)
            # Fix Turkish Character Corruption
            response.encoding = 'windows-1254' 
            
            if link.endswith('.pdf'):
                # Save PDFs as-is (Use a PDF loader in your RAG later)
                with open(os.path.join("emu_rag_data", link), "wb") as f:
                    f.write(response.content)
            else:
                # Clean HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Remove MS Word specific junk and script tags
                for element in soup(["script", "style", "meta", "link", "o:p"]):
                    element.decompose()
                
                # Convert to structured Markdown
                markdown_text = converter.handle(str(soup))
                
                with open(os.path.join("emu_rag_data", file_name), "w", encoding="utf-8") as f:
                    f.write(markdown_text)
                    
            time.sleep(1) # Respectful delay
            
        except Exception as e:
            print(f"Error on {link}: {e}")

if __name__ == "__main__":
    scrape_clean()
    print("\nSuccess! Your RAG-ready files are in the 'emu_rag_data' folder.")