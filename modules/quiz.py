import random
import streamlit as st


QUESTION_BANK = {
    "Machine Learning": [
        {
            "topic": "Supervised Learning",
            "question": "What is supervised learning?",
            "options": [
                "Learning from labeled data",
                "Learning without data",
                "Deleting training data",
                "Storing files"
            ],
            "answer": "Learning from labeled data",
            "explanation": (
                "Supervised learning uses labeled examples "
                "to learn input-output relationships."
            )
        },
        {
            "topic": "Regression",
            "question": "Which algorithm is commonly used for regression?",
            "options": [
                "Linear regression",
                "K-means",
                "Apriori",
                "Breadth-first search"
            ],
            "answer": "Linear regression",
            "explanation": (
                "Linear regression predicts a continuous value."
            )
        },
        {
            "topic": "Classification",
            "question": "What does classification predict?",
            "options": [
                "A category or class",
                "Only a file name",
                "A database password",
                "A computer's temperature"
            ],
            "answer": "A category or class",
            "explanation": (
                "Classification predicts discrete categories."
            )
        }
    ],

    "Database Management Systems": [
        {
            "topic": "Keys",
            "question": "What is a primary key?",
            "options": [
                "A field or set of fields that uniquely identifies a row",
                "A duplicate field",
                "A backup file",
                "A database password"
            ],
            "answer": (
                "A field or set of fields that uniquely identifies a row"
            ),
            "explanation": (
                "A primary key uniquely identifies each row."
            )
        },
        {
            "topic": "SQL",
            "question": "Which SQL command retrieves data?",
            "options": [
                "SELECT",
                "DELETE",
                "DROP",
                "ALTER"
            ],
            "answer": "SELECT",
            "explanation": (
                "SELECT retrieves records from a database."
            )
        }
    ],

    "Computer Networks": [
        {
            "topic": "Networking Devices",
            "question": "Which device forwards packets between networks?",
            "options": [
                "Router",
                "Keyboard",
                "Printer",
                "Scanner"
            ],
            "answer": "Router",
            "explanation": (
                "Routers forward packets between IP networks."
            )
        },
        {
            "topic": "Transport Layer",
            "question": "Which protocol provides reliable, ordered delivery?",
            "options": [
                "TCP",
                "UDP",
                "ARP",
                "ICMP"
            ],
            "answer": "TCP",
            "explanation": (
                "TCP provides reliable, ordered byte-stream delivery."
            )
        }
    ]
}


def show_quiz():
    st.header("🧠 Practice Quiz")

    subjects = st.session_state.get(
        "subjects",
        list(QUESTION_BANK.keys())
    )

    if not subjects:
        st.warning("Add your subjects first.")
        return

    subject = st.selectbox(
        "Select Subject",
        subjects,
        key="practice_subject"
    )

    available = QUESTION_BANK.get(subject, [])

    if not available:
        st.info(
            "No sample questions are available for this subject yet."
        )
        return

    count = st.selectbox(
        "Number of questions",
        list(range(1, len(available) + 1))
    )

    if st.button("Start Quiz"):
        st.session_state.active_questions = random.sample(
            available,
            count
        )
        st.session_state.quiz_subject = subject
        st.session_state.quiz_started = True
        st.session_state.quiz_submitted = False

    questions = st.session_state.get(
        "active_questions",
        []
    )

    if not questions:
        return

    with st.form("practice_quiz_form"):
        answers = []

        for i, question in enumerate(questions):
            st.write(
                f"**Q{i + 1}. {question['question']}**"
            )

            selected = st.radio(
                "Choose an answer",
                question["options"],
                index=None,
                key=f"question_answer_{i}"
            )

            answers.append(selected)

        submitted = st.form_submit_button(
            "Submit Quiz"
        )

    if submitted:
        score = 0
        topic_results = {}

        for question, answer in zip(
            questions,
            answers
        ):
            correct = answer == question["answer"]

            if correct:
                score += 1

            topic = question["topic"]

            if topic not in topic_results:
                topic_results[topic] = {
                    "correct": 0,
                    "total": 0
                }

            topic_results[topic]["total"] += 1

            if correct:
                topic_results[topic]["correct"] += 1

            st.write(f"**Topic:** {topic}")

            if correct:
                st.success("Correct!")
            else:
                st.error(
                    f"Correct answer: {question['answer']}"
                )

            st.caption(question["explanation"])

        percentage = round(
            score / len(questions) * 100
        )

        st.session_state.setdefault(
            "scores",
            {}
        )

        st.session_state.scores[subject] = percentage

        st.session_state.setdefault(
            "topic_scores",
            {}
        )

        for topic, result in topic_results.items():
            accuracy = round(
                result["correct"] /
                result["total"] * 100
            )

            st.session_state.topic_scores[
                f"{subject} - {topic}"
            ] = accuracy

        st.success(
            f"Final score: {score}/{len(questions)} "
            f"({percentage}%)"
        )