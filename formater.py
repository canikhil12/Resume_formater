import streamlit as st
import docx
from io import BytesIO
import json
from typing import Optional, List
from openai import OpenAI

# ============================================================
#  🔑 OpenAI Client – PUT YOUR REAL API KEY HERE
# ============================================================
client = OpenAI(api_key="your_api_key")


# ============================================================
#  Utility: Replace paragraph text but preserve formatting
# ============================================================
def replace_text_preserve_format(paragraph, new_text: str):
    """
    Replace the text of a paragraph while preserving:
    - Paragraph style
    - Alignment
    - First run font name, size, bold, italic
    """
    original_style = paragraph.style
    original_alignment = paragraph.alignment

    first_run_info = None
    if paragraph.runs:
        r = paragraph.runs[0]
        first_run_info = {
            "font_name": r.font.name,
            "font_size": r.font.size,
            "bold": r.bold,
            "italic": r.italic,
        }

    # Clear all runs
    for run in paragraph.runs:
        run.text = ""

    # Set new text
    paragraph.text = new_text

    # Restore paragraph-level formatting
    paragraph.style = original_style
    paragraph.alignment = original_alignment

    # Restore first-run font formatting
    if paragraph.runs and first_run_info:
        r = paragraph.runs[0]
        if first_run_info["font_name"]:
            r.font.name = first_run_info["font_name"]
        if first_run_info["font_size"]:
            r.font.size = first_run_info["font_size"]
        if first_run_info["bold"] is not None:
            r.bold = first_run_info["bold"]
        if first_run_info["italic"] is not None:
            r.italic = first_run_info["italic"]


