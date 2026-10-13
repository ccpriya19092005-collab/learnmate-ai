import streamlit as st


def show_subject_setup():
    st.header("🎓 My Semester")

    course = st.text_input(
        "Course",
        value="B.E. Computer Science"
    )

    semester = st.selectbox(
        "Select Semester",
        list(range(1, 9)),
        index=4
    )

    subjects_text = st.text_area(
        "Enter your subjects, one per line",
        value=(
            "Machine Learning\n"
            "Computer Networks\n"
            "Database Management Systems\n"
            "Software Engineering\n"
            "Theory of Computation"
        )
    )

    if st.button("Save Semester Details"):
        subjects = [
            subject.strip()
            for subject in subjects_text.splitlines()
            if subject.strip()
        ]

        st.session_state.course = course
        st.session_state.semester = semester
        st.session_state.subjects = subjects

        st.success("Semester details saved!")

        st.write("### Your Subjects")

        for subject in subjects:
            st.write(f"📘 {subject}")