import streamlit as st
import pandas as pd
import json
import altair as alt
from datetime import date, datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# --- ICONS ---
ICON_TROPHY = "\U0001F3C6"
ICON_PUZZLE = "\U0001F9E9"
ICON_CHECK = "\u2705"
ICON_NOTE = "\U0001F4DD"
ICON_FIRE = "\U0001F525"
ICON_REFRESH = "\U0001F504"
ICON_TRASH = "\U0001F5D1"
ICON_INFO = "\u2139\uFE0F"
ICON_GROUP = "\U0001F465"
ICON_BOOKS = "\U0001F4DA"
ICON_CALENDAR = "\U0001F4C5"
ICON_SCROLL = "\U0001F4DC"
ICON_TOOL = "\U0001F6E0"
ICON_CROSS = "\u274C"
ICON_GEAR = "\u2699\uFE0F"
ICON_CHART = "\U0001F4C8"
ICON_RULES = "\U0001F4DC"

st.set_page_config(page_title="Wordle Competitive", page_icon=ICON_PUZZLE, layout="wide")

# --- MOBILE STYLING ---
def mobile_friendly_style():
    st.markdown("""
        <style>
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        #stDecoration {display:none;}
        
        .block-container {
            padding-top: 0.5rem !important;
            padding-bottom: 2rem !important;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        
        h1 { text-align: center; margin-bottom: 0px; }
        
        div.stButton > button {
            width: 100%;
            border-radius: 8px;
            height: 2.8em;
            font-weight: bold;
        }
        
        input { font-size: 16px !important; }
        
        /* --- STAT BOX CSS --- */
        .stat-card {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            border-radius: 12px;
            padding: 12px;
            margin-bottom: 15px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .stat-header {
            font-size: 1.3rem;
            font-weight: 900;
            color: #212529;
            margin-bottom: 10px;
            border-bottom: 2px solid #e9ecef;
            padding-bottom: 5px;
        }
        
        /* UPDATED TO 4 COLUMNS TO FIT TIES */
        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 5px;
            margin-bottom: 12px;
            text-align: center;
        }
        .stat-item {
            display: flex;
            flex-direction: column;
        }
        .stat-label {
            font-size: 0.70rem;
            text-transform: uppercase;
            color: #6c757d;
            font-weight: 700;
        }
        .stat-value {
            font-size: 1.1rem;
            font-weight: 800;
            color: #212529;
        }
        .stat-value.win { color: #198754; } 
        .stat-value.tie { color: #fd7e14; } /* Orange for Ties */
        
        .guess-container {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            justify-content: center;
        }
        .guess-pill {
            background-color: #ffffff;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 4px 8px;
            font-family: monospace;
            font-size: 0.9rem;
            font-weight: bold;
            color: #212529;
            box-shadow: 0 1px 1px rgba(0,0,0,0.05);
        }
        .guess-pill.zero {
            background-color: transparent;
            border: 1px dashed #e9ecef;
            color: #adb5bd; 
            box-shadow: none;
        }
        </style>
        """, unsafe_allow_html=True)

mobile_friendly_style()

# --- DATA MANAGER ---
def get_connection():
    return st.connection("gsheets", type=GSheetsConnection)

def load_data():
    conn = get_connection()
    df_players = conn.read(worksheet="players")
    players_dict = {}
    for index, row in df_players.iterrows():
        burned_list = str(row["Burned"]).split("|") if pd.notna(row["Burned"]) and row["Burned"] != "" else []
        sols_list = str(row["Past_Solutions"]).split("|") if pd.notna(row["Past_Solutions"]) and row["Past_Solutions"] != "" else []
        players_dict[row["Name"]] = {
            "score": int(row["Score"]), "clean_days": int(row["Clean_Days"]),
            "burned": burned_list, "past_solutions": sols_list
        }

    # --- SAFER HISTORY LOADING ---
    df_history = conn.read(worksheet="history")
    history_list = []
    
    # Convert to Datetime, handle errors
    df_history["Date"] = pd.to_datetime(df_history["Date"], errors="coerce")
    
    # If bad dates exist, fill with dummy date instead of deleting
    if df_history["Date"].isnull().any():
        st.toast("⚠️ Warning: Some dates were unreadable. Moved to bottom.", icon="⚠️")
        df_history["Date"] = df_history["Date"].fillna(pd.Timestamp("1900-01-01"))

    df_history = df_history.sort_values(by="Date", ascending=False)
    
    for index, row in df_history.iterrows():
        raw_json = row["Scores_JSON"]
        scores_data = {}
        if pd.notna(raw_json) and str(raw_json).strip() != "":
            try:
                scores_data = json.loads(raw_json)
            except:
                scores_data = {}

        history_list.append({
            "date": row["Date"].strftime("%Y-%m-%d"),
            "solution": row["Solution"] if pd.notna(row["Solution"]) else "?",
            "winner_log": row["Winner_Log"] if pd.notna(row["Winner_Log"]) else "",
            "victory_awarded": bool(row["Victory_Awarded"]),
            "scores": scores_data
        })
    return {"players": players_dict, "history": history_list}

