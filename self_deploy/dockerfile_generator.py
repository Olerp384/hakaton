"""Generate multi-stage Dockerfile content tailored to the detected tech stack."""

from __future__ import annotations

from textwrap import dedent

from .project_scanner import ProjectDescriptor


def _java_or_kotlin(descriptor: ProjectDescriptor) -> str:
    build_tool = (descriptor.build_tool or "").lower()
    if build_tool == "gradle":
        return dedent(
            """
            # syntax=docker/dockerfile:1
            FROM gradle:8-jdk17 AS build
            WORKDIR /app
            COPY . .
            RUN gradle build -x test

            FROM eclipse-temurin:17-jre AS runtime
            WORKDIR /app
            COPY --from=build /app/build/libs/*.jar app.jar
            EXPOSE 8080
            ENTRYPOINT ["java", "-jar", "app.jar"]
            """
        ).strip()
    return dedent(
        """
        # syntax=docker/dockerfile:1
        FROM maven:3.9-eclipse-temurin-17 AS build
        WORKDIR /app
        COPY . .
        RUN mvn -B -DskipTests package

        FROM eclipse-temurin:17-jre AS runtime
        WORKDIR /app
        COPY --from=build /app/target/*.jar app.jar
        EXPOSE 8080
        ENTRYPOINT ["java", "-jar", "app.jar"]
        """
    ).strip()


def _go() -> str:
    return dedent(
        """
        # syntax=docker/dockerfile:1
        FROM golang:1.21 AS build
        WORKDIR /app
        COPY . .
        RUN go mod download
        RUN go build -o app .

        FROM alpine:3.19 AS runtime
        RUN apk add --no-cache ca-certificates
        WORKDIR /app
        COPY --from=build /app/app /usr/local/bin/app
        EXPOSE 8080
        ENTRYPOINT ["/usr/local/bin/app"]
        """
    ).strip()


def _node_backend() -> str:
    return dedent(
        """
        # syntax=docker/dockerfile:1
        FROM node:20 AS build
        WORKDIR /app
        COPY package*.json ./
        RUN npm ci
        COPY . .
        RUN npm run build

        FROM node:20-alpine AS runtime
        WORKDIR /app
        ENV NODE_ENV=production
        COPY --from=build /app/package*.json ./
        RUN npm ci --omit=dev
        COPY --from=build /app/dist ./dist
        EXPOSE 3000
        CMD ["node", "dist/index.js"]
        """
    ).strip()


def _python() -> str:
    return dedent(
        """
        # syntax=docker/dockerfile:1
        FROM python:3.11-slim AS base
        WORKDIR /app
        ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

        FROM python:3.11 AS build
        WORKDIR /app
        COPY requirements.txt* .  # optional constraints files
        RUN python -m pip install --upgrade pip && \
            pip install --prefix=/install -r requirements.txt
        COPY . .

        FROM base AS runtime
        WORKDIR /app
        COPY --from=build /install /usr/local
        COPY . .
        EXPOSE 8000
        CMD ["python", "app.py"]
        """
    ).strip()


def generate_dockerfile(descriptor: ProjectDescriptor) -> str:
    """Return the contents of a multi-stage Dockerfile for the project."""
    language = (descriptor.language or "").lower()

    if language in {"java", "kotlin"}:
        return _java_or_kotlin(descriptor)
    if language == "go":
        return _go()
    if language in {"js", "ts"}:
        return _node_backend()
    if language == "python":
        return _python()

    return dedent(
        """
        # syntax=docker/dockerfile:1
        FROM alpine:3.19
        WORKDIR /app
        COPY . .
        CMD ["sh"]
        """
    ).strip()
