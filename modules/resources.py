import streamlit as st


def show_resources():
    st.header("📚 Syllabus, Notes and PYQs")

    subjects = st.session_state.get("subjects", [])

    if not subjects:
        st.warning(
            "Please add your subjects in My Semester first."
        )
        return

    subject = st.selectbox(
        "Choose a subject",
        subjects,
        key="resource_subject"
    )

    resource_type = st.selectbox(
        "Resource type",
        [
            "Syllabus",
            "Study Notes",
            "Previous-Year Questions",
            "Reference Material"
        ]
    )

    uploaded_file = st.file_uploader(
        "Upload a PDF",
        type=["pdf"],
        key="resource_pdf"
    )

    if uploaded_file is not None:
        st.success(
            f"Uploaded: {uploaded_file.name}"
        )

        st.write("Subject:", subject)
        st.write("Resource type:", resource_type)

        st.download_button(
            "Download Uploaded PDF",
            data=uploaded_file.getvalue(),
            file_name=uploaded_file.name,
            mime="application/pdf"
        )

        st.info(
            "This prototype previews the resource upload. "
            "Permanent storage will be added through SQLite "
            "and a file-storage folder."
        )