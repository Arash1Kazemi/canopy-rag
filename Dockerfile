# Use lightweight Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy dependency files and project code
COPY pyproject.toml requirements.txt ./
COPY rag_core/ ./rag_core/
COPY baseline_runner/ ./baseline_runner/
COPY tests/ ./tests/
COPY case_study/ ./case_study/
COPY registry/ ./registry/
COPY metrics/ ./metrics/
COPY glossary/ ./glossary/
COPY scope/ ./scope/
COPY prompts/ ./prompts/
COPY pytest.ini ./

# Install python package and dependencies
RUN pip install --no-cache-dir -e .

# Run pytest by default to test inside the container
CMD ["pytest"]