def save_data(data):
    conn = get_connection()
    player_rows = []
    for name, stats in data["players"].items():
        player_rows.append({
            "Name": name, "Score": stats["score"], "Clean_Days": stats["clean_days"],
            "Burned": "|".join(stats["burned"]), "Past_Solutions": "|".join(stats["past_solutions"])
        })
    df_p = pd.DataFrame(player_rows)
    history_rows = []
    for h in data["history"]:
        history_rows.append({
            "Date": h["date"], "Solution": h["solution"],
            "Winner_Log": h.get("winner_log", ""), "Victory_Awarded": h.get("victory_awarded", False),
            "Scores_JSON": json.dumps(h["scores"])
        })
    df_h = pd.DataFrame(history_rows)
    try:
        conn.update(worksheet="players", data=df_p)
        conn.update(worksheet="history", data=df_h)
    except Exception as e:
        st.error(f"Error saving: {e}")
    st.cache_data.clear()

def guess_from_base(base_score):
    map_score = {10:1, 8:2, 6:3, 4:4, 2:5, 1:6, 0:"Fail"}
    return map_score.get(base_score, "-")

# --- CALCULATION LOGIC ---
def calculate_day_stats(guesses, wrong_words_str, solution, current_burned_set, current_solutions_set, current_streak):
    base_map = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2, 6: 1, "Fail": 0}
    base = base_map.get(guesses, 0)
    if guesses == "Fail": base = 0
    penalties = 0; penalty_log = []; new_burns_for_day = []
    wrong_words_list = [w.strip().upper() for w in wrong_words_str.split(",") if w.strip()]
    for word in wrong_words_list:
        if word in current_burned_set: penalties += 2; penalty_log.append(f"{word} (Burned)")
        elif word in current_solutions_set: penalty_log.append(f"{word} (Grace Used)"); new_burns_for_day.append(word) 
        else: new_burns_for_day.append(word) 
    is_clean = (penalties == 0)
    bonus = 0; new_streak_val = current_streak
    if is_clean:
        new_streak_val += 1
        tier = ((new_streak_val - 1) // 7) + 1
        bonus = tier * 3
    return {
        "score": base - penalties + bonus, "base": base, "guesses": guesses, "penalties": penalties,
        "bonus": bonus, "log": penalty_log, "new_burns": new_burns_for_day, 
        "new_streak": new_streak_val, "wrong_words_input": wrong_words_str
    }

def recalculate_history(data):
    for p in data["players"]: data["players"][p] = {"score": 0, "clean_days": 0, "burned": [], "past_solutions": []}
    chronological = sorted(data["history"], key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))
    for day in chronological:
        sol = day["solution"]; daily_perf = {}
        for p_name in data["players"]:
            if p_name in day["scores"]:
                raw_input = day["scores"][p_name].get("wrong_words_input", "")
                raw_guess = day["scores"][p_name].get("guesses", guess_from_base(day["scores"][p_name].get("base", 0)))
                p_state = data["players"][p_name]
                stats = calculate_day_stats(raw_guess, raw_input, sol, set(p_state["burned"]), set(p_state["past_solutions"]), p_state["clean_days"])
                p_state["score"] += stats["score"]
                p_state["clean_days"] = stats["new_streak"]
                p_state["burned"].extend(stats["new_burns"])
                if sol and sol not in p_state["past_solutions"]: p_state["past_solutions"].append(sol)
                day["scores"][p_name] = stats
                daily_perf[p_name] = stats["base"] - stats["penalties"]
        if daily_perf:
            max_perf = max(daily_perf.values())
            winners = [p for p, s in daily_perf.items() if s == max_perf]
            day["winner_log"] = f"{winners[0]} (+1)" if len(winners) == 1 else "Tie (No Bonus)"
            day["victory_awarded"] = True
            if len(winners) == 1: data["players"][winners[0]]["score"] += 1
    data["history"] = list(reversed(chronological))
    return data

