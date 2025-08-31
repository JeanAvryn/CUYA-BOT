from flask import Flask, render_template, request, jsonify
from datetime import datetime
from flask import session, redirect, url_for
import sqlite3
import urllib.parse

app = Flask(__name__)
DB_NAME = "reports.db"

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    emergency_type TEXT,
                    location TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

# Chat memory
user_state = {
    "awaiting_location": False,
    "emergency_type": None,
    "stage": None,
    "extra_info": {},
    "follow_up_index": 0
}

# Follow-up questions per emergency type
follow_up_questions = {
    "🔥 Fire": [
        "Are there any injuries? (May nasugatan po ba?)",
        "How large is the fire? (Gaano kalaki ang sunog?)"
    ],
    "🌊 Flood": [
        "How high is the flood? (Gaano kataas ang baha?)",
        "Are you stranded within your area? (Hindi na po ba kayo makakalabas sa pinaroroonan ninyo?)"
    ],
    "🚑 Road Accident": [
        "How many people are involved? (Ilang tao ang nasangkot?)",
        "Is an ambulance needed? (May kailangan bang ambulansya?)"
    ],
    "🌍 Earthquake": [
        "How strong did you feel the earthquake? (Gaano kalakas mo naramdaman ang lindol?)",
        "Did any structures fall? (May bumagsak bang estruktura?)",
        "Were there any injured or do anyone need help? (May nasugatan ba o nanghihingi ng tulong?)",
    ],
    "🏔️ Landslide": [
        "Were people, houses, or vehicles buried? (May natabunan bang tao, bahay, o sasakyan?)",
        "Is the ground still moving? (May gumagalaw pa bang lupa?)"
    ],
    "🗂️ Oil Spill": [
        "What kind of oil was spilled? (Anong uri ng langis ang natapon?)",
        "Were animals or people affected? (May mga hayop o tao bang naapektuhan?)"
    ],
    "⚡ Power Outage": [
        "When did it start? (Kailan po ito nagsimula?)",
        "How many homes or areas are affected? (Ilang bahay o lugar ang apektado?)"
    ],
    "💥 Explosion": [
        "What type of explosion occurred? (Anong uri ng pagsabog?)",
        "Are there any injured or missing? (May sugatan o nawawala bang tao?)"
    ],
    "🌪️ Tornado": [
        "How strong was the tornado? (Gaano kalakas ang ipo-ipo?)",
        "Were buildings or properties destroyed? (May nawasak bang gusali o ari-arian?)"
    ],
    "🦠 Epidemic": [
        "How many people have symptoms? (Ilang tao na po ang may sintomas?)",
        "What symptoms are most common? (Anong sintomas ang nararanasan ng karamihan?)"
    ],
    "🐍 Animal Attack": [
        "What kind of animal attacked? (Anong hayop ang umatake?)",
        "Was the victim treated or vaccinated immediately? (Nabakunahan ba agad ang biktima?)"
    ],
    "🚨 Crime or Theft": [
        "What kind of crime occurred? (Anong klaseng krimen ang naganap?)",
        "Was anyone hurt? (May nasaktan bang biktima?)"
    ],
    "⚠️ General Danger": [
        "What kind of threat did you witness? (Anong uri ng banta ang nakita mo?)",
        "Is there still danger in the area? (May kasalukuyang panganib pa ba sa lugar?)"
    ],
}

# Location detector
def is_location_in_cuyapo(location):
    location = location.lower()
    cuyapo_keywords = [
        "cuyapo", "baloy", "bambanaba", "butao", "bantug", "san antonio",
        "san jose", "bentigan", "bibiclat", "bonifacio", "bued", "bulala", "burgos",
        "cabileo", "cacapasan", "cabatuan", "calancuasan norte", "calancuasan sur", "colosboa",
        "columbitin", "curva", "district 1", "district 2", "district 4", "district 5",
        "district 6", "district 7", "district 8", "landig", "latap", "loob", "luna",
        "malbeg", "malineng", "matindeg", "nagcuralan", "nagmisahan", "paitan norte", "paitan sur",
        "piglisan", "pugo", "rizal", "sabit", "salagusog", "san juan", "santa clara", "santa cruz",
        "simimbaan", "maycaban", "tagtagumba", "ungab", "tutuloy", "villaflores"
    ]
    return any(keyword in location for keyword in cuyapo_keywords)

