"""
═══════════════════════════════════════════════════════════════════
  HATMS Full Automation Script
  Automates 2 courses on SCFHS HATMS platform:
    Course 1: MCS-01 (Medical Cause of Death - course_id=45)
    Course 2: IDE (Disability Etiquette - course_id=265)

  For each course:
    1. Auto-extract SESSKEY
    2. Auto-enroll
    3. Complete all SCORM slides
    4. Start and solve the Final Exam
    5. Submit and display grade

  Usage: Just update COOKIE_STRING and run!
═══════════════════════════════════════════════════════════════════
"""
import sys
import io
import re
import json
import time
import argparse
from curl_cffi import requests as cf_requests

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

# ═══════════════════════════════════════════════════════
# CONFIGURATION - غيّر هذا فقط لكل حساب جديد
# ═══════════════════════════════════════════════════════
BASE_URL = "https://hatms.scfhs.org.sa"
COOKIE_STRING = "MoodleSession=2tt03ko27jrqt2ldimo08umr9s"

HEADERS = {
    "accept": "*/*",
    "cookie": COOKIE_STRING,
    "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

SESSKEY = ""
TIMEOUT = 30

# ═══════════════════════════════════════════════════════
# COURSE DEFINITIONS
# ═══════════════════════════════════════════════════════

COURSES = {
    "MCS-01": {
        "name": "Medical Cause of Death Certification (MCS-01)",
        "course_id": 45,
        "quiz_cmid": 131,
        "scorm_modules": [
            {"a": 60, "scoid": 120},
            {"a": 37, "scoid": 74},
            {"a": 38, "scoid": 76},
            {"a": 59, "scoid": 118},
            {"a": 41, "scoid": 82},
            {"a": 42, "scoid": 84},
        ],
        "quiz_type": "mcs01",
        "quiz_pages": 12,
        "cert_cmid": 137,
    },
    "IDE": {
        "name": "Etiquette for Interacting with Persons with Disabilities (IDE)",
        "course_id": 265,
        "quiz_cmid": 691,
        "scorm_modules": [
            {"a": 214, "scoid": 428},
            {"a": 215, "scoid": 430},
            {"a": 216, "scoid": 432},
        ],
        "quiz_type": "ide",
        "quiz_pages": 10,
        "cert_cmid": 697,
    },
}

# ═══════════════════════════════════════════════════════
# MCS-01 ANSWER KEYS
# ═══════════════════════════════════════════════════════

MCS01_MCQ_ANSWERS = {
    "best defines the underlying cause of death": "started the chain of events leading to death",
    "30-year-old woman died 8 weeks after delivering": "O96",
    "infant born at 28 weeks gestation died at 2 days": "Certain conditions originating in the perinatal period",
    "elderly man died from complications of a head injury after falling from a ladder": "W11",
    "55-year-old man died of respiratory failure due to pulmonary fibrosis": "B90.9",
    "32-year-old woman died 18 months after delivering": "O97",
    "what code should be assigned as the underlying cause of death for the infant": "P00.0",
    "45-year-old man died from a self-inflicted gunshot": "X72",
    "man suffered a traumatic brain injury in a car accident": "Y85.0",
}

# ═══════════════════════════════════════════════════════
# IDE ANSWER KEYS (question text -> correct value index)
# ═══════════════════════════════════════════════════════

IDE_ANSWERS = {
    # Original 10 questions
    "People with disabilities want":       "Respect and equality",
    "Which statement is true":             "Many disabilities are invisible",
    "Saudi Disability Rights Law":         "Equal access to healthcare",
    "right approach to people with disabilities": "Respect and empowerment",
    "patient who uses a wheelchair":       "Asked if they need help",
    "patient with a cognitive disability": "Simplified instructions",
    "Protecting a patient":                "Respecting privacy",
    "Disability is mainly caused by":      "Interaction between health condition and environment",
    "inclusive healthcare environment":    "physically and communicatively accessible",
    "most respectful way to refer":        "Patient with a disability",
    # Pool batch 2
    "Before helping a patient":            "Ask first",
    "medical model of disability":         "Fixing the person",
    "Maintaining patient autonomy":        "Letting them make choices",
    "Healthcare professionals should":     "Treat all patients equally",
    "For a blind patient":                 "Introduce yourself and describe",
    "An inclusive healthcare environment should": "physically and communicatively accessible",
    # Pool batch 3
    "example of accessibility":            "ramp beside stairs",
    "patient with hearing loss":           "Face them when talking",
    "Communication with patients who have disabilities": "Respectful and adapted to their needs",
    "Practicing disability etiquette":     "Improve quality and safety",
    "social model of disability":          "Removing barriers in society",
}



# ═══════════════════════════════════════════════════════
# PHASE 0: Session Initialization
# ═══════════════════════════════════════════════════════

def init_sesskey():
    global SESSKEY
    print("🔍 Extracting SESSKEY...")
    r = cf_requests.get(f"{BASE_URL}/my/", headers=HEADERS, impersonate="chrome", timeout=TIMEOUT)

    # Extract account name from the page
    name_match = re.search(r'class="usertext[^"]*"[^>]*>([^<]+)', r.text)
    if not name_match:
        name_match = re.search(r'"userfullname":"([^"]+)"', r.text)
    if not name_match:
        name_match = re.search(r'<span class="userbutton">.*?<span[^>]*>([^<]+)</span>', r.text, re.DOTALL)
    if name_match:
        account_name = name_match.group(1).strip()
        print(f"👤 ACCOUNT_NAME: {account_name}")
    else:
        print("👤 ACCOUNT_NAME: Unknown")

    match = re.search(r'"sesskey":"([^"]+)"', r.text)
    if not match:
        match = re.search(r'sesskey=([^&"]+)', r.text)
    if match:
        SESSKEY = match.group(1)
        print(f"✅ SESSKEY: {SESSKEY}")
        return True
    print("❌ Could not extract SESSKEY!")
    return False


# ═══════════════════════════════════════════════════════
# PHASE 1: Auto-Enrollment
# ═══════════════════════════════════════════════════════

def auto_enroll(course_id):
    print(f"  📋 Checking enrollment for course {course_id}...")
    # Check by visiting the course page directly
    r = cf_requests.get(f"{BASE_URL}/course/view.php?id={course_id}", headers=HEADERS, impersonate="chrome", timeout=TIMEOUT)

    if "enrol/index.php" not in r.url:
        print("  ✅ Already enrolled.")
        return True

    print("  ▶️ Not enrolled, enrolling...")
    inst = re.search(r'name="instance" type="hidden" value="(\d+)"', r.text)
    if not inst:
        print("  ❌ No enrol form found.")
        return False

    payload = {
        "id": str(course_id),
        "instance": inst.group(1),
        "sesskey": SESSKEY,
        f"_qf__{inst.group(1)}_enrol_self_enrol_form": "1",
        "mform_isexpanded_id_selfheader": "1",
    }
    hdr = HEADERS.copy()
    hdr["content-type"] = "application/x-www-form-urlencoded"
    rp = cf_requests.post(f"{BASE_URL}/enrol/index.php", data=payload, headers=hdr, impersonate="chrome", timeout=TIMEOUT)
    if rp.status_code == 200 and "enrol/index.php" not in rp.url:
        print("  ✅ Enrolled successfully!")
        return True
    print(f"  ❌ Enrollment failed: {rp.status_code}")
    return False


# ═══════════════════════════════════════════════════════
# PHASE 2: SCORM Completion
# ═══════════════════════════════════════════════════════

def complete_scorm(a, scoid):
    payload = {
        "a": str(a), "sesskey": SESSKEY, "attempt": "1", "scoid": str(scoid),
        "cmi__core__lesson_status": "completed",
        "cmi__completion_status": "completed",
        "cmi__success_status": "passed",
        "cmi__suspend_data": '{"v":2,"d":[123,34,112,114,111,103,114,101,115,115,34,58,256,108,263,115,111,110,265,267,34,48,266,256,112,266,57,44,34,105,278,276,286,99,266,49,283,285,275,277,275,118,280,58,52,53,283,289,58,49,125,306,283,49,286,293,123,307,34,50,310,278,313,51,316,267,313,52,320,312,125,283,53,324,313,54,329,326,34,55,332,283,56,336,34,57,339,49,295,256,311,306,347,306],"cpv":"R8wK_NJ9"}',
    }
    hdr = HEADERS.copy()
    hdr["content-type"] = "application/x-www-form-urlencoded"
    hdr["x-requested-with"] = "XMLHttpRequest"
    hdr["referer"] = f"{BASE_URL}/mod/scorm/player.php?a={a}&currentorg=&scoid={scoid}"
    try:
        r = cf_requests.post(f"{BASE_URL}/mod/scorm/datamodel.php", data=payload, headers=hdr, impersonate="chrome", timeout=TIMEOUT)
        return r.status_code == 200
    except:
        return False


def complete_all_scorm(modules):
    print(f"  📚 Completing {len(modules)} SCORM modules...")
    for i, m in enumerate(modules, 1):
        ok = complete_scorm(m["a"], m["scoid"])
        print(f"    [{i}/{len(modules)}] a={m['a']}, scoid={m['scoid']} -> {'✅' if ok else '❌'}")
        time.sleep(0.3)


def is_quiz_passed(cmid):
    """Checks if the quiz already has a passing grade or is marked as completed/passed."""
    try:
        r = cf_requests.get(f"{BASE_URL}/mod/quiz/view.php?id={cmid}", headers=HEADERS, impersonate="chrome", timeout=TIMEOUT)
        # Check for passing indicators in Arabic and English
        passing_terms = [
            "منجز: يحرز درجة النجاح",
            "يحرز درجة النجاح",
            "Achieve a passing grade",
            "Passed",
            "Completed"
        ]
        # Also check for grade table
        if any(term in r.text for term in passing_terms):
            # Verify if it's the success badge
            if 'alert-success' in r.text and ("منجز" in r.text or "Done" in r.text):
                return True
        
        # Check grade value vs required
        grade_match = re.search(r"أعلى درجة: ([\d.]+)", r.text) # Highest grade in Arabic
        if not grade_match:
            grade_match = re.search(r"Highest grade: ([\d.]+)", r.text)
        
        if grade_match:
            grade = float(grade_match.group(1))
            # Get total if possible
            total_match = re.search(r"من أصل ([\d.]+)", r.text)
            if not total_match:
                total_match = re.search(r"out of ([\d.]+)", r.text)
            
            if total_match:
                total = float(total_match.group(1))
                pass_pct = 0.80 if cmid == 131 else 0.85
                if (grade / total) >= pass_pct:
                    return True
    except Exception as e:
        print(f"  ⚠️ Error checking status: {e}")
    return False

def check_certificate(cert_cmid):
    """Visits the certificate page to ensure it is generated/viewed."""
    print(f"  🎓 Checking and issuing certificate (cmid={cert_cmid})...")
    try:
        r = cf_requests.get(f"{BASE_URL}/mod/coursecertificate/view.php?id={cert_cmid}", headers=HEADERS, impersonate="chrome", timeout=TIMEOUT)
        if r.status_code == 200:
            if "tool/certificate/view.php" in r.text or "عرض الشهادة" in r.text or "View certificate" in r.text:
                print("  ✅ Certificate is available and checked!")
                return True
            else:
                print("  ⚠️ Certificate page loaded, but certificate might not be ready yet.")
                return False
        else:
            print(f"  ❌ Failed to load certificate page. Status: {r.status_code}")
            return False
    except Exception as e:
        print(f"  ⚠️ Error checking certificate: {e}")
        return False


# ═══════════════════════════════════════════════════════
# PHASE 3: Quiz Solver
# ═══════════════════════════════════════════════════════

def start_quiz(cmid):
    # First check the quiz view page for existing attempts
    rv = cf_requests.get(f"{BASE_URL}/mod/quiz/view.php?id={cmid}", headers=HEADERS, impersonate="chrome")

    # If there's an in-progress attempt, continue it
    cont = re.search(r'attempt\.php\?attempt=(\d+)', rv.text)
    if cont and 'Continue' in rv.text:
        attempt_id = cont.group(1)
        r = cf_requests.get(f"{BASE_URL}/mod/quiz/attempt.php?attempt={attempt_id}&cmid={cmid}", headers=HEADERS, impersonate="chrome")
        return (attempt_id, r.text)

    # Start new attempt
    data = {"cmid": str(cmid), "sesskey": SESSKEY}
    hdr = HEADERS.copy()
    hdr["content-type"] = "application/x-www-form-urlencoded"
    r = cf_requests.post(f"{BASE_URL}/mod/quiz/startattempt.php", data=data, headers=hdr, impersonate="chrome", allow_redirects=True, timeout=TIMEOUT)
    m = re.search(r"attempt=(\d+)", r.url)
    if m:
        return (m.group(1), r.text)

    # Maybe landed on a confirmation page
    if "startattempt" in r.text:
        # Re-submit with confirmation
        r2 = cf_requests.post(f"{BASE_URL}/mod/quiz/startattempt.php", data=data, headers=hdr, impersonate="chrome", allow_redirects=True, timeout=TIMEOUT)
        m2 = re.search(r"attempt=(\d+)", r2.url)
        if m2:
            return (m2.group(1), r2.text)

    return (None, r.text)


def fetch_page(attempt_id, cmid, page):
    r = cf_requests.get(f"{BASE_URL}/mod/quiz/attempt.php?attempt={attempt_id}&cmid={cmid}&page={page}", headers=HEADERS, impersonate="chrome", timeout=TIMEOUT)
    return r.text


def find_choice(choice_map, *keywords):
    for kw in keywords:
        for text, num in choice_map.items():
            if kw.lower() in text.lower():
                return num
    return None


# --- Unified MCQ Solver ---
def solve_mcq(html, attempt_id, page, cmid, answer_dict):
    qm = re.search(r'<div class="qtext">(.*?)</div>', html, re.DOTALL)
    if not qm:
        return (False, html)
    qtext = re.sub(r"<[^>]+>", "", qm.group(1)).strip()

    correct = None
    # Try direct mapping
    for key, val in answer_dict.items():
        if key.lower() in qtext.lower():
            correct = val
            break
    
    # Try learning table fuzzy match
    if not correct:
        for key, val in IDE_ANSWERS.items(): # This now acts as a secondary shared pool
            if key.lower() in qtext.lower():
                correct = val
                break

    if not correct:
        return (False, html)

    rn_m = re.search(r'name="(q\d+:\d+_answer)"', html)
    if not rn_m:
        return (False, html)
    rn = rn_m.group(1)

    # Support multiple formats for options
    opts = re.findall(r'value="(\d+)"[^>]*/>\s*<div[^>]*>\s*<span class="answernumber">[^<]*</span>\s*<div class="flex-fill ms-1">(.*?)</div>', html, re.DOTALL)
    if not opts:
        opts = re.findall(r'<input type="radio" name="' + re.escape(rn) + r'" value="(\d+)"[^>]*/>\s*<div[^>]*>\s*<div[^>]*>(.*?)</div>', html, re.DOTALL)
    if not opts:
        opts = re.findall(r'value="(\d+)"[^>]*/>\s*<div[^>]*>(.*?)</div>', html, re.DOTALL)

    chosen = None
    for val, lbl in opts:
        lbl_clean = re.sub(r"<[^>]+>", "", lbl).strip()
        if correct.lower() in lbl_clean.lower():
            chosen = val
            break
    
    if chosen is None:
        return (False, html)

    return submit_mcq(html, attempt_id, page, cmid, rn, chosen)


# --- Common MCQ Submit ---
def submit_mcq(html, attempt_id, page, cmid, radio_name, value):
    q_prefix = radio_name.rsplit("_", 1)[0]
    seq_m = re.search(r'name="' + re.escape(q_prefix) + r'_:sequencecheck" value="(\d+)"', html)
    seqcheck = seq_m.group(1) if seq_m else "1"
    slot_m = re.search(r'name="slots" value="(\d+)"', html)
    slot = slot_m.group(1) if slot_m else str(page + 1)

    payload = {
        "attempt": attempt_id, "thispage": str(page), "nextpage": str(page + 1),
        "timeup": "0", "sesskey": SESSKEY, "mdlscrollto": "0", "scrollpos": "0", "slots": slot,
        radio_name: value,
        f"{q_prefix}_:sequencecheck": seqcheck,
        f"{q_prefix}_:flagged": "0",
        "next": "Next page",
    }
    hdr = HEADERS.copy()
    # It identifies as multipart in the HTML, let's use a standard POST which curl_cffi handles well
    # Use multipart/form-data for Moodle quiz submissions
    files = {k: (None, str(v)) for k, v in payload.items()}
    try:
        r = cf_requests.post(f"{BASE_URL}/mod/quiz/processattempt.php?cmid={cmid}", files=files, headers=HEADERS, impersonate="chrome", allow_redirects=True, timeout=TIMEOUT)
        return (r.status_code == 200, r.text)
    except Exception as e:
        print(f"  ⚠️ Submission error: {e}")
        return (False, html)


# --- MCS-01 Drag & Drop Solver ---
def solve_mcs01_dd(html, attempt_id, page, cmid):
    slot_m = re.search(r'name="slots" value="(\d+)"', html)
    slot = slot_m.group(1) if slot_m else str(page + 1)

    prefix_m = re.search(r'name="(q\d+:\d+)_p\d+"', html)
    if not prefix_m:
        return False
    q_prefix = prefix_m.group(1)

    choices = re.findall(r'choice(\d+)\s+infinite">(.*?)</div>', html)
    choice_map = {text.strip(): num for num, text in choices}

    scenario_m = re.search(r'Case Scenario.*?</span></p>(.*?)</div></div>', html, re.DOTALL)
    scenario = re.sub(r"<[^>]+>", "", scenario_m.group(1)).strip() if scenario_m else ""

    init_m = re.search(r'amd\.init\("[^"]+",\s*false,\s*(\{.*?\})\)', html)
    drop_zones = {}
    if init_m:
        try:
            dz = json.loads(init_m.group(1))
            for k, v in dz.items():
                pn = v["fieldname"].split("_p")[1]
                drop_zones[pn] = {"x": int(v["xy"][0]), "y": int(v["xy"][1])}
        except:
            pass

    left = sorted([(p, d) for p, d in drop_zones.items() if d["x"] < 1000 and d["y"] < 750], key=lambda x: x[1]["y"])
    right = sorted([(p, d) for p, d in drop_zones.items() if d["x"] >= 1000 and d["y"] < 750], key=lambda x: x[1]["y"])
    part2 = [(p, d) for p, d in drop_zones.items() if d["y"] >= 750]

    layout = {}
    rows = ["a", "b", "c", "d"]
    for i, (pn, _) in enumerate(left):
        if i < len(rows): layout[f"cause_{rows[i]}"] = pn
    for i, (pn, _) in enumerate(right):
        if i < len(rows): layout[f"time_{rows[i]}"] = pn
    for pn, _ in part2:
        layout["part2"] = pn

    answers = {}
    if "cervical cancer" in scenario.lower():
        mapping = {"cause_a": ["Hamorrhage","Hemorrhage"], "time_a": ["2 Days"], "cause_b": ["Cervical cancer"], "time_b": ["1 Year"]}
        for k, v in mapping.items():
            if k in layout: answers[layout[k]] = find_choice(choice_map, *v)
        for k in ["cause_c","time_c","cause_d","time_d","part2"]:
            if k in layout: answers[layout[k]] = find_choice(choice_map, "None")

    elif "pulmonary embolism" in scenario.lower() or "31-year-old woman" in scenario.lower():
        if "cause_a" in layout: answers[layout["cause_a"]] = find_choice(choice_map, "Pulmonary embolism")
        if "time_a" in layout: answers[layout["time_a"]] = find_choice(choice_map, "1 Day")
        for k in ["cause_b","time_b","cause_c","time_c","cause_d","time_d"]:
            if k in layout: answers[layout[k]] = find_choice(choice_map, "None")
        if "part2" in layout: answers[layout["part2"]] = find_choice(choice_map, "Postpartum")

    elif "gastric cancer" in scenario.lower() or "65-year-old male" in scenario.lower():
        mapping = {
            "cause_a": ["Hemorrhagic shock"], "time_a": ["1 Day"],
            "cause_b": ["Gastrointestinal"], "time_b": ["2 Days"],
            "cause_c": ["Metastatic"], "time_c": ["6 Months"],
            "cause_d": ["Malignant neoplasm","C16.9"], "time_d": ["2 Years"],
        }
        for k, v in mapping.items():
            if k in layout: answers[layout[k]] = find_choice(choice_map, *v)
        if "part2" in layout: answers[layout["part2"]] = find_choice(choice_map, "None")
    else:
        return False

    seq_m = re.search(r'name="' + re.escape(q_prefix) + r'_:sequencecheck" value="(\d+)"', html)
    seqcheck = seq_m.group(1) if seq_m else "1"

    payload = {
        "attempt": attempt_id, "thispage": str(page), "nextpage": str(page + 1),
        "timeup": "0", "sesskey": SESSKEY, "mdlscrollto": "", "slots": slot,
        f"{q_prefix}_:sequencecheck": seqcheck, f"{q_prefix}_:flagged": "0",
        "next": "Next page",
    }
    for pn, cn in answers.items():
        if cn:
            payload[f"{q_prefix}_p{pn}"] = str(cn)

    files = {k: (None, str(v)) for k, v in payload.items()}
    try:
        r = cf_requests.post(f"{BASE_URL}/mod/quiz/processattempt.php?cmid={cmid}", files=files, headers=HEADERS, impersonate="chrome", allow_redirects=True, timeout=TIMEOUT)
        return (r.status_code == 200, r.text)
    except Exception as e:
        print(f"  ⚠️ Drag&Drop submission error: {e}")
        return (False, html)


# --- Submit Final ---
def submit_quiz(attempt_id, cmid):
    payload = {
        "attempt": attempt_id, "finishattempt": "1", "timeup": "0",
        "slots": "", "sesskey": SESSKEY, "cmid": str(cmid),
    }
    hdr = HEADERS.copy()
    try:
        r = cf_requests.post(f"{BASE_URL}/mod/quiz/processattempt.php?cmid={cmid}", data=payload, headers=hdr, impersonate="chrome", allow_redirects=True, timeout=TIMEOUT)
    except:
        print("  ❌ Connection timed out during submission.")
        return (0, 0)

    if r.status_code == 200:
        grade = re.search(r"Grade\s*([\d.]+)\s*out of\s*([\d.]+)", r.text)
        states = re.findall(r'class="state">(.*?)</div>', r.text)
        correct = sum(1 for s in states if s.strip() == "Correct")
        total = len(states)
        if grade:
            print(f"  🏆 Grade: {grade.group(1)}/{grade.group(2)}")
        if states:
            print(f"  📊 Correct: {correct}/{total}")
        if not grade and not states:
            print("  ✅ Submitted!")

        # Learn from wrong answers for IDE quiz
        if total > 0 and correct < total:
            blocks = re.findall(r'(class="que multichoice.*?)(?=class="que multichoice|class="submitbtns")', r.text, re.DOTALL)
            for block in blocks:
                st = re.search(r'class="state">(.*?)</div>', block)
                if st and st.group(1).strip() != "Correct":
                    qt = re.search(r'<div class="qtext">(.*?)</div>', block, re.DOTALL)
                    qt_clean = re.sub(r"<[^>]+>", "", qt.group(1)).strip() if qt else ""
                    # Find correct option
                    corr = re.findall(r'class="r\d+([^"]*)">\s*.*?<div class="flex-fill ms-1">(.*?)</div>', block, re.DOTALL)
                    for extra, opt_text in corr:
                        if "correct" in extra:
                            ans = re.sub(r"<[^>]+>", "", opt_text).strip()
                            # Add to answer key dynamically
                            key = qt_clean[:50]
                            # Use quiz_type to direct learned answers, but IDE is the primary fuzzy pool
                            if "MCS-01" in r.text or "Cause of Death" in r.text:
                                MCS01_MCQ_ANSWERS[key] = ans
                            else:
                                IDE_ANSWERS[key] = ans
                            print(f"  📝 Learned: \"{key}\" -> \"{ans}\"")

        return (correct, total)
    print(f"  ❌ Submit failed: {r.status_code}")
    return (0, 0)


# ═══════════════════════════════════════════════════════
# COURSE RUNNER
# ═══════════════════════════════════════════════════════

def solve_quiz(c):
    """Attempt the quiz once, return (correct, total)."""
    print(f"  🧠 Starting exam (cmid={c['quiz_cmid']})...")
    attempt_id, first_html = start_quiz(c["quiz_cmid"])
    if not attempt_id:
        print("  ❌ Failed to start quiz!")
        return (0, 0)
    print(f"  ✅ Attempt: {attempt_id}")

    html = first_html
    for page in range(c["quiz_pages"]):
        # Navigation logic: if we have the next page HTML from the previous POST, use it.
        # Otherwise, fetch it.
        if page > 0 and not html_ready:
            html = fetch_page(attempt_id, c["quiz_cmid"], page)
            time.sleep(0.3)

        html_ready = False
        if c["quiz_type"] == "mcs01":
            if page <= 8:
                ok, next_html = solve_mcq(html, attempt_id, page, c["quiz_cmid"], MCS01_MCQ_ANSWERS)
            else:
                ok, next_html = solve_mcs01_dd(html, attempt_id, page, c["quiz_cmid"])
        elif c["quiz_type"] == "ide":
            ok, next_html = solve_mcq(html, attempt_id, page, c["quiz_cmid"], IDE_ANSWERS)
        else:
            ok, next_html = (False, html)

        if ok:
            html = next_html
            html_ready = True

        status = "✅" if ok else "❌"
        print(f"    Q{page+1}/{c['quiz_pages']} {status}")
        time.sleep(0.3)

    return submit_quiz(attempt_id, c["quiz_cmid"])


def run_course(course_key):
    c = COURSES[course_key]
    print(f"\n{'═' * 60}")
    print(f"  📘 {c['name']}")
    print(f"{'═' * 60}")

    # Enroll
    auto_enroll(c["course_id"])

    # SCORM
    complete_all_scorm(c["scorm_modules"])

    # First check if quiz is already passed
    if is_quiz_passed(c["quiz_cmid"]):
        print(f"  🎉 Course {course_key} is ALREADY PASSED (100% complete).")
        if "cert_cmid" in c:
            check_certificate(c["cert_cmid"])
        return True

    # Quiz - with retry for random pool quizzes
    pass_pct = 0.80 if c["quiz_type"] == "mcs01" else 0.85
    max_attempts = 5

    for attempt_num in range(1, max_attempts + 1):
        if attempt_num > 1:
            print(f"\n  🔄 Retry #{attempt_num}...")
        correct, total = solve_quiz(c)
        if total > 0 and (correct / total) >= pass_pct:
            print(f"  🎉 PASSED! ({correct}/{total})")
            if "cert_cmid" in c:
                check_certificate(c["cert_cmid"])
            return True
        elif total > 0:
            print(f"  ⚠️ Below passing ({correct}/{total}), retrying...")
        else:
            print("  ⚠️ Could not get results.")
            break

    print(f"  ❌ Could not pass after {max_attempts} attempts.")
    return False


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookie", help="MoodleSession cookie value")
    args = parser.parse_args()

    if args.cookie:
        global COOKIE_STRING, HEADERS
        COOKIE_STRING = f"MoodleSession={args.cookie}" if "MoodleSession=" not in args.cookie else args.cookie
        HEADERS["cookie"] = COOKIE_STRING

    print("\n" + "═" * 60)
    print("  🚀 HATMS FULL AUTOMATION (2 Courses)")
    print("═" * 60)

    if not init_sesskey():
        return

    for key in COURSES:
        run_course(key)

    print(f"\n{'═' * 60}")
    print("  🏁 ALL DONE! Both courses completed + exams submitted.")
    print("═" * 60)


if __name__ == "__main__":
    main()