# --- STATS HELPERS ---
def get_badges(player_name, player_data, history):
    badges = []
    if player_data["clean_days"] >= 7: badges.append("🔥")
    if history:
        last_game = history[0]
        if player_name in last_game["scores"]:
            g = last_game["scores"][player_name].get("guesses")
            if g in [1, 2]: badges.append("🎯")
    recent_games = [h for h in history[:5] if player_name in h["scores"]]
    if len(recent_games) >= 3:
        penalties = sum([h["scores"][player_name].get("penalties", 0) for h in recent_games])
        if penalties == 0: badges.append("🛡️")
    return " ".join(badges)

# --- MAIN APP UI ---
data = load_data()

st.title(f"{ICON_PUZZLE} Wordle League")

# SCOREBOARD
sorted_players = sorted(data["players"].items(), key=lambda x: x[1]['score'], reverse=True)
cols = st.columns(len(sorted_players))

for i, (name, p_data) in enumerate(sorted_players):
    badges_str = get_badges(name, p_data, data["history"])
    with cols[i]:
        st.markdown(f"""
        <div style="background-color: #f8f9fa; border-radius: 10px; padding: 10px; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); margin-bottom: 15px;">
            <div style="font-size: 1.6rem; font-weight: 900; color: black; margin-bottom: -5px;">
                {name} <span style="font-size: 0.8rem;">{badges_str}</span>
            </div>
            <div style="font-size: 3rem; font-weight: 800; color: #FF4B4B; line-height: 1.1;">
                {p_data['score']}
            </div>
            <div style="font-size: 1rem; font-weight: bold; color: #006600;">
                Streak: {p_data['clean_days']}
            </div>
        </div>
        """, unsafe_allow_html=True)

st.write("---")

# ACTION BAR
c1, c2 = st.columns([1, 1])
with c1:
    search_term = st.text_input("Burn Checker", placeholder="Check word...", label_visibility="collapsed").upper().strip()
with c2:
    if st.button(f"{ICON_REFRESH} Updates", use_container_width=True):
        st.cache_data.clear(); st.rerun()

# --- SMART BURN CHECKER ---
if search_term:
    found_any = False
    res_cols = st.columns(len(data["players"]))
    for i, (p_name, p_data) in enumerate(data["players"].items()):
        with res_cols[i]:
            if search_term in p_data["burned"]:
                # SCAN HISTORY FOR THE DATE
                found_date = None
                for day in data["history"]:
                    if day["solution"] == search_term:
                        found_date = day["date"]; break
                    if p_name in day["scores"]:
                        p_day = day["scores"][p_name]
                        if "new_burns" in p_day and search_term in p_day["new_burns"]:
                            found_date = day["date"]; break
                
                date_display = ""
                if found_date:
                    try:
                        dt = datetime.strptime(found_date, "%Y-%m-%d")
                        date_display = f" on {dt.strftime('%b %d, %Y')}"
                    except: date_display = f" ({found_date})"
                else: date_display = " (Legacy)"

                st.error(f"{p_name}: BURNED{date_display}"); found_any = True
            else: st.success(f"{p_name}: Safe")
    if not found_any: st.caption(f"'{search_term}' is safe.")
    st.write("---")

# TABS (Rules Added)
tab_play, tab_stats, tab_history, tab_rules, tab_library = st.tabs([
    f"{ICON_CALENDAR} Daily", 
    f"{ICON_CHART} Stats", 
    f"{ICON_SCROLL} History", 
    f"{ICON_RULES} Rules", 
    f"{ICON_BOOKS} Library"
])

