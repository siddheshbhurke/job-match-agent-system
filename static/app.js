async function analyzeResume() {

    const resumeText =
        document.getElementById(
            "resumeText"
        ).value;

    const resultsDiv =
        document.getElementById(
            "results"
        );

    const loadingDiv =
        document.getElementById(
            "loading"
        );

    resultsDiv.innerHTML = "";
    loadingDiv.style.display = "block";

    try {

        const response = await fetch(
            "/recommend",
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json"
                },
                body: JSON.stringify({
                    resume_text: resumeText
                })
            }
        );

        const data = await response.json();

        loadingDiv.style.display = "none";

        let html = `
            <h2>Candidate Profile</h2>

            <div class="job-card">
                <p><strong>Name:</strong>
                ${data.candidate.name}</p>

                <p><strong>Skills:</strong>
                ${data.candidate.skills.join(", ")}</p>

                <p><strong>Preferred Roles:</strong>
                ${data.candidate.preferred_roles.join(", ")}</p>
            </div>

            <h2>Recommended Jobs</h2>
        `;

        data.ranked_jobs.forEach(job => {

            html += `
                <div class="job-card">

                    <div class="job-title">
                        ${job.title}
                    </div>

                    <div class="company">
                        ${job.company}
                    </div>

                    <div class="score">
                        Match Score:
                        ${job.similarity_score}
                    </div>

                    <div class="explanation">
                        ${job.explanation}
                    </div>

                </div>
            `;
        });

        html += `
            <div class="job-card">
                <strong>Clarifying Question:</strong>
                ${data.clarifying_question}
            </div>
        `;

        resultsDiv.innerHTML = html;

    } catch (error) {

        loadingDiv.style.display = "none";

        resultsDiv.innerHTML = `
            <div class="job-card">
                Error processing resume.
            </div>
        `;
    }
}