# AI-Enhanced Chatbot Logic
def chatbot_response(message):
    message = message.lower()

    # Friendly talk
    greetings = ["hi", "hello", "kamusta", "kumusta", "heyy", "good day", "gud pm", "gud am", "may tao ba", "anyone there", "hello po", "uy", "yo", "hey"]
    help_commands = ["help", "tulong", "how to", "paano to", "pano gamitin", "guide", "what can you do", "ano to", "anong ginagawa mo", "instructions", "ano gamit mo"]
    bot_name_queries = ["ano pangalan mo", "who are you", "anong pangalan mo", "pangalan mo", "name please", "what's your name"]

    if any(word in message for word in greetings):
        return "👋 Hello! I’m CUYA-BOT, your emergency assistant.\n📝 You can say things like 'May sunog!' or 'There’s a flood!' to report an emergency."

    if any(word in message for word in help_commands):
        return "🚘 I can detect and log emergencies like fire, flood, road accidents, earthquakes, and more.\nJust describe the situation and I’ll ask for your location next."

    if any(word in message for word in bot_name_queries):
        return "🤖 I’m CUYA-BOT — short for *Cuyapo AI Bot*. I help report local emergencies for faster response!"

    # Follow-up logic
    if user_state["stage"] == "location":
        if not is_location_in_cuyapo(message):
            user_state.update({
                "awaiting_location": False,
                "emergency_type": None,
                "stage": None,
                "extra_info": {},
                "follow_up_index": 0
            })
            return "📍 Paumanhin, CUYA-BOT ay para lang sa mga insidente sa Cuyapo, Nueva Ecija."

        user_state["extra_info"]["location"] = message.title()
        user_state["stage"] = "follow_ups"
        user_state["follow_up_index"] = 0
        questions = follow_up_questions.get(user_state["emergency_type"], [])
        if questions:
            return questions[0]
        else:
            user_state["stage"] = "done"
            return "✅ Emergency recorded. Naiulat na po sa lokal na pamahalaan."

    elif user_state["stage"] == "follow_ups":
        index = user_state["follow_up_index"]
        question = follow_up_questions.get(user_state["emergency_type"], [])[index]
        user_state["extra_info"][question] = message
        user_state["follow_up_index"] += 1
        questions = follow_up_questions.get(user_state["emergency_type"], [])
        if user_state["follow_up_index"] < len(questions):
            return questions[user_state["follow_up_index"]]
        else:
            user_state["stage"] = None
            location = user_state["extra_info"].get("location", "Unknown")
            emergency_type = user_state["emergency_type"]
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            answers = "; ".join([f"{k} – {v}" for k, v in user_state["extra_info"].items() if k != "location"])

            # Reset state
            user_state.update({
                "awaiting_location": False,
                "emergency_type": None,
                "stage": None,
                "extra_info": {},
                "follow_up_index": 0
            })

            # Save to DB
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT INTO reports (timestamp, emergency_type, location) VALUES (?, ?, ?)",
                      (timestamp, f"{emergency_type} | {answers}", location))
            conn.commit()
            conn.close()

            encoded_location = urllib.parse.quote(location)
            maps_link = f"https://www.google.com/maps/search/?q={encoded_location}"
            return f"✅ Naiulat na ang insidente sa LGU.\n📍 {location}\n🗺️ {maps_link}"

    # Detect emergencies
    keywords = {
        "🔥 Fire": ["fire", "sunog", "nasusunog", "may apoy", "apoy"],
        "🌊 Flood": ["flood", "baha", "binaha", "nalubog", "tag-ulan", "rain", "lightning", "ulan", "bagyo", "typhoon", "storm", "kidlat"],
        "🚑 Road Accident": ["accident", "bangga", "nabundol", "naaksidente", "crash", "collision"],
        "🌍 Earthquake": ["earthquake", "lindol", "umuga", "nayanig"],
        "🏔️ Landslide": ["landslide", "guho", "gumuhong lupa", "land slide"],
        "🗂️ Oil Spill": ["oil spill", "langis", "tagas ng langis", "leak"],
        "⚡ Power Outage": ["brownout", "blackout", "power outage", "walang kuryente", "nawalan ng ilaw"],
        "💥 Explosion": ["explosion", "sumabog", "pagsabog", "blasted"],
        "🌪️ Tornado": ["tornado", "ipo-ipo", "twister"],
        "🦠 Epidemic": ["epidemic", "virus", "lagnat", "ubo", "may sakit", "outbreak", "nagkakasakit", "sakit"],
        "🐍 Animal Attack": ["snake", "bite", "nakagat", "aso", "pusa", "kinagat"],
        "🚨 Crime or Theft": ["nakawan", "magnanakaw", "krimen", "crime", "holdap", "hold-up", "burglary"],
        "⚠️ General Danger": ["delikado", "threat", "suspicious", "tulungan", "tulong", "kaso", "danger"]
    }

    for category, terms in keywords.items():
        if any(term in message for term in terms):
            user_state["awaiting_location"] = True
            user_state["emergency_type"] = category
            user_state["stage"] = "location"
            return f"{category} detected.📍 Saan po nangyari ang insidente?"

    return "🤖 Sorry, I didn't understand. Please report a disaster like 'fire', 'flood', 'accident', etc."

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    bot_reply = chatbot_response(user_message)
    return jsonify({'reply': bot_reply})

@app.route('/reports')
def view_reports():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM reports ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return render_template('reports.html', reports=rows)

@app.route('/delete/<int:report_id>', methods=['POST'])
def delete_report(report_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM reports WHERE id = ?", (report_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)
