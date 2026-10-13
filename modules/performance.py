import streamlit as st


def classify_score(score):
    if score >= 80:
        return "Strong"

    if score >= 65:
        return "Good"

    if score >= 40:
        return "Needs Improvement"

    return "High Priority"


def show_performance():
    st.header("📊 Performance Analysis")

    scores = st.session_state.get("scores", {})

    subjects = st.session_state.get("subjects", [])

    if not subjects:
        st.info(
            "Add your subjects in My Semester first."
        )
        return

    if not scores:
        st.info(
            "Take a quiz to see your performance analysis."
        )
        return

    for subject in subjects:
        if subject not in scores:
            st.write(
                f"📘 **{subject}** — Not assessed yet"
            )
            continue

        score = scores[subject]
        classification = classify_score(score)

        st.subheader(subject)

        st.progress(score / 100)

        st.write(f"Latest score: {score}%")
        st.write(f"Classification: {classification}")

        if score < 40:
            st.warning(
                "Revise fundamental concepts and take a practice quiz."
            )
        elif score < 65:
            st.info(
                "Practice more questions and review mistakes."
            )
        elif score < 80:
            st.info(
                "Strengthen difficult topics and practice exam questions."
            )
        else:
            st.success(
                "Good performance. Continue revision to retain knowledge."
            )

    st.subheader("Topics Requiring Attention")

    topic_scores = st.session_state.get(
        "topic_scores",
        {}
    )

    weak_topics = sorted(
        topic_scores.items(),
        key=lambda item: item[1]
    )

    if not weak_topics:
        st.info(
            "Complete more topic-tagged quizzes to identify weak topics."
        )
    else:
        for topic, score in weak_topics:
            if score < 65:
                st.warning(
                    f"{topic}: {score}% — prioritize revision"
                )