FROM python:3.10-slim-bookworm

# Copy uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy the project files
COPY . .

# install dependencies
RUN uv sync

# Set the default command to bash
CMD ["/bin/bash"]