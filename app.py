import random
from math import floor

from flask import Flask, jsonify, redirect, render_template, request, url_for
from nba_api.stats.static import players

import firebase_admin
from firebase_admin import credentials, firestore

categories = ['ball', 'aura', 'hot', 'like',
    'scorer', 'defender', 'playmaker', 
    'controversial', 'franchise', 
    'roommate', 'leader', 'teammate'
]
category_prompts = {
    'ball' : 'Who is the better basketball player?',
    'aura' : 'Who has more aura?',
    'hot' : "Who is more attractive?",
    'like' : "Which player do you like more?",
    'scorer' : 'Who is the better scorer?',
    'defender' : 'Who is the better defender?',
    'playmaker' : 'Who is the better playmaker?',
    'controversial' : 'Who is more controversial?',
    'franchise' : "Who would you rather start a franchise with today?",
    'roommate' : "Who would you rather have as a roommate?",
    'leader' : "Who is a better leader?",
    'teammate' : "Who is a better teammate?"
}

ALL_PLAYERS = players.get_players()
ACTIVE_PLAYERS = players.get_active_players()

cred = credentials.Certificate("serviceKey.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True

def get_headshot_url(player_id):
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"

# ELO logic
def expected(rA, rB):
    return 1 / (1 + 10 ** ((rB - rA) / 400))

def update_elo(rA, rB, winner_is_A, K=32):
    EA = expected(rA, rB)
    EB = expected(rB, rA)

    SA = 1 if winner_is_A else 0
    SB = 1 if not winner_is_A else 0
    return (rA + K * (SA - EA), rB + K * (SB - EB), EA, EB)



def get_or_create(player):
    ref = db.collection("players").document(str(player["id"]))
    doc = ref.get()

    if doc.exists:
        return doc.to_dict()
    else:
        data = { cat : 1500 for cat in categories}
        ref.set(data)
        return data

def load_players(active=True):
    if active:
        p1, p2 = random.sample(ACTIVE_PLAYERS, 2)
    else:
        p1, p2 = random.sample(ALL_PLAYERS, 2)
    p1 = { "name": p1["full_name"], "id": p1["id"], "image": get_headshot_url(p1["id"]) }
    p2 = { "name": p2["full_name"], "id": p2["id"], "image": get_headshot_url(p2["id"]) }
    return (p1, p2)



# ROUTES
@app.route('/')
def home():
    cat = categories[floor(random.random() * len(categories))]
    p1, p2 = load_players()
    return render_template('rank.html', p1=p1, p2=p2, prompt=category_prompts[cat], category=cat)

@app.route('/leaderboard')
def reroute_to_main_leaderboard():
    return redirect('/leaderboard/ball')
@app.route("/leaderboard/<category>")
def leaderboard(category):
    return render_template("leaderboard.html", category=category)

@app.route('/about')
def about():
    return render_template('about.html')


@app.route("/api/leaderboard/<category>")
def leaderboard_api(category):
    last = request.args.get("last")
    query = (db.collection("players")
        .order_by(category, direction=firestore.Query.DESCENDING)
        .limit(50)
    )
    if last:
        last_doc = db.collection("players").document(last).get()
        query = query.start_after(last_doc)

    docs = query.stream()

    ps = []
    last_seen = None
    for doc in docs:
        data = doc.to_dict()
        p = { "id": doc.id, "name": players.find_player_by_id(doc.id)['full_name'], "image": get_headshot_url(doc.id) }
        for k, v in data.items(): p[k] = v

        ps.append(p)
        last_seen = doc.id

    return jsonify({
        "players": ps,
        "last": last_seen
    })


# endpoints to load data
@app.route("/new_matchup")
def matchup():
    active = request.args.get("active")
    cat = categories[floor(random.random() * len(categories))]
    p1, p2 = load_players(active)
    return jsonify({"p1": p1, "p2": p2, "prompt": category_prompts[cat], "category": cat})

@app.route("/submit", methods=["POST"])
def submit():
    data = request.json

    p1 = data["p1"]
    p2 = data["p2"]
    winner_id = data["winner"]
    cat = data["cat"]

    p1_db = get_or_create(p1)
    p2_db = get_or_create(p2)

    r1, r2 = p1_db[cat], p2_db[cat] 
    if r1 is None: r1 = 1500
    if r2 is None: r2 = 1500

    app.logger.info(f"{winner_id}, { p1['id'] }, {winner_id == p1['id']}")
    winner_is_p1 = (str(winner_id) == str(p1["id"]))
    new_r1, new_r2, E1, E2 = update_elo(r1, r2, winner_is_p1)

    db.collection("players").document(str(p1["id"])).update({cat : new_r1})
    db.collection("players").document(str(p2["id"])).update({cat : new_r2})

    return jsonify({
        "p1": {**p1, "before": r1, "after": new_r1, "expected": E1},
        "p2": {**p2, "before": r2, "after": new_r2, "expected": E2},
        "winner": winner_id
    })

if __name__ == '__main__':
    app.run(debug=True)