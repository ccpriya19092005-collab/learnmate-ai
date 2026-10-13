import streamlit as st


def show_ai_advisor():
    st.header("🤖 My Study Advisor")

    subjects = st.session_state.get("subjects", [])
    scores = st.session_state.get("scores", {})
    topic_scores = st.session_state.get(
        "topic_scores",
        {}
    )

    if not subjects:
        st.warning(
            "Add your subjects to get recommendations."
        )
        return

    st.write(
        "Ask for study recommendations based on your performance."
    )

    question = st.text_input(
        "What would you like help with?",
        placeholder="Which subject should I study today?"
    )

    if st.button("Get Recommendation"):
        if not scores:
            st.info(
                "Take a quiz first so I can assess your performance."
            )
            return

        assessed = [
            (subject, scores[subject])
            for subject in subjects
            if subject in scores
        ]

        if not assessed:
            st.info(
                "No assessed subjects are available yet."
            )
            return

        weakest_subject, weakest_score = min(
            assessed,
            key=lambda item: item[1]
        )

        st.subheader("Your Recommendation")

        st.write(
            f"Prioritize **{weakest_subject}** "
            f"because your latest recorded score is "
            f"{weakest_score}%."
        )

        weak_topics = [
            (topic, score)
            for topic, score in topic_scores.items()
            if score < 65
        ]

        if weak_topics:
            st.write("### Topics to Revise")

            for topic, score in sorted(
                weak_topics,
                key=lambda item: item[1]
            ):
                st.write(
                    f"- {topic}: {score}%"
                )

        st.write("### Suggested Next Steps")

        st.write(
            "1. Review the relevant notes.\n"
            "2. Practice questions on your weakest topics.\n"
            "3. Review incorrect answers.\n"
            "4. Take another quiz to measure improvement."
        )

        if question:
            st.caption(
                "This recommendation is based on your "
                "recorded scores, not a full AI language model."
            )