# ============================================================
#  JD Keyword Extraction – MULTI-WORD, NO HARDCODED EXAMPLES
# ============================================================
def extract_keywords(jd_text: str) -> List[str]:
    """
    Extract ~15 important technical / domain keywords and key phrases
    directly from the Job Description.

    - Multi-word phrases allowed (cloud platforms, DW concepts, domain terms).
    - Exact phrases as written in the JD.
    - No soft skills or generic verbs.
    """

    prompt = f"""
    Extract the 15 MOST IMPORTANT skill-based and domain-based keywords and key phrases 
    from the following job description.

    REQUIREMENTS:
    - Extract multi-word technical terms and domain concepts (for example: cloud platforms, 
      data warehouse concepts, data validation, domain phrases, methodologies, reporting tools).
    - Extract:
      * technologies
      * tools
      * cloud services
      * data / analytics / BI platforms
      * industry or domain phrases
      * modeling / warehouse / pipeline related phrases
    - Use the EXACT wording found in the job description.
    - Exclude generic words like "analysis", "performance", "team", "collaboration", "communication".
    - Exclude vague soft skills and generic verbs.
    - Output ONLY a JSON object that contains a field called "keywords"
      which is a JSON array of strings. No explanation.

    JOB DESCRIPTION:
    {jd_text}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        temperature=0.0,
    )

    try:
        content = response.choices[0].message.content
        parsed = json.loads(content)

        if isinstance(parsed, list):
            return [k for k in parsed if isinstance(k, str) and k.strip()]

        if isinstance(parsed, dict):
            if "keywords" in parsed and isinstance(parsed["keywords"], list):
                return [k for k in parsed["keywords"] if isinstance(k, str) and k.strip()]
            # Fallback: first list value
            for v in parsed.values():
                if isinstance(v, list):
                    return [k for k in v if isinstance(k, str) and k.strip()]
        return []
    except Exception:
        return []


# ============================================================
#  Section Rewriting with AI (Summary + Bullets)
# ============================================================
def rewrite_with_ai(
    section_text: str,
    jd_text: str,
    section_type: str,
    bullet_count: Optional[int] = None,
    keywords: Optional[List[str]] = None,
) -> str:
    """
    Call OpenAI to rewrite either:
    - Summary (a short block)
    - Bullets (multiple lines, counted)
    """

    keyword_block = ""
    if keywords:
        keyword_block = "\n".join(f"- {kw}" for kw in keywords)

    if section_type == "Summary":
        rules = f"""
        Rewrite the summary into 3 clean, concise lines.

        HARD REQUIREMENTS:
        - The FIRST line MUST begin with exactly:
          "Data Analyst with 5 years of experience"
        - Integrate the job description concepts and the keywords below naturally.
        - Focus on skills and responsibilities clearly present in the job description
          (for example: SQL, Python, some Java, Tableau, AWS, script reviews, controls,
          financial data, reporting, data validation).
        - Do NOT add more than 3 lines.
        - Do NOT return bullet points or markdown.
        - Do NOT introduce technologies, domains, or responsibilities that are not present 
          in either the job description or the existing summary.

        RELEVANT KEYWORDS AND PHRASES (use when appropriate):
        {keyword_block}
        """
    elif section_type == "Bullets":
        rules = f"""
        Rewrite this work experience content into EXACTLY {bullet_count} bullet points.

        HARD REQUIREMENTS FOR BULLETS:
        - Return plain text lines only (NO bullet characters, NO numbering).
        - Produce exactly {bullet_count} lines (no more, no fewer).
        - Each line MUST be a single bullet sentence (no multi-line wrapping in the text).
        - Each bullet MUST:
          * Start with a strong, unique action verb.
          * Include at least one concrete detail (metric, volume, frequency, or impact).
          * Reflect responsibilities and skills from the job description where relevant
            (for example: SQL, Python, Tableau, AWS, script reviews, controls, financial data,
             reporting quality, data validation).
        - You MAY introduce new responsibilities only if they are consistent with the role
          AND clearly implied by the original bullets.
        - You MUST stay truthful to the general nature of the original bullets 
          (data-focused, analytics, reporting, validation, operations).
        - Do NOT introduce unrelated domains or technologies that do NOT appear in the job description
          or the original bullet content.
        - If the job description mentions reviewing scripts (like OE/DE), executing controls,
          or working with financial data, you should reinforce those themes using the existing content.

        RELEVANT KEYWORDS AND PHRASES FROM THE JOB DESCRIPTION:
        {keyword_block}
        """
    else:
        raise ValueError("Unknown section_type")

    prompt = f"""
    You are an expert ATS resume optimization system.

    JOB DESCRIPTION:
    {jd_text}

    CURRENT {section_type.upper()} TEXT:
    {section_text}

    INSTRUCTIONS:
    {rules}

    Return ONLY the rewritten text (no explanations, no extra labels).
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.25,
    )

    raw = response.choices[0].message.content.strip()

    # Cleanup: remove any accidental markdown bullets
    cleaned_lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Remove leading bullet symbols or dashes only at the start of the line
        stripped = stripped.lstrip("•*- \t")
        if stripped:
            cleaned_lines.append(stripped)

    return "\n".join(cleaned_lines)


