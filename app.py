import streamlit as st
from src import config, database, generator, utils

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------

st.set_page_config(
    page_title="SportIQ",
    page_icon="🏆",
    layout="wide"
)

utils.setup_logging()

# ---------------------------------------------------
# CSS
# ---------------------------------------------------

st.markdown("""
<style>

.block-container{
    max-width:900px;
    padding-top:2rem;
}

footer{
visibility:hidden;
}

.question{
    font-size:28px;
    font-weight:700;
    margin-bottom:25px;
}

.answer-box{
    padding:15px;
    border-radius:10px;
    background:#f8f9fa;
    border-left:5px solid #0d6efd;
    margin-top:15px;
}

.stButton>button{
    border-radius:10px;
}

</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------
# DATABASE
# ---------------------------------------------------

@st.cache_resource
def load_database():

    client = database.initialize_database()

    database.populate_database(
        client,
        force_repopulate=False
    )

    return client


db_client = load_database()

# ---------------------------------------------------
# SESSION STATE
# ---------------------------------------------------

if "quiz_result" not in st.session_state:
    st.session_state.quiz_result = None

if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}

if "submitted" not in st.session_state:
    st.session_state.submitted = False

if "current_question" not in st.session_state:
    st.session_state.current_question = 0

# ---------------------------------------------------
# SIDEBAR
# ---------------------------------------------------

with st.sidebar:

    st.title("🏆 SportIQ")

    st.divider()

    sport = st.selectbox(
        "Sport",
        [
            "Cricket",
            "Football",
            "Basketball",
            "Tennis",
            "Badminton",
            "Formula 1",
            "Olympics"
        ]
    )

    difficulty = st.selectbox(
        "Difficulty",
        [
            "Easy",
            "Medium",
            "Hard"
        ]
    )

    st.divider()

    generate_quiz = st.button(
        "🚀 Generate Quiz",
        use_container_width=True,
        type="primary"
    )

# ---------------------------------------------------
# TITLE
# ---------------------------------------------------

st.title("🏆 SportIQ")
st.caption("Sports Quiz Generator")

# ---------------------------------------------------
# GENERATE QUIZ
# ---------------------------------------------------

if generate_quiz:

    st.session_state.quiz_result = None
    st.session_state.user_answers = {}
    st.session_state.submitted = False
    st.session_state.current_question = 0

    with st.spinner("Generating Quiz..."):

        result = generator.generate_quiz_rag(
            sport=sport,
            difficulty=difficulty,
            db_client=db_client,
            provider=config.LLM_PROVIDER,
            api_key=config.LLM_API_KEY,
            base_url=config.LLM_BASE_URL,
            model=config.LLM_MODEL
        )

    if result["status"] == "success":

        st.session_state.quiz_result = result

    elif result["status"] == "insufficient_context":

        st.warning(result["error_message"])

    else:

        st.error(result["error_message"])
        # ---------------------------------------------------
# QUIZ SCREEN
# ---------------------------------------------------

if st.session_state.quiz_result:

    quiz = st.session_state.quiz_result["quiz"]
    questions = quiz["questions"]

    total_questions = len(questions)
    current = st.session_state.current_question

    # Progress
    st.progress((current + 1) / total_questions)

    st.markdown(
        f"### Question {current + 1} of {total_questions}"
    )

    question = questions[current]

    st.markdown(
        f"<div class='question'>{question['question']}</div>",
        unsafe_allow_html=True
    )

    options = question["options"]

    option_strings = [
        f"{key}: {value}"
        for key, value in options.items()
    ]

    previous_answer = st.session_state.user_answers.get(current)

    default_index = None

    if previous_answer:

        letters = list(options.keys())

        if previous_answer in letters:
            default_index = letters.index(previous_answer)

    selected = st.radio(
        "Choose your answer",
        option_strings,
        index=default_index,
        key=f"question_{current}",
        disabled=st.session_state.submitted
    )

    if selected:

        st.session_state.user_answers[current] = selected.split(":")[0]

    st.write("")

    # -----------------------------
    # Navigation Buttons
    # -----------------------------

    if not st.session_state.submitted:

        if current == 0:

            left, center, right = st.columns([1,2,1])

            with center:

                if st.button(
                    "Next ▶",
                    use_container_width=True
                ):

                    if current < total_questions - 1:

                        st.session_state.current_question += 1
                        st.rerun()

        elif current == total_questions - 1:

            left, center, right = st.columns(3)

            with left:

                if st.button(
                    "◀ Previous",
                    use_container_width=True
                ):

                    st.session_state.current_question -= 1
                    st.rerun()

            with right:

                if st.button(
                    "✅ Submit Quiz",
                    type="primary",
                    use_container_width=True
                ):

                    st.session_state.submitted = True
                    st.rerun()

        else:

            left, right = st.columns(2)

            with left:

                if st.button(
                    "◀ Previous",
                    use_container_width=True
                ):

                    st.session_state.current_question -= 1
                    st.rerun()

            with right:

                if st.button(
                    "Next ▶",
                    use_container_width=True
                ):

                    st.session_state.current_question += 1
                    st.rerun()
                    # ---------------------------------------------------
# RESULTS
# ---------------------------------------------------

if (
    st.session_state.quiz_result
    and st.session_state.submitted
):

    st.divider()

    quiz = st.session_state.quiz_result["quiz"]
    questions = quiz["questions"]

    # Calculate Score
    score = 0

    for i, question in enumerate(questions):

        user_answer = st.session_state.user_answers.get(i, None)
        correct_answer = question["answer"]

        if user_answer is not None and user_answer == correct_answer:
            score += 1

    st.success(f"🎉 Your Score: {score} / {len(questions)}")

    st.progress(score / len(questions))

    # Performance Message
    percentage = (score / len(questions)) * 100

    if percentage >= 85:
        st.balloons()
        st.success("🏆 Excellent! You're a Sports Expert.")
    elif percentage >= 60:
        st.info("👏 Good Job! Keep it up.")
    else:
        st.warning("📚 Keep Practicing! You'll improve.")

    st.divider()

    # Show Results
    for i, question in enumerate(questions):

        st.markdown(f"### Question {i+1}")

        st.write(question["question"])

        user_answer = st.session_state.user_answers.get(i, None)
        correct_answer = question["answer"]

        if user_answer is None:

            st.warning("⚪ Not Answered")

        elif user_answer == correct_answer:

            st.success("✅ Correct")

        else:

            st.error("❌ Incorrect")

        if user_answer:

            st.write(
                f"**Your Answer:** {user_answer}: {question['options'][user_answer]}"
            )

        else:

            st.write("**Your Answer:** Not Answered")

        st.write(
            f"**Correct Answer:** {correct_answer}: {question['options'][correct_answer]}"
        )

        if question.get("explanation"):

            st.info(question["explanation"])

        st.divider()

    # Generate New Quiz Button
    col1, col2, col3 = st.columns([2, 1, 2])

    with col2:

        if st.button(
            "🔄 Generate New Quiz",
            use_container_width=True,
            type="primary"
        ):

            st.session_state.quiz_result = None
            st.session_state.user_answers = {}
            st.session_state.current_question = 0
            st.session_state.submitted = False

            st.rerun()
