---
title: 3D Designer Agent
emoji: 🤖
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
---
# 3D Designer Agent

A Dockerized Streamlit app that converts text prompts into printable STL models via OpenAI + OpenSCAD.

## Local Usage with Docker

1. Build the Docker image:
   ```bash
   docker build -t 3d-designer-agent .
   ```
2. Run the container (passing your OpenAI key):
   ```bash
   docker run --rm -p 7860:7860 -e OPENAI_API_KEY=$OPENAI_API_KEY 3d-designer-agent
   ```
3. Visit http://localhost:7860 in your browser.

## Deploying to Hugging Face

Note: This project requires a Hugging Face Space of type "Docker".

First, ensure you have a remote named `hf` pointing to your Hugging Face Space repository. You can add it with:
`git remote add hf https://huggingface.co/spaces/YOUR-USERNAME/YOUR-SPACE-NAME`


Then execute the commands below to create a temporary branch, commit all files, force-pushes to the `hf` remote's `main` branch, and then cleans up: 

```bash
git checkout --orphan hf-main && \
git add . && \
git commit -m "New release" && \
git push --force hf hf-main:main && \
git checkout main && \
git branch -D hf-main
```

## Demo

![Demo Screenshot](https://media.githubusercontent.com/media/nchourrout/Chat-To-STL/main/demo.png)

For more example models and usage patterns, see our Medium post: [Vibe Modeling: Turning Prompts into Parametric 3D Prints](https://medium.com/@nchourrout/vibe-modeling-turning-prompts-into-parametric-3d-prints-a63405d36824).

Made by [Flowful.ai](https://flowful.ai)

## License
This project is licensed under the [MIT License](LICENSE).