with tab_play:
    if 'curr_date' not in st.session_state: st.session_state.curr_date = date.today()
    d_col1, d_col2, d_col3 = st.columns([1, 2, 1])
    with d_col1:
        if st.button("◀", use_container_width=True): st.session_state.curr_date -= timedelta(days=1); st.rerun()
    with d_col3:
        if st.button("▶", use_container_width=True): st.session_state.curr_date += timedelta(days=1); st.rerun()
    with d_col2:
        st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.curr_date.strftime('%b %d')}</h3>", unsafe_allow_html=True)
        new_date = st.date_input("Jump", value=st.session_state.curr_date, label_visibility="collapsed")
        if new_date != st.session_state.curr_date: st.session_state.curr_date = new_date; st.rerun()

    date_str = str(st.session_state.curr_date)
    existing_day = next((item for item in data["history"] if item["date"] == date_str), None)
    if not existing_day: current_day_data = {"date": date_str, "solution": "", "victory_awarded": False, "scores": {}}
    else: current_day_data = existing_day

    # Spoiler Logic
    done_count = len(current_day_data["scores"]); total_p = len(data["players"])
    in_prog = (done_count > 0) and (done_count < total_p)
    show_spoiler = st.checkbox("Show Solution", value=False)
    if in_prog and not show_spoiler:
        st.info("🙈 Solution hidden until all submit.")
        solution = st.text_input("Solution", value=current_day_data["solution"], type="password", disabled=True).upper().strip()
    else:
        solution = st.text_input("Solution", value=current_day_data["solution"]).upper().strip()
    st.write("---")

    for p_name in data["players"]:
        has_played = p_name in current_day_data["scores"]
        label = f"{ICON_CHECK} {p_name}: {current_day_data['scores'][p_name]['score']} pts" if has_played else f"{ICON_NOTE} {p_name} (Pending)"
        with st.expander(label, expanded=not has_played):
            with st.form(f"entry_{p_name}"):
                def_w = current_day_data["scores"][p_name].get("wrong_words_input", "") if has_played else ""
                guesses = st.radio("Guesses", [1,2,3,4,5,6,"Fail"], index=3, key=f"g_{p_name}_{date_str}", horizontal=True)
                wrong = st.text_area("Incorrect Words", value=def_w, key=f"w_{p_name}_{date_str}")
                if st.form_submit_button("Submit"):
                    if not solution: st.error("Solution required.")
                    else:
                        current_day_data["solution"] = solution
                        current_day_data["scores"][p_name] = {"guesses": guesses, "wrong_words_input": wrong, "base": 0, "score": 0}
                        if not existing_day: data["history"].insert(0, current_day_data)
                        with st.spinner("Syncing..."): new_data = recalculate_history(data); save_data(new_data)
                        st.success("Saved!"); st.rerun()

with tab_stats:
    st.subheader("📊 Analytics")
    
    if not data["history"]:
        st.info("Play some games to see stats!")
    else:
        stat_cols = st.columns(len(data["players"]))
        
        for i, (p_name, p_data) in enumerate(data["players"].items()):
            with stat_cols[i]:
                games = 0; wins = 0; total_guesses = 0; head_to_head_wins = 0; ties = 0
                counts = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, "Fail":0}
                
                for h in data["history"]:
                    if p_name in h["scores"]:
                        g = h["scores"][p_name].get("guesses")
                        games += 1
                        counts[g] += 1
                        if g != "Fail": wins += 1; total_guesses += g
                        
                        w_log = h.get("winner_log", "")
                        if f"{p_name} (+1)" in w_log: head_to_head_wins += 1
                        elif "Tie" in w_log: ties += 1

                avg = round(total_guesses / wins, 2) if wins > 0 else 0.0
                
                pill_htmls = []
                for k in [1, 2, 3, 4, 5, 6, "Fail"]:
                    val = counts[k]
                    css = "guess-pill" if val > 0 else "guess-pill zero"
                    pill_htmls.append(f'<div class="{css}">{k}: {val}</div>')
                pill_str = "".join(pill_htmls)

                html_block = f"""
<div class="stat-card">
    <div class="stat-header">{p_name}</div>
    <div class="stat-grid">
        <div class="stat-item"><span class="stat-label">Games</span><span class="stat-value">{games}</span></div>
        <div class="stat-item"><span class="stat-label">Avg</span><span class="stat-value">{avg}</span></div>
        <div class="stat-item"><span class="stat-label">H2H</span><span class="stat-value win">{head_to_head_wins}</span></div>
        <div class="stat-item"><span class="stat-label">Ties</span><span class="stat-value tie">{ties}</span></div>
    </div>
    <div class="guess-container">{pill_str}</div>
</div>
"""
                st.markdown(html_block, unsafe_allow_html=True)
                
        st.divider()

        # TUG OF WAR
        chronological = sorted(data["history"], key=lambda x: datetime.strptime(x["date"], "%Y-%m-%d"))
        running_scores = {p: 0 for p in data["players"]}
        trend_data = []
        
        for day in chronological:
            for p, s in day["scores"].items(): running_scores[p] += s["score"]
            if "winner_log" in day and "(+1)" in day["winner_log"]:
                winner = day["winner_log"].split(" ")[0]
                if winner in running_scores: running_scores[winner] += 1
            for p, score in running_scores.items():
                trend_data.append({"Date": day["date"], "Player": p, "Total Score": score})

        if trend_data:
            df_trend = pd.DataFrame(trend_data)
            line_chart = alt.Chart(df_trend).mark_line(point=True).encode(
                x=alt.X('Date:T', axis=alt.Axis(format='%b %d')),
                y='Total Score:Q',
                color='Player',
                tooltip=['Date', 'Player', 'Total Score']
            ).properties(title="Score History")
            st.altair_chart(line_chart, use_container_width=True)

