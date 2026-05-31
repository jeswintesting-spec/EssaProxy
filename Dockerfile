FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install .
# EssaProxy uses Redis for distributed state
CMD ["essaproxy", "--config", "docker_config.json"]
