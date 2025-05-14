import streamlit as st
from openai import OpenAI
import subprocess
import tempfile
import os
from dotenv import load_dotenv
import trimesh
import plotly.graph_objects as go
import re

# Load environment variables from .env
load_dotenv(override=True)
title = "3D Designer Agent"

# Set the Streamlit layout to wide
st.set_page_config(page_title=title, layout="wide")

# Initialize OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM_PROMPT = (
    "You are an expert in OpenSCAD. Given a user prompt describing a 3D printable model, "
    "generate a parametric OpenSCAD script that fulfills the description. "
    "Only return the raw .scad code without any explanations or markdown formatting."
)


def generate_scad(prompt: str) -> str:
    """
    Uses OpenAI API to generate OpenSCAD code from a user prompt.
    """
    # Build conversation messages including history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in st.session_state.get("history", []):
        if "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model="o4-mini",
        messages=messages,
        max_completion_tokens=4500,
    )
    code = response.choices[0].message.content.strip()
    return code


def generate_3d_files(scad_path: str, formats: list[str] = ["stl", "3mf"]) -> dict[str, str]:
    """
    Generate 3D files from a SCAD file using OpenSCAD CLI for specified formats.
    Returns a mapping from format extension to output file path.
    Throws CalledProcessError on failure.
    """
    paths: dict[str, str] = {}
    for fmt in formats:
        output_path = scad_path.replace(".scad", f".{fmt}")
        subprocess.run(["openscad", "-o", output_path, scad_path], check=True, capture_output=True, text=True)
        paths[fmt] = output_path
    return paths


def parse_scad_parameters(code: str) -> dict[str, float]:
    params: dict[str, float] = {}
    for line in code.splitlines():
        m = re.match(r"(\w+)\s*=\s*([0-9\.]+)\s*;", line)
        if m:
            params[m.group(1)] = float(m.group(2))
    return params


def apply_scad_parameters(code: str, params: dict[str, float]) -> str:
    def repl(match):
        name = match.group(1)
        if name in params:
            return f"{name} = {params[name]};"
        return match.group(0)
    return re.sub(r"(\w+)\s*=\s*[0-9\.]+\s*;", repl, code)


# Dialog for downloading model in chosen format
@st.dialog("Download Model")
def download_model_dialog(stl_path: str, threemf_path: str):
    choice = st.radio("Choose file format", ["STL", "3MF"] )
    if choice == "STL":
        with open(stl_path, "rb") as f:
            st.download_button(
                label="Download STL File", data=f, file_name="model.stl",
                mime="application/sla", on_click="ignore"
            )
    else:
        with open(threemf_path, "rb") as f:
            st.download_button(
                label="Download 3MF File", data=f, file_name="model.3mf",
                mime="application/octet-stream", on_click="ignore"
            )
    if st.button("Close"):
        st.rerun()


def main():
    # Sidebar for custom OpenAI API key
    api_key = st.sidebar.text_input("OpenAI API Key", type="password", value=os.getenv("OPENAI_API_KEY", ""))
    if api_key:
        client.api_key = api_key

    # Display large app logo and updated title
    st.logo("logo.png", size="large")
    st.title(title)
    st.write("Enter a description for your 3D model, and this app will generate an STL file using OpenSCAD and OpenAI.")

    # Initialize chat history
    if "history" not in st.session_state:
        st.session_state.history = []

    # Replay full conversation history
    for idx, msg in enumerate(st.session_state.history):
        with st.chat_message(msg["role"]):
            if msg["role"] == "user":
                st.write(msg["content"])
            else:
                with st.expander("Generated OpenSCAD Code", expanded=False):
                    st.code(msg["scad_code"], language="c")
                mesh = trimesh.load(msg["stl_path"])
                fig = go.Figure(data=[go.Mesh3d(
                    x=mesh.vertices[:,0], y=mesh.vertices[:,1], z=mesh.vertices[:,2],
                    i=mesh.faces[:,0], j=mesh.faces[:,1], k=mesh.faces[:,2],
                    color='lightblue', opacity=0.50
                )])
                fig.update_layout(scene=dict(aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0))
                st.plotly_chart(fig, use_container_width=True, height=600)
                # Single button to open download dialog
                if st.button("Download Model", key=f"download-model-{idx}"):
                    download_model_dialog(msg["stl_path"], msg["3mf_path"])
                # Add parameter adjustment UI tied to this history message
                if msg["role"] == "assistant":
                    params = parse_scad_parameters(msg["scad_code"])
                    if params:
                        with st.expander("Adjust parameters", expanded=False):
                            updated: dict[str, float] = {}
                            for name, default in params.items():
                                updated[name] = st.number_input(name, value=default, key=f"{idx}-{name}")
                            if st.button("Regenerate Preview", key=f"regen-{idx}"):
                                # Apply new parameter values
                                new_code = apply_scad_parameters(msg["scad_code"], updated)
                                # Overwrite SCAD file
                                with open(msg["scad_path"], "w") as f:
                                    f.write(new_code)
                                # Regenerate only STL preview for speed
                                try:
                                    stl_only_path = generate_3d_files(msg["scad_path"], formats=["stl"])["stl"]
                                except subprocess.CalledProcessError as e:
                                    st.error(f"OpenSCAD failed with exit code {e.returncode}")
                                    return
                                # Update history message in place
                                msg["scad_code"] = new_code
                                msg["content"] = new_code
                                msg["stl_path"] = stl_only_path
                                # Rerun to refresh UI
                                st.rerun()

    # Accept new user input and handle conversation state
    if user_input := st.chat_input("Describe the desired object"):
        # Add user message to history
        st.session_state.history.append({"role": "user", "content": user_input})
        # Generate SCAD and 3D files
        with st.spinner("Generating and rendering your model..."):
            scad_code = generate_scad(user_input)
            with tempfile.NamedTemporaryFile(suffix=".scad", delete=False) as scad_file:
                scad_file.write(scad_code.encode("utf-8"))
                scad_path = scad_file.name
            try:
                file_paths = generate_3d_files(scad_path)
            except subprocess.CalledProcessError as e:
                st.error(f"OpenSCAD failed with exit code {e.returncode}")
                st.subheader("OpenSCAD stdout")
                st.code(e.stdout or "<no stdout>")
                st.subheader("OpenSCAD stderr")
                st.code(e.stderr or "<no stderr>")
                return
        # Add assistant message to history and rerun to display via history loop
        st.session_state.history.append({
            "role": "assistant",
            "content": scad_code,
            "scad_code": scad_code,
            "scad_path": scad_path,
            "stl_path": file_paths["stl"],
            "3mf_path": file_paths["3mf"]
        })
        # Rerun to update chat history display
        st.rerun()

    # Fixed footer always visible
    st.markdown(
        """
        <style>
        footer {
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            text-align: center;
            padding: 10px 0;
            background-color: #f0f2f6;
            z-index: 1000;
        }
        </style>
        <footer>Made by <a href="https://flowful.ai" target="_blank">flowful.ai</a></footer>
        """, unsafe_allow_html=True
    )


if __name__ == "__main__":
    main() 