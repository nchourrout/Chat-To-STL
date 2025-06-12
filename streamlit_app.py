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

SYSTEM_PROMPT = (
    "You are an expert in OpenSCAD. Given a user prompt describing a 3D printable model, "
    "generate a parametric OpenSCAD script that fulfills the description. "
    "Only return the raw .scad code without any explanations or markdown formatting."
)


# Cache SCAD generation to avoid repeated API calls for same prompt+history
@st.cache_data
def generate_scad(prompt: str, history: tuple[tuple[str, str]], api_key: str) -> str:
    """
    Uses OpenAI API to generate OpenSCAD code from a user prompt.
    """
    client = OpenAI(api_key=api_key)
    # Build conversation messages including history
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for role, content in history:
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})
    response = client.chat.completions.create(
        model="o4-mini",
        messages=messages,
        max_completion_tokens=4500,
    )
    code = response.choices[0].message.content.strip()
    return code


@st.cache_data
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

    # Display large app logo and updated title
    st.logo("https://media.githubusercontent.com/media/nchourrout/Chat-To-STL/main/logo.png", size="large")
    st.title(title)
    st.write("Enter a description for your 3D model, and this app will generate an STL file using OpenSCAD and OpenAI.")

    if not api_key:
        st.warning("👈 Please enter an OpenAI API key in the sidebar to generate a model.")
        st.image("demo.gif")

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
                    with st.expander("Adjust parameters", expanded=False):
                        if not params:
                            st.write("No numeric parameters detected in the SCAD code.")
                        else:
                            # Use a form so inputs don't trigger reruns until submitted
                            with st.form(key=f"param-form-{idx}"):
                                updated: dict[str, float] = {}
                                for name, default in params.items():
                                    updated[name] = st.number_input(name, value=default, key=f"{idx}-{name}")
                                regenerate = st.form_submit_button("Regenerate Preview")
                            if regenerate:
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
        if not api_key:
            st.error("👈 Please enter an OpenAI API key in the sidebar to generate a model.")
            return

        # Add user message to history
        st.session_state.history.append({"role": "user", "content": user_input})
        # Generate SCAD and 3D files
        with st.spinner("Generating and rendering your model..."):
            history_for_api = tuple(
                (m["role"], m["content"])
                for m in st.session_state.history
                if "content" in m and "role" in m
            )
            scad_code = generate_scad(user_input, history_for_api, api_key)
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
            background-color: var(--secondary-background-color);
            color: var(--text-color);
            z-index: 1000;
        }
        footer a {
            color: var(--primary-color);
        }
        </style>
        <footer>Made by <a href="https://flowful.ai" target="_blank">flowful.ai</a> | <a href="https://medium.com/@nchourrout/vibe-modeling-turning-prompts-into-parametric-3d-prints-a63405d36824" target="_blank">Examples</a></footer>
        """, unsafe_allow_html=True
    )


if __name__ == "__main__":
    main() 