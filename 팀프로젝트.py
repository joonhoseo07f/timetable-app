from ortools.sat.python import cp_model
import streamlit as st
import os
import json
from datetime import datetime
from collections import Counter

st.set_page_config(page_title="시험 시간표 최적화 - OR-Tools", layout="wide")
st.title("🗓️ 시험 시간표 최적화 웹앱 (OR-Tools 기반)")

def generate_timetable_ortools(subjects, difficulties, num_days, max_per_day, exclude_weekend, scenario):
    model = cp_model.CpModel()
    n = len(subjects)
    day_vars = [model.NewIntVar(0, num_days - 1, f'day_{i}') for i in range(n)]

    for day in range(num_days):
        is_on_day = []
        for i in range(n):
            is_on_this_day = model.NewBoolVar(f'is_subject_{i}_on_day_{day}')
            model.Add(day_vars[i] == day).OnlyEnforceIf(is_on_this_day)
            model.Add(day_vars[i] != day).OnlyEnforceIf(is_on_this_day.Not())
            is_on_day.append(is_on_this_day)
        model.Add(sum(is_on_day) <= max_per_day)

    if exclude_weekend:
        weekend_days = [5, 6]
        for i in range(n):
            for wd in weekend_days:
                if wd < num_days:
                    model.Add(day_vars[i] != wd)

    if scenario == "초반에 어려운 과목 몰아서 끝내기":
        for i in range(n):
            for j in range(n):
                if difficulties[subjects[i]] > difficulties[subjects[j]]:
                    model.Add(day_vars[i] <= day_vars[j])
    elif scenario == "쉬운 과목 먼저 배치":
        for i in range(n):
            for j in range(n):
                if difficulties[subjects[i]] < difficulties[subjects[j]]:
                    model.Add(day_vars[i] <= day_vars[j])
    elif scenario == "난이도 고르게 분산":
        day_difficulty_sums = []
        for d in range(num_days):
            in_day = []
            for i in range(n):
                b = model.NewBoolVar(f'subject_{i}_in_day_{d}')
                model.Add(day_vars[i] == d).OnlyEnforceIf(b)
                model.Add(day_vars[i] != d).OnlyEnforceIf(b.Not())
                in_day.append(b)
            day_diff = model.NewIntVar(0, sum(difficulties.values()), f'day_{d}_difficulty_sum')
            model.Add(day_diff == sum([difficulties[subjects[i]] * in_day[i] for i in range(n)]))
            day_difficulty_sums.append(day_diff)
        max_diff_sum = model.NewIntVar(0, sum(difficulties.values()), "max_diff_sum")
        min_diff_sum = model.NewIntVar(0, sum(difficulties.values()), "min_diff_sum")
        model.AddMaxEquality(max_diff_sum, day_difficulty_sums)
        model.AddMinEquality(min_diff_sum, day_difficulty_sums)
        model.Minimize(max_diff_sum - min_diff_sum)

    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        timetable = [[] for _ in range(num_days)]
        for i in range(n):
            day = solver.Value(day_vars[i])
            timetable[day].append(subjects[i])
        return timetable
    else:
        return None

st.header("1. 사용자 입력")

name = st.text_input("이름 또는 닉네임을 입력하세요").strip()

subjects = st.multiselect(
    "시험 과목을 선택하세요",
    ['국어', '수학', '영어', '화학', '생명과학', '물리', '지구과학']
)

difficulties = {}
if subjects:
    st.subheader("과목별 난이도 (1~7)")
    for subject in subjects:
        difficulties[subject] = st.slider(f"{subject} 난이도", 1, 7, 4)

st.subheader("제약조건 설정")
num_days = st.slider("시험을 며칠에 걸쳐 보고 싶나요?", 1, 7, 4)
max_per_day = st.slider("하루 최대 시험 과목 수", 1, 5, 2)
exclude_weekend = st.checkbox("주말을 제외하고 싶어요", value=True)

scenario = st.selectbox(
    "시험 순서 시나리오를 선택하세요",
    [
        "초반에 어려운 과목 몰아서 끝내기",
        "쉬운 과목 먼저 배치",
        "난이도 고르게 분산"
    ]
)

if st.button("📅 시간표 생성 및 저장"):
    if not name:
        st.warning("이름을 입력해주세요.")
    elif not subjects:
        st.warning("시험 과목을 한 개 이상 선택해주세요.")
    else:
        timetable = generate_timetable_ortools(subjects, difficulties, num_days, max_per_day, exclude_weekend, scenario)

        if timetable is None:
            st.error("조건을 만족하는 시간표를 찾지 못했습니다. 제약조건을 다시 확인해주세요.")
        else:
            result = {
                "이름": name,
                "시간표": timetable,
                "과목난이도": difficulties,
                "시나리오": scenario,
                "생성시간": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            filepath = "saved_timetables.json"
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
            else:
                saved = []

            saved.append(result)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(saved, f, indent=4, ensure_ascii=False)

            st.success("✅ 시간표가 저장되었습니다!")

            st.subheader(f"🎯 {name} 님의 시간표")
            for i, day in enumerate(timetable):
                st.markdown(f"**Day {i+1}**: {', '.join(day)}")

st.header("2. 실시간 인기 시간표 분석")

def normalize_timetable(timetable):
    return " / ".join(["|".join(sorted(day)) for day in timetable])

def find_most_common_timetables(json_path):
    if not os.path.exists(json_path):
        return []
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    counter = Counter()
    pattern_map = {}

    for entry in data:
        pattern = normalize_timetable(entry['시간표'])
        counter[pattern] += 1
        if pattern not in pattern_map:
            pattern_map[pattern] = entry['시간표']

    most_common = counter.most_common(3)
    return [(pattern_map[p], c) for p, c in most_common]

popular = find_most_common_timetables("saved_timetables.json")

if popular:
    st.subheader("🔥 가장 많이 선택된 시간표 TOP 3")
    for idx, (tt, count) in enumerate(popular):
        st.markdown(f"### #{idx+1} - 등장 {count}회")
        for i, day in enumerate(tt):
            st.markdown(f"**Day {i+1}**: {', '.join(day)}")
        st.markdown("---")
else:
    st.info("아직 저장된 시간표가 없습니다.")
