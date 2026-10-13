import streamlit as st


def show_study_planner():
    st.header("📅 Personalized Study Planner")

    subjects = st.session_state.get("subjects", [])

    if not subjects:
        st.warning(
            "Add your subjects in My Semester first."
        )
        return

    hours = st.number_input(
        "Available study hours per day",
        min_value=1.0,
        max_value=16.0,
        value=3.0,
        step=0.5
    )

    scores = st.session_state.get("scores", {})

    st.subheader("Today's Recommended Plan")

    priorities = []

    for subject in subjects:
        score = scores.get(subject)

        if score is None:
            priority = 1.0
            reason = "Not assessed yet"
        else:
            priority = max(
                0.1,
                (100 - score) / 100
            )
            reason = f"Latest quiz score: {score}%"

        priorities.append(
            (subject, priority, reason)
        )

    total_priority = sum(
        priority
        for _, priority, _ in priorities
    )

    total_minutes = int(hours * 60)

    allocations = []

    for subject, priority, reason in priorities:
        minutes = round(
            total_minutes * priority / total_priority
        )

        allocations.append(
            (subject, minutes, reason)
        )

    # Correct rounding differences so the total matches.
    difference = total_minutes - sum(
        minutes for _, minutes, _ in allocations
    )

    if allocations:
        subject, minutes, reason = allocations[0]

        allocations[0] = (
            subject,
            minutes + difference,
            reason
        )

    for subject, minutes, reason in allocations:
        st.write(f"### 📘 {subject}")

        st.write(
            f"Recommended study time: {minutes} minutes"
        )

        st.caption(reason)

    st.info(
        "This is a basic score-based planner. "
        "Exam dates, syllabus coverage, topic difficulty, "
        "and PYQ frequency can be added to improve priorities."
    )