const API_BASE =
    "http://127.0.0.1:8000";

let currentResumeText = "";

// =====================================
// DOM ELEMENTS
// =====================================

const recommendBtn =
    document.getElementById(
        "recommend-btn"
    );

const refineBtn =
    document.getElementById(
        "refine-btn"
    );

const resumeInput =
    document.getElementById(
        "resume-text"
    );

const userFeedbackInput =
    document.getElementById(
        "user-feedback"
    );


// =====================================
// RECOMMENDATION FLOW
// =====================================

recommendBtn.addEventListener(
    "click",
    async () => {

        const resumeText =
            resumeInput.value.trim();

        if (!resumeText) {

            alert(
                "Please paste resume text"
            );

            return;
        }

        currentResumeText =
            resumeText;

        try {

            recommendBtn.disabled = true;

            recommendBtn.innerText =
                "Generating...";

            const response = await fetch(
                `${API_BASE}/recommend`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({
                        resume_text:
                            resumeText
                    })
                }
            );

            const data =
                await response.json();

            console.log(data);

            renderCandidate(
                data.candidate
            );

            renderJobs(
                data.ranked_jobs
            );

            showClarificationQuestion(
                data.clarifying_question
            );

        } catch (error) {

            console.error(error);

            alert(
                "Failed to generate recommendations"
            );

        } finally {

            recommendBtn.disabled = false;

            recommendBtn.innerText =
                "Generate Recommendations";
        }
    }
);


// =====================================
// REFINE FLOW
// =====================================

refineBtn.addEventListener(
    "click",
    async () => {

        const feedback =
            userFeedbackInput.value.trim();

        if (!feedback) {

            alert(
                "Please answer the clarifying question"
            );

            return;
        }

        try {

            refineBtn.disabled = true;

            refineBtn.innerText =
                "Refining...";

            const response = await fetch(
                `${API_BASE}/refine`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body: JSON.stringify({

                        resume_text:
                            currentResumeText,

                        user_feedback:
                            feedback
                    })
                }
            );

            const data =
                await response.json();

            console.log(data);

            renderJobs(
                data.ranked_jobs
            );

        } catch (error) {

            console.error(error);

            alert(
                "Failed to refine recommendations"
            );

        } finally {

            refineBtn.disabled = false;

            refineBtn.innerText =
                "Refine Recommendations";
        }
    }
);


// =====================================
// RENDER CANDIDATE
// =====================================

function renderCandidate(
    candidate
) {

    const section =
        document.getElementById(
            "candidate-section"
        );

    const container =
        document.getElementById(
            "candidate-info"
        );

    section.classList.remove(
        "hidden"
    );

    let skillsHTML = "";

    if (
        candidate.skills &&
        candidate.skills.length
    ) {

        candidate.skills.forEach(
            skill => {

                skillsHTML += `
                    <span class="skill">
                        ${skill}
                    </span>
                `;
            }
        );
    }

    container.innerHTML = `

        <p>
            <strong>Name:</strong>
            ${candidate.name}
        </p>

        <p>
            <strong>Experience:</strong>
            ${candidate.experience_years} years
        </p>

        <p>
            <strong>Education:</strong>
            ${candidate.education}
        </p>

        <div style="margin-top:12px;">
            <strong>Skills:</strong>
            <div>
                ${skillsHTML}
            </div>
        </div>
    `;
}


// =====================================
// RENDER JOBS
// =====================================

function renderJobs(
    jobs
) {

    const section =
        document.getElementById(
            "results-section"
        );

    const container =
        document.getElementById(
            "results"
        );

    section.classList.remove(
        "hidden"
    );

    container.innerHTML = "";

    jobs.forEach(job => {

        container.innerHTML += `

            <div class="job-card">

                <h3>
                    ${job.title}
                </h3>

                <p>
                    <strong>Company:</strong>
                    ${job.company}
                </p>

                <p>
                    <strong>Similarity Score:</strong>
                    ${job.similarity_score}
                </p>

                <p>
                    <strong>Explanation:</strong>
                    ${job.explanation}
                </p>

            </div>
        `;
    });
}


// =====================================
// SHOW QUESTION
// =====================================

function showClarificationQuestion(
    question
) {

    const section =
        document.getElementById(
            "clarification-section"
        );

    const questionElement =
        document.getElementById(
            "clarifying-question"
        );

    section.classList.remove(
        "hidden"
    );

    questionElement.innerText =
        question;
}