# ============================================================
#  Dedicated Skills Rewriter – OPTION B (STRICT JD MATCH)
# ============================================================
def rewrite_skills_option_b(original_skills: str, jd_text: str, keywords: List[str]) -> str:
    """
    Rewrite the Technical Skills section with a STRICT JD match (Option B).

    Behavior:
    - Focus on skills that:
      * Explicitly appear in the job description (e.g., SQL, Python, some Java, Tableau, AWS).
      * Are generic core data/analytics / reporting skills (e.g., Excel, BI tools) already in the original skills.
    - Remove advanced / unrelated / niche tools (LLMs, EHR-specific, deep ML, big data, etc.)
      unless they are clearly mentioned in the JD.
    - Only technical skills: no soft skills, responsibilities, or process phrases.
    - Output 1–3 clean comma-separated lines (no bullets, no markdown, no bold markers).
    """

    keyword_block = "\n".join(f"- {kw}" for kw in (keywords or []))

    prompt = f"""
    You are optimizing a Technical Skills section for a Data Analyst resume.

    This is OPTION B: STRICT JD MATCH.

    GOAL:
    - Produce a concise, strictly technical skills section aligned to the job description.
    - Focus on tools, languages, platforms, and technical concepts.
    - Remove skills that are clearly outside what the job description needs.

    SOURCES YOU MAY USE:
    1) Skills explicitly mentioned in the Job Description.
    2) Core data / analytics / reporting / SQL / Python / BI / Excel skills from the original skills text
       that would be useful in almost any Data Analyst role.
    3) Cloud/warehouse platforms ONLY if the job description mentions them
       (e.g., AWS should be included if mentioned).

    DO NOT INCLUDE:
    - Soft skills or responsibilities like "POD deliverables", "report schedules",
      "intake process", "communication", "stakeholder updates".
    - Highly advanced or unrelated tools that are not in the JD, such as:
      deep learning frameworks, LLM tooling, EHR-specific tools,
      or big-data stacks (e.g. Spark, PySpark, Kafka, Hadoop, GPT-4, LangChain, etc.)
      UNLESS they are explicitly mentioned in the Job Description.
    - Domain-specific tools unrelated to the JD.

    FORMAT:
    - Output 1 to 3 lines maximum.
    - Each line is a comma-separated list of skills.
    - No bullets, no markdown, no bold markers, no headings.
    - Example style (DO NOT COPY WORDS, only format):
      SQL, Python, Java, Tableau, AWS, Excel (VLOOKUP, Pivot Tables), Data Validation, Reporting Analysis

    ORIGINAL TECHNICAL SKILLS:
    {original_skills}

    JOB DESCRIPTION:
    {jd_text}

    RELEVANT KEYWORDS FROM JD:
    {keyword_block}
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.15,
    )

    # Ensure plain text without markdown symbols
    raw = response.choices[0].message.content.strip()
    lines = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        stripped = stripped.lstrip("•*- \t")
        lines.append(stripped)

    return "\n".join(lines)


# ============================================================
#  Bullet Extraction – PER JOB, ONLY inside WORK EXPERIENCE
# ============================================================
def extract_work_experience_groups(doc: docx.Document):
    """
    Extract bullet paragraphs PER JOB in the WORK EXPERIENCE section.

    Returns:
        groups: list of dicts:
            {
                "title_para": Paragraph or None,
                "bullet_paragraphs": [Paragraph, ...],
                "bullet_texts": [str, ...]
            }
    """
    groups = []
    current_group = None

    inside_work = False

    SECTION_STARTS = ["WORK EXPERIENCE"]
    SECTION_ENDS = ["EDUCATION", "TECHNICAL SKILLS", "SKILLS", "PROJECTS", "CERTIFICATIONS"]

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    for para in doc.paragraphs:
        raw = para.text.strip()
        if not raw:
            continue

        upper = raw.upper()

        # Detect section start
        if any(upper.startswith(s) for s in SECTION_STARTS):
            inside_work = True
            current_group = None
            continue

        # Detect section end
        if any(upper.startswith(s) for s in SECTION_ENDS):
            inside_work = False
            current_group = None

        if not inside_work:
            continue

        # Normalize bullet markers
        clean = raw.lstrip("•●*- \t").strip()
        if not clean:
            continue

        # Check for job title line: e.g. "Data Analyst | TD Bank"
        is_title_line = "|" in clean and not any(m in clean for m in months) and len(clean.split()) <= 10

        # Date/location line (contains month name)
        is_date_line = any(m in clean for m in months)

        is_heading_style = para.style and para.style.name.lower() in [
            "heading 1", "heading 2", "heading 3", "title", "subtitle"
        ]

        is_all_caps_short = clean.isupper() and len(clean.split()) <= 4

        if is_heading_style or is_all_caps_short:
            # Heading-like, skip as a bullet but keep group context
            continue

        if is_title_line:
            # Start a new job group
            current_group = {
                "title_para": para,
                "bullet_paragraphs": [],
                "bullet_texts": []
            }
            groups.append(current_group)
            continue

        # Skip pure date/location lines
        if is_date_line:
            continue

        # Heuristic: treat as bullet if either started with bullet symbol or has enough words
        if raw[0] in "•●*-" or len(clean.split()) > 4:
            if current_group is None:
                # Bullet without a detected title, attach to a generic group
                current_group = {
                    "title_para": None,
                    "bullet_paragraphs": [],
                    "bullet_texts": []
                }
                groups.append(current_group)

            current_group["bullet_paragraphs"].append(para)
            current_group["bullet_texts"].append(clean)

    return groups


# ============================================================
#  Find Summary Paragraph
# ============================================================
def find_summary_paragraph(doc: docx.Document):
    """
    Locate the main summary paragraph:
    - Search for a heading like "PROFESSIONAL SUMMARY" or "SUMMARY".
    - Use the first non-empty paragraph after that as the summary body.
    """
    for i, para in enumerate(doc.paragraphs):
        txt = para.text.strip().upper()
        if txt in ["PROFESSIONAL SUMMARY", "SUMMARY"]:
            # Next non-empty paragraph is assumed to be the summary body
            for j in range(i + 1, min(i + 8, len(doc.paragraphs))):
                body_para = doc.paragraphs[j]
                if body_para.text.strip():
                    return body_para
            break
    return None


# ============================================================
#  Find Skills Paragraph(s)
# ============================================================
def find_skills_paragraphs(doc: docx.Document):
    """
    Locate the Technical Skills or Skills section body paragraphs.

    Returns:
        list[Paragraph] (could be 1–3 paragraphs under the SKILLS heading)
    """
    skills_paras = []
    inside_skills = False

    for para in doc.paragraphs:
        txt = para.text.strip().upper()

        if txt in ["TECHNICAL SKILLS", "SKILLS"]:
            inside_skills = True
            continue

        if inside_skills:
            # Stop if we hit another major heading
            if txt in ["WORK EXPERIENCE", "EDUCATION", "PROJECTS", "CERTIFICATIONS"]:
                break

            if not para.text.strip():
                # stop on empty line
                break

            skills_paras.append(para)

    return skills_paras


# ============================================================
#  ATS Score Calculation (Upgraded)
# ============================================================
def calculate_ats_score(resume_text: str, keywords: List[str]) -> float:
    """
    Upgraded ATS-style score:

    - 60%: coverage of JD keywords (from extract_keywords)
    - 10%: presence of "data analyst" phrase
    - 10%: presence of "operations" or "analytics" near 'data'
    - 10%: presence of at least one BI/reporting tool (tableau / power bi / bi / dashboard / reporting)
    - 10%: presence of data-quality concepts (validation / quality / integrity / accuracy / consistency)
    """
    text = resume_text.lower()

    # Keyword coverage
    keyword_hits = 0
    for kw in keywords or []:
        if kw.lower() in text:
            keyword_hits += 1
    keyword_score = (keyword_hits / len(keywords) * 60) if keywords else 0

    # Role phrase
    role_score = 10 if "data analyst" in text else 0

    # Operations/analytics context
    ops_score = 0
    if "operations" in text or "operational" in text:
        ops_score += 5
    if "analytics" in text or "analytical" in text:
        ops_score += 5

    # BI / reporting tools
    bi_score = 0
    if "tableau" in text or "power bi" in text or "bi " in text or "dashboard" in text or "reporting" in text:
        bi_score = 10

    # Data quality concepts
    dq_score = 0
    dq_terms = ["data quality", "data validation", "validation", "integrity", "accuracy", "consistency", "spot check"]
    if any(t in text for t in dq_terms):
        dq_score = 10

    total = keyword_score + role_score + ops_score + bi_score + dq_score
    # Cap at 100
    return round(min(total, 100), 2)


# ============================================================
#  Main Transformation: Update Resume
# ============================================================
def update_resume(file, jd_text: str):
    doc = docx.Document(file)

    # 1) Extract prioritized JD keywords
    keywords = extract_keywords(jd_text)
    st.session_state["keywords"] = keywords

    # 2) Rewrite Summary
    summary_para = find_summary_paragraph(doc)
    if summary_para:
        original_summary = summary_para.text
        rewritten_summary = rewrite_with_ai(
            original_summary,
            jd_text,
            section_type="Summary",
            keywords=keywords,
        )
        replace_text_preserve_format(summary_para, rewritten_summary)
    else:
        st.warning("Could not find a 'SUMMARY' or 'PROFESSIONAL SUMMARY' section to rewrite.")

    # 3) Rewrite Work Experience bullets PER JOB
    groups = extract_work_experience_groups(doc)

    any_bullets = False
    for group in groups:
        bullet_paragraphs = group["bullet_paragraphs"]
        bullet_texts = group["bullet_texts"]

        if not bullet_texts:
            continue

        any_bullets = True
        original_bullets_joined = "\n".join(bullet_texts)

        rewritten_bullets_text = rewrite_with_ai(
            original_bullets_joined,
            jd_text,
            section_type="Bullets",
            bullet_count=len(bullet_texts),
            keywords=keywords,
        )

        # Split rewritten text into lines and match count
        new_lines = [l.strip() for l in rewritten_bullets_text.splitlines() if l.strip()]

        # Enforce same count as original bullets
        if len(new_lines) < len(bullet_paragraphs):
            remaining = bullet_texts[len(new_lines):]
            new_lines.extend(remaining)
        if len(new_lines) > len(bullet_paragraphs):
            new_lines = new_lines[:len(bullet_paragraphs)]

        # Apply each new bullet back into the paragraph, re-adding a bullet symbol
        for para, new_line in zip(bullet_paragraphs, new_lines):
            final_text = f"• {new_line}"
            replace_text_preserve_format(para, final_text)

    if not any_bullets:
        st.warning("No work experience bullet points were detected for rewriting.")

    # 4) Rewrite Skills – STRICT JD MATCH (Option B)
    skills_paras = find_skills_paragraphs(doc)
    if skills_paras:
        original_skills_text = " ".join(p.text.strip() for p in skills_paras if p.text.strip())
        if original_skills_text:
            rewritten_skills = rewrite_skills_option_b(
                original_skills_text,
                jd_text,
                keywords,
            )
            # Apply rewritten skills to the FIRST skills paragraph, clear others
            first_para = skills_paras[0]
            replace_text_preserve_format(first_para, rewritten_skills)

            # ENSURE NO BOLD IN SKILLS SECTION
            for run in first_para.runs:
                run.bold = False

            for para in skills_paras[1:]:
                replace_text_preserve_format(para, "")
                for run in para.runs:
                    run.bold = False
    else:
        st.info("No explicit TECHNICAL SKILLS / SKILLS section body found to rewrite.")

    # 5) Save to BytesIO
    output = BytesIO()
    doc.save(output)
    output.seek(0)
    return output


# ============================================================
#  STREAMLIT APP
# ============================================================
st.title("📄 AI Resume Optimizer – Summary + Work Experience + Skills (Strict JD Match)")

st.markdown(
    """
