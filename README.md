# 3D Designer Agent

A local Streamlit app that converts text prompts into printable STL models via OpenAI + OpenSCAD.

## Prerequisites

- OpenSCAD CLI installed and available in your PATH (e.g. `brew install openscad` on macOS).

## Quickstart (Local)

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   streamlit run streamlit_app.py
   ```
3. Enter your OpenAI API key in the sidebar.
4. Describe the desired object and download the STL.

## Demo

![Demo Screenshot](demo.png)

Made by [Flowful.ai](https://flowful.ai) 