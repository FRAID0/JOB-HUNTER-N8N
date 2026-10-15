# 📂 Candidate Document Hub (`documents/`)

Place your application documents in **PDF format** inside this directory. The automated **Playwright Browser Agent** (`copilot_apply.py`) and **DocumentHub** will automatically index, categorize, and upload the appropriate files when completing online application forms.

---

## 📋 Recommended Document File Names

The intelligent `DocumentHub` scanner inspects file names and automatically maps them to the corresponding fields on ATS portals (e.g. Personio, Workday, Greenhouse, Lever, SAP SuccessFactors):

| Document Type | Purpose / Description | Recommended File Name | Recognized Keywords |
| :--- | :--- | :--- | :--- |
| **Curriculum Vitae (Resume)** | Your updated CV / Lebenslauf | `cv.pdf` | `cv`, `lebenslauf`, `resume` |
| **Cover Letter** | DIN 5008 tailored cover letter *(auto-generated or custom)* | `anschreiben.pdf` | `anschreiben`, `cover`, `motivation` |
| **Academic Transcript** | Transcript of Records / Official grades | `notenspiegel.pdf` | `notenspiegel`, `transcript`, `grades` |
| **Certificate of Enrollment** | Current university enrollment certificate *(students)* | `immatrikulationsbescheinigung.pdf` | `immatrikulation`, `studienbescheinigung`, `student` |
| **Work / Internship References** | Employment references, certificates, or recommendation letters | `arbeitszeugnis.pdf` | `arbeitszeugnis`, `praktikumszeugnis`, `zeugnis`, `reference` |
| **Work Permit / Residence** | Work authorization or residency documentation *(if applicable)* | `aufenthaltstitel.pdf` | `aufenthaltstitel`, `visa`, `work_permit` |

---

## 🤖 How Document Resolution Works

1. **Semantic Categorization**: When an online job portal requests an attachment (e.g., *"Upload Lebenslauf"* vs *"Zeugnisse / Certificates"*), the **DocumentHub** engine detects the field context using DOM accessibility attributes and labels.
2. **Strict Slot Isolation**: A resume is never uploaded into a certificates slot, and vice versa.
3. **Automated DIN 5008 Generation**: If a specific job posting requires a customized German cover letter, the AI generates a DIN 5008 formatted PDF directly as `documents/anschreiben.pdf` before the application starts.

---

## 🔒 Privacy & Git Safety

> [!NOTE]
> All personal PDF files inside this directory (`documents/*.pdf`) are **strictly excluded by `.gitignore`**. Your personal files, diplomas, and sensitive data will **never** be committed or pushed to any public Git repository.
