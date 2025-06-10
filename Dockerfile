FROM python:3.10-slim

# Install OpenSCAD CLI and required system libraries for headless OpenSCAD
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openscad libgl1 libglu1-mesa xvfb \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
# Copy and install Python dependencies (will use prebuilt wheels, no compilers needed)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Ensure OpenSCAD runs headlessly
ENV OPENSCAD_NO_GUI=1

# Expose HF Spaces default port
EXPOSE 7860

# Launch the Streamlit app
CMD ["streamlit","run","streamlit_app.py","--server.port","7860","--server.address","0.0.0.0"] 