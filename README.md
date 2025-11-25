# self-deploy

self-deploy анализирует Git-репозиторий, определяет стек (язык, фреймворк, инструменты сборки и тесты) и автоматически генерирует GitLab CI пайплайн, многостадийный Dockerfile, а также краткие отчеты — всё на основе локального анализа без внешних запросов.

## Установка

```bash
pip install -e .
```

Требования: Python 3.10+, установленный Git CLI и Docker (для локального стенда).

## Использование

Сгенерировать артефакты для репозитория:

```bash
self-deploy generate --repo https://github.com/org/java-app.git --output ./out
```

Пример с указанием ветки и кастомной директории вывода:

```bash
self-deploy generate --repo https://github.com/org/python-service.git --branch develop --output ./generated
```

Что будет создано в выходной директории:
- `.gitlab-ci.yml` — пайплайн GitLab CI со стадиями prepare, lint, test, sonar, build/package, docker build/push и шаблонами деплоя.
- `Dockerfile` — многостадийный образ под обнаруженный стек (пропускается, если уже есть Dockerfile).
- `sonar-project.properties` — базовая конфигурация для SonarQube.
- `report.json` — машиночитаемый отчет анализа.
- `report.md` — читаемый человекоориентированный отчет.

## Локальный стенд (GitLab, Runner, SonarQube, Nexus)

Запустить стенд:

```bash
docker-compose up -d
```

Опционально: скопируйте `compose/.env.example` в `compose/.env` и поправьте токены/пароли (compose уже подключает файл).

### Быстрая первичная настройка
- **GitLab**: откройте http://localhost:8080, задайте пароль root (или используйте `GITLAB_ROOT_PASSWORD` в `.env`), создайте проект и получите токен регистрации раннера.
- **GitLab Runner**: задайте `GITLAB_RUNNER_TOKEN` (через `.env`) до старта compose или выполните `gitlab-runner register` в контейнере, выбрав Docker executor. Упрощённый вариант — скрипт `scripts/register_runner.sh`:
  ```bash
  GITLAB_RUNNER_TOKEN=XXXX scripts/register_runner.sh
  ```
- **SonarQube**: откройте http://localhost:9000, задайте пароль admin, создайте проект и токен; пропишите `SONAR_HOST_URL` и `SONAR_TOKEN` в переменных CI.
- **Nexus**: откройте http://localhost:8081, завершите разблокировку admin, создайте нужные репозитории (Maven/npm/PyPI/Docker hosted/proxy). Docker-hosted можно привязать к порту 8082 (уже проброшен).

### Как проверить сгенерированный пайплайн
1. Выполните `self-deploy generate ...`.
2. Залейте `.gitlab-ci.yml` и `Dockerfile` в GitLab из docker-compose.
3. Добавьте переменные CI/CD для реестра и SonarQube (`SONAR_HOST_URL`, `SONAR_TOKEN`, `CI_REGISTRY_USER`, `CI_REGISTRY_PASSWORD` при необходимости).
4. Запустите пайплайн и проверьте стадии (lint/test/sonar/build/package/docker/deploy) в GitLab и SonarQube.

## Кастомизация шаблонов
- Шаблоны лежат в `templates/` (можно переопределить через переменную `SELF_DEPLOY_TEMPLATES_DIR` или параметр `templates_dir` в конфиге).
- CI-шаблоны заточены под GitLab и включают кеширование зависимостей, SonarQube, сборку/публикацию Docker-образа и заготовки деплой-стадий.
- Docker-шаблоны — многостадийные для Java/Kotlin, Go, Node.js/TypeScript (backend/frontend) и Python.

## Если SonarQube не стартует (Elasticsearch bootstrap checks)
Elasticsearch внутри SonarQube требует `vm.max_map_count >= 262144`. На хосте (Linux/WSL2) выполните:
```bash
sudo sysctl -w vm.max_map_count=262144
echo "vm.max_map_count=262144" | sudo tee /etc/sysctl.d/99-sonarqube.conf
sudo sysctl --system
```
Затем перезапустите стенд: `docker-compose down && docker-compose up -d`.
