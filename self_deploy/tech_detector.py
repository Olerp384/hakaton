"""Detect probable technologies from a project descriptor."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import replace
from typing import Iterable, Set

from .project_scanner import ProjectDescriptor


def _contains_any(contents: Iterable[str], keywords: Iterable[str]) -> bool:
    for content in contents:
        lower = content.lower()
        if any(keyword in lower for keyword in keywords):
            return True
    return False


def _collect_package_dependencies(package_json_blobs: list[str]) -> Set[str]:
    deps: Set[str] = set()
    for blob in package_json_blobs:
        try:
            data = json.loads(blob)
        except json.JSONDecodeError:
            continue

        for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            section_data = data.get(section) or {}
            if isinstance(section_data, dict):
                deps.update(name.lower() for name in section_data.keys())
    return deps


def detect_tech(descriptor: ProjectDescriptor) -> ProjectDescriptor:
    """Return a new descriptor with language, framework, build_tool and tests filled based on metadata."""
    result = replace(
        descriptor,
        tests=list(descriptor.tests),
        additional_metadata=deepcopy(descriptor.additional_metadata or {}),
    )
    metadata = result.additional_metadata or {}
    detected_files = metadata.get("detected_files", {})
    file_contents = metadata.get("file_contents", {})
    detected_dirs = metadata.get("detected_dirs", {})
    tests_seen: Set[str] = set(result.tests)

    def has_file(name: str) -> bool:
        return bool(detected_files.get(name))

    def get_contents(*names: str) -> list[str]:
        contents: list[str] = []
        for name in names:
            contents.extend(file_contents.get(name, []))
        return contents

    def add_test(name: str) -> None:
        if name not in tests_seen:
            result.tests.append(name)
            tests_seen.add(name)

    # Language and build tool detection
    if has_file("pom.xml"):
        result.language = "java"
        result.build_tool = "maven"
    elif has_file("build.gradle") or has_file("build.gradle.kts"):
        result.language = "kotlin" if has_file("build.gradle.kts") else "java"
        result.build_tool = "gradle"
    elif has_file("go.mod"):
        result.language = "go"
    elif has_file("package.json"):
        result.language = "ts" if has_file("tsconfig.json") else "js"
    elif has_file("pyproject.toml") or has_file("requirements.txt") or has_file("pipfile"):
        result.language = "python"

    # Package manager defaults
    if result.language in {"java", "kotlin"}:
        result.package_manager = result.build_tool
    elif result.language == "go":
        result.package_manager = "go"
    elif result.language in {"js", "ts"}:
        result.package_manager = "npm"
    elif result.language == "python":
        if has_file("pyproject.toml"):
            pyproject_text = "\n".join(get_contents("pyproject.toml"))
            if "poetry" in pyproject_text:
                result.package_manager = "poetry"
            elif "pipenv" in pyproject_text:
                result.package_manager = "pipenv"
            else:
                result.package_manager = "pip"
        elif has_file("pipfile"):
            result.package_manager = "pipenv"
        else:
            result.package_manager = "pip"

    # Framework detection
    if result.language in {"java", "kotlin"}:
        java_contents = get_contents("pom.xml", "build.gradle", "build.gradle.kts")
        if _contains_any(java_contents, ("spring-boot", "springframework", "spring.core", "spring.context")):
            result.framework = "spring"
        elif _contains_any(java_contents, ("micronaut",)):
            result.framework = "micronaut"
        elif _contains_any(java_contents, ("quarkus",)):
            result.framework = "quarkus"

        if _contains_any(java_contents, ("junit",)):
            add_test("junit")
        if _contains_any(java_contents, ("testng",)):
            add_test("testng")
        if _contains_any(java_contents, ("kotest",)):
            add_test("kotest")

    elif result.language == "go":
        go_contents = get_contents("go.mod")
        if _contains_any(go_contents, ("github.com/gin-gonic/gin", "github.com/gin-gonic")):
            result.framework = "gin"
        elif _contains_any(go_contents, ("github.com/labstack/echo", "github.com/labstack/echo/v4")):
            result.framework = "echo"
        elif _contains_any(go_contents, ("github.com/gofiber/fiber",)):
            result.framework = "fiber"
        elif _contains_any(go_contents, ("github.com/go-chi/chi",)):
            result.framework = "chi"

        if _contains_any(go_contents, ("github.com/stretchr/testify", "testify")):
            add_test("testify")
        if _contains_any(go_contents, ("github.com/onsi/ginkgo", "ginkgo")):
            add_test("ginkgo")

    elif result.language in {"js", "ts"}:
        package_contents = get_contents("package.json")
        deps = _collect_package_dependencies(package_contents)
        for blob in package_contents:
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue
            pkg_mgr = data.get("packageManager")
            if isinstance(pkg_mgr, str) and pkg_mgr:
                result.package_manager = pkg_mgr.split("@", 1)[0]
                break

        def package_text_has(*keys: str) -> bool:
            if any(any(key in dep for key in keys) for dep in deps):
                return True
            return _contains_any(package_contents, keys)

        if not result.framework:
            if package_text_has("nestjs"):
                result.framework = "nestjs"
            elif package_text_has("next"):
                result.framework = "next"
            elif package_text_has("express"):
                result.framework = "express"
            elif package_text_has("fastify"):
                result.framework = "fastify"
            elif package_text_has("koa"):
                result.framework = "koa"
            elif package_text_has("react"):
                result.framework = "react"
            elif package_text_has("vue"):
                result.framework = "vue"
            elif package_text_has("svelte"):
                result.framework = "svelte"

        if package_text_has("jest"):
            add_test("jest")
        if package_text_has("mocha"):
            add_test("mocha")
        if package_text_has("vitest"):
            add_test("vitest")
        if package_text_has("ava"):
            add_test("ava")
        if package_text_has("tap"):
            add_test("tap")
        if package_text_has("cypress"):
            add_test("cypress")

        engines_version = None
        for blob in package_contents:
            try:
                data = json.loads(blob)
            except json.JSONDecodeError:
                continue
            engines = data.get("engines") or {}
            node_version = engines.get("node")
            if node_version:
                engines_version = str(node_version)
                break
        if engines_version:
            result.version = engines_version

    elif result.language == "python":
        python_contents = get_contents("pyproject.toml", "requirements.txt", "pipfile")
        if _contains_any(python_contents, ("django",)):
            result.framework = "django"
        elif _contains_any(python_contents, ("fastapi",)):
            result.framework = "fastapi"
        elif _contains_any(python_contents, ("flask",)):
            result.framework = "flask"
        elif _contains_any(python_contents, ("starlette",)):
            result.framework = "starlette"

        if _contains_any(python_contents, ("pytest",)):
            add_test("pytest")
        if _contains_any(python_contents, ("unittest", "unittest2")):
            add_test("unittest")
        if _contains_any(python_contents, ("nose", "nose2")):
            add_test("nose")
        if _contains_any(python_contents, ("tox",)):
            add_test("tox")

        py_version_match = re.search(r"python[^\\n]*([0-9]+\\.[0-9]+)", " ".join(python_contents), re.IGNORECASE)
        if py_version_match:
            result.version = py_version_match.group(1)

    # Generic directory-based test heuristics
    if not result.tests:
        for dir_name in detected_dirs.keys():
            if "test" in dir_name:
                add_test("tests-present")
                break

    return result
        version_match = re.search(r"\\bgo\\s+([0-9.]+)", " ".join(go_contents))
        if version_match:
            result.version = version_match.group(1)
