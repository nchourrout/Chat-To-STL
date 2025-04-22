import streamlit as st
from openai import OpenAI
import subprocess
import tempfile
import os
from dotenv import load_dotenv
import trimesh
import plotly.graph_objects as go

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
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    response = client.chat.completions.create(
        model="o4-mini",
        messages=messages,
        max_completion_tokens=4500,
    )
    code = response.choices[0].message.content.strip()
    return code


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
                with open(msg["stl_path"], "rb") as f:
                    st.download_button(
                        label="Download STL File", data=f, file_name="model.stl", mime="application/sla",
                        key=f"download-{idx}"
                    )

    # Accept new user input and display messages
    if user_input := st.chat_input("Describe the desired object"):
        # Echo user message
        with st.chat_message("user"):
            st.write(user_input)

        # Generate SCAD code and STL file
        with st.chat_message("assistant"):
            with st.spinner("Generating and rendering your model..."):
                scad_code = generate_scad(user_input)
                with tempfile.NamedTemporaryFile(suffix=".scad", delete=False) as scad_file:
                    scad_file.write(scad_code.encode("utf-8"))
                    scad_path = scad_file.name
                stl_path = scad_path.replace(".scad", ".stl")
            # Run OpenSCAD and catch errors
            try:
                subprocess.run(["openscad", "-o", stl_path, scad_path], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                st.error(f"OpenSCAD failed with exit code {e.returncode}")
                st.subheader("OpenSCAD stdout")
                st.code(e.stdout or "<no stdout>")
                st.subheader("OpenSCAD stderr")
                st.code(e.stderr or "<no stderr>")
                return
            # Display results if render succeeded
            with st.expander("Generated OpenSCAD Code", expanded=False):
                st.code(scad_code, language="c")
            mesh = trimesh.load(stl_path)
            fig = go.Figure(data=[go.Mesh3d(
                x=mesh.vertices[:,0], y=mesh.vertices[:,1], z=mesh.vertices[:,2],
                i=mesh.faces[:,0], j=mesh.faces[:,1], k=mesh.faces[:,2],
                color='lightblue', opacity=0.50
            )])
            fig.update_layout(scene=dict(aspectmode='data'), margin=dict(l=0, r=0, b=0, t=0))
            st.plotly_chart(fig, use_container_width=True, height=600)
            with open(stl_path, "rb") as f:
                st.download_button(
                    label="Download STL File", data=f, file_name="model.stl", mime="application/sla", key=stl_path
                )
        # Store messages in history
        st.session_state.history.append({"role": "user", "content": user_input})
        st.session_state.history.append({"role": "assistant", "scad_code": scad_code, "stl_path": stl_path})

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