with tab_history:
    st.subheader("Match History")
    for idx, h in enumerate(data["history"]):
        with st.container():
            c1, c2 = st.columns([4, 1])
            c1.write(f"**{h['date']}** | {h['solution']}")
            if "winner_log" in h: c1.caption(f"Result: {h['winner_log']}")
            with c2:
                unique_key = f"del_{h['date']}_{idx}"
                if st.button(f"{ICON_TRASH}", key=unique_key):
                    data["history"].pop(idx)
                    with st.spinner("Deleting..."): data = recalculate_history(data); save_data(data)
                    st.rerun()
            cols = st.columns(len(h["scores"])) if h["scores"] else [st.container()]
            for i, (p, stats) in enumerate(h["scores"].items()):
                with cols[i]:
                    is_win = (p in h.get('winner_log', '')) and ("+1" in h.get('winner_log', ''))
                    total = stats['score'] + (1 if is_win else 0)
                    st.write(f"{p}: **{total}**")
                    if stats.get('wrong_words_input'): st.caption(f"{ICON_CROSS} {stats['wrong_words_input']}")
            st.divider()

with tab_rules:
    st.header(f"{ICON_RULES} League Rules & Scoring")
    
    st.subheader("1. Base Scoring")
    st.markdown("""
    Points are awarded based on how quickly you solve the Wordle:
    * **1 Guess:** 10 pts
    * **2 Guesses:** 8 pts
    * **3 Guesses:** 6 pts
    * **4 Guesses:** 4 pts
    * **5 Guesses:** 2 pts
    * **6 Guesses:** 1 pt
    * **Fail:** 0 pts
    """)
    
    st.subheader("2. Penalties")
    st.markdown("""
    * **Burned Word Penalty:** **-2 pts** per word.
    * *Definition:* Entering a word in the "Incorrect Words" box that has **already been a solution** or was previously burned by another player.
    * *Grace Rule:* If you accidentally reuse a past solution, it is added to your burn list but you are not penalized points (Grace Used).
    """)
    
    st.subheader("3. Bonuses")
    st.markdown("""
    * **Daily Victory:** **+1 pt** for the player with the highest daily score (Base - Penalties + Streak).
    * *Tie Rule:* If scores are tied, no victory point is awarded.
    
    * **Clean Streak Bonus:**
        * If you have **0 Penalties** for the day, your Streak increases by 1.
        * **Tier 1 (Days 1-7):** +3 pts per day.
        * **Tier 2 (Days 8-14):** +6 pts per day.
        * **Tier 3 (Days 15+):** +9 pts per day.
    """)

with tab_library:
    st.subheader("Burned Word Library")
    cols = st.columns(len(data["players"]))
    for i, (p, val) in enumerate(data["players"].items()):
        with cols[i]:
            st.write(f"**{p}** ({len(val['burned'])})")
            st.caption(", ".join(sorted(val["burned"])))

# ADMIN
st.write(""); st.write("")
with st.expander(f"{ICON_GEAR} Admin & Roster"):
    c_add, c_del = st.columns(2)
    with c_add:
        new_player = st.text_input("New Name")
        if st.button("Add Player"):
            if new_player and new_player not in data["players"]:
                data["players"][new_player] = {"score": 0, "clean_days": 0, "burned": [], "past_solutions": []}
                save_data(data); st.rerun()
    with c_del:
        p_edit = st.selectbox("Select Player", options=list(data["players"].keys()))
        if st.button("Delete Player"): del data["players"][p_edit]; save_data(data); st.rerun()
    st.divider()
    if st.button("⚠️ Force Full Recalculate"):
        with st.spinner("Replaying History..."): data = recalculate_history(data); save_data(data)
        st.success("Done!"); st.rerun()