Upload your **.docx resume** and paste a **Job Description**.
This app will:

- Rewrite your **Professional Summary** (starting with 5 years of experience).
- Rewrite your **Work Experience bullet points per job** to match the JD.
- Rewrite your **Skills** section with a strict JD match (Option B: remove unrelated tech).
- Preserve your formatting and bullet count as much as possible.
- Show extracted **JD Keywords** and an upgraded **ATS Match Score**.
"""
)

uploaded_file = st.file_uploader("Upload your resume (.docx)", type=["docx"])
jd_text = st.text_area("Paste Job Description here", height=260)

if uploaded_file and jd_text:
    if st.button("Optimize Resume", type="primary", use_container_width=True):
        optimized_buffer = update_resume(uploaded_file, jd_text)

        st.success("✅ Optimization complete! Summary, Work Experience bullets, and Skills have been updated.")

        # Download button
        st.download_button(
            "📥 Download Optimized Resume",
            data=optimized_buffer,
            file_name="Resume_Optimized_Targeted.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True,
        )

        # Reload the optimized doc from buffer for ATS scoring
        optimized_doc = docx.Document(optimized_buffer)
        full_text = " ".join(p.text for p in optimized_doc.paragraphs)

        # ATS Score (upgraded)
        ats_score = calculate_ats_score(full_text, st.session_state.get("keywords", []))
        st.session_state["ats_score"] = ats_score

        st.subheader("📊 ATS Match Score")
        st.metric(label="Estimated JD Match", value=f"{ats_score}%")

        # Show extracted keywords
        st.subheader("🔑 Extracted JD Keywords")
        if st.session_state.get("keywords"):
            st.code(", ".join(st.session_state["keywords"]), language="text")
        else:
            st.info("No keywords extracted. Check the job description text and try again.")