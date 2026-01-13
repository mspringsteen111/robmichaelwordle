import streamlit as st
import pandas as pd
import json
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

st.set_page_config(page_title="Wordle Competitive", page_icon=ICON_PUZZLE, layout="wide")

# --- MOBILE STYLING ---
def mobile_friendly_style():
    st.markdown("""
        <style>
        /* 1. Hide Footer/Header/Deploy/Decoration */
        footer {visibility: hidden;}
        .stDeployButton {display:none;}
        #stDecoration {display:none;}
        
        /* 2. Compact spacing */
        .block-container {
            padding-top: 1rem !important;
            padding-bottom: 3rem !important;
        }
        
        /* 3. CENTER THE TITLE */
        h1 { text-align: center; }
        
        /* 4. Mobile-friendly Buttons */
        div.stButton > button {
            width: 100%;
            border-radius: 12px;
            height: 3em;
            font-weight: bold;
        }
        
        /* 5. Input text size fix */
        input { font-size: 16px !important; }
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

    df_history = conn.read(worksheet="history")
    history_list = []
    df_history["Date"] = pd.to_datetime(df_history["Date"], errors="coerce")
    df_history = df_history.dropna(subset=["Date"])
    df_history = df_history.sort_values(by="Date", ascending=False)
    
    for index, row in df_history.iterrows():
        scores_data = json.loads(row["Scores_JSON"])
        history_list.append({
            "date": row["Date"].strftime("%Y-%m-%d"),
            "solution": row["Solution"],
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
    penalties = 0
    penalty_log = []
    new_burns_for_day = []
    wrong_words_list = [w.strip().upper() for w in wrong_words_str.split(",") if w.strip()]
    for word in wrong_words_list:
        if word in current_burned_set:
            penalties += 2; penalty_log.append(f"{word} (Burned)")
        elif word in current_solutions_set:
            penalty_log.append(f"{word} (Grace Used)"); new_burns_for_day.append(word) 
        else:
            new_burns_for_day.append(word) 
    is_clean = (penalties == 0)
    bonus = 0
    new_streak_val = current_streak
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
        sol = day["solution"]
        daily_perf = {}
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

# --- MAIN APP UI ---

# 1. LOAD DATA
data = load_data()

# 2. TITLE
st.title(f"{ICON_PUZZLE} Wordle League")

# 3. CUSTOM SCOREBOARD (HTML injection for exact control)
sorted_players = sorted(data["players"].items(), key=lambda x: x[1]['score'], reverse=True)
cols = st.columns(len(sorted_players))

for i, (name, p_data) in enumerate(sorted_players):
    with cols[i]:
        # WE BUILD THE BOX MANUALLY HERE
        st.markdown(f"""
        <div style="
            background-color: #f8f9fa; 
            border-radius: 10px; 
            padding: 10px; 
            text-align: center; 
            box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
            margin-bottom: 15px;">
            <div style="font-size: 1.8rem; font-weight: 900; color: black; margin-bottom: -10px;">
                {name}
            </div>
            <div style="font-size: 3.5rem; font-weight: 800; color: #FF4B4B; line-height: 1.2;">
                {p_data['score']}
            </div>
            <div style="font-size: 1.1rem; font-weight: bold; color: #006600;">
                Streak: {p_data['clean_days']}
            </div>
        </div>
        """, unsafe_allow_html=True)

st.write("---")

# 4. ACTION BAR
st.caption(f"{ICON_FIRE} **BURN CHECKER**") 
c1, c2 = st.columns([1, 1])
with c1:
    search_term = st.text_input("Burn Checker", placeholder="Check word...", label_visibility="collapsed").upper().strip()
with c2:
    if st.button(f"{ICON_REFRESH} Check for Updates", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

if search_term:
    found_any = False
    res_cols = st.columns(len(data["players"]))
    for i, (p_name, p_data) in enumerate(data["players"].items()):
        with res_cols[i]:
            if search_term in p_data["burned"]:
                st.error(f"{p_name}: BURNED"); found_any = True
            else:
                st.success(f"{p_name}: Safe")
    if not found_any: st.caption(f"'{search_term}' is safe.")
    st.write("---")

# 5. TABS
tab_play, tab_history, tab_library = st.tabs([f"{ICON_CALENDAR} Daily", f"{ICON_SCROLL} History", f"{ICON_BOOKS} Library"])

with tab_play:
    # --- NEW MOBILE DATE NAVIGATION ---
    if 'curr_date' not in st.session_state:
        st.session_state.curr_date = date.today()

    # Create 3 columns: Previous Button | Date Display | Next Button
    d_col1, d_col2, d_col3 = st.columns([1, 2, 1])
    
    with d_col1:
        if st.button("◀", use_container_width=True):
            st.session_state.curr_date -= timedelta(days=1)
            st.rerun()
    with d_col3:
        if st.button("▶", use_container_width=True):
            st.session_state.curr_date += timedelta(days=1)
            st.rerun()
    with d_col2:
        # Display date nicely centered
        st.markdown(f"<h3 style='text-align: center; margin: 0;'>{st.session_state.curr_date.strftime('%b %d')}</h3>", unsafe_allow_html=True)
        # Small fallback picker if they really need to jump far
        new_date = st.date_input("Jump to date", value=st.session_state.curr_date, label_visibility="collapsed")
        if new_date != st.session_state.curr_date:
            st.session_state.curr_date = new_date
            st.rerun()

    date_str = str(st.session_state.curr_date)
    # ----------------------------------

    existing_day = next((item for item in data["history"] if item["date"] == date_str), None)
    
    if not existing_day:
        current_day_data = {"date": date_str, "solution": "", "victory_awarded": False, "scores": {}}
    else:
        current_day_data = existing_day

    # Spoiler Logic
    players_done_count = len(current_day_data["scores"])
    total_players = len(data["players"])
    is_in_progress = (players_done_count > 0) and (players_done_count < total_players)
    show_spoiler = st.checkbox("Show Solution", value=False)
    
    if is_in_progress and not show_spoiler:
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
                    if not solution:
                        st.error("Solution required.")
                    else:
                        current_day_data["solution"] = solution
                        current_day_data["scores"][p_name] = {"guesses": guesses, "wrong_words_input": wrong, "base": 0, "score": 0}
                        if not existing_day: data["history"].insert(0, current_day_data)
                        
                        with st.spinner("Syncing..."):
                            new_data = recalculate_history(data)
                            save_data(new_data)
                        st.success("Saved!")
                        st.rerun()

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
                    with st.spinner("Deleting..."):
                        data = recalculate_history(data)
                        save_data(data)
                    st.rerun()
            cols = st.columns(len(h["scores"])) if h["scores"] else [st.container()]
            for i, (p, stats) in enumerate(h["scores"].items()):
                with cols[i]:
                    is_win = (p in h.get('winner_log', '')) and ("+1" in h.get('winner_log', ''))
                    total = stats['score'] + (1 if is_win else 0)
                    st.write(f"{p}: **{total}**")
                    if stats.get('wrong_words_input'): st.caption(f"{ICON_CROSS} {stats['wrong_words_input']}")
            st.divider()

with tab_library:
    st.subheader("Burned Word Library")
    cols = st.columns(len(data["players"]))
    for i, (p, val) in enumerate(data["players"].items()):
        with cols[i]:
            st.write(f"**{p}** ({len(val['burned'])})")
            st.caption(", ".join(sorted(val["burned"])))

# 6. ADMIN
st.write("")
st.write("")
with st.expander(f"{ICON_GEAR} Admin & Roster"):
    st.write("Manage Players")
    c_add, c_del = st.columns(2)
    with c_add:
        new_player = st.text_input("New Name")
        if st.button("Add Player"):
            if new_player and new_player not in data["players"]:
                data["players"][new_player] = {"score": 0, "clean_days": 0, "burned": [], "past_solutions": []}
                save_data(data)
                st.rerun()
    with c_del:
        p_edit = st.selectbox("Select Player", options=list(data["players"].keys()))
        if st.button("Delete Player"):
            del data["players"][p_edit]; save_data(data); st.rerun()
    st.divider()
    if st.button("⚠️ Force Full Recalculate"):
        with st.spinner("Replaying History..."):
            data = recalculate_history(data); save_data(data)
        st.success("Done!"); st.rerun()
