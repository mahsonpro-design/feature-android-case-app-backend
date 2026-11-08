# Copilot instructions

## Project structure

This repository combines a Python API backend with an Android client project:

- `api.py` defines the FastAPI application, authentication, and API routes. It uses SQLite for application data and environment variables for runtime configuration.
- `admin_features.py` contains administrator management, reporting, and search routes mounted by the API.
- `android/` is the Android Gradle project. It uses Kotlin, Jetpack Compose, AndroidX, Retrofit, and coroutines; Gradle configuration is in Kotlin DSL (`*.gradle.kts`).
- `Dockerfile` describes the backend container image and starts the API with Uvicorn.
- `README.md` documents the product and intended deployment setup; `.env.example` lists backend configuration names.

The API also imports `case_records.py`, which the Dockerfile obtains from the configured source repository during image construction. When working locally, ensure that dependency is available as described by the deployment setup.

## Coding conventions

- Python: use type annotations where practical, keep API input validation in Pydantic models, and use FastAPI dependency injection for authentication/authorization. Preserve the existing SQLite transaction/rollback behavior and parameterize SQL values rather than interpolating them into queries.
- Security is important: enforce authorization on the server for protected/admin routes, hash passwords with Argon2, and never put backend secrets or tokens in the Android app. Do not log passwords, tokens, or other credentials.
- Keep user-facing API validation/errors consistent with the existing Arabic messages and API response patterns.
- Android: use Kotlin with the project’s official Kotlin code style and existing Jetpack Compose/AndroidX patterns. Keep API base URL configuration external to source code (`API_BASE_URL` Gradle property/build configuration); do not hard-code deployment credentials or secrets.
- Keep Gradle configuration in Kotlin DSL and follow the versions/dependency conventions already declared in `android/app/build.gradle.kts`.

## Tests

No test framework or test suite is currently configured in the repository. Do not assume pytest, JUnit, or an existing test command. For behavioral changes, add focused tests using the framework appropriate to the component (for example, pytest with FastAPI’s test client for API behavior or Android local/instrumented tests for the client), and document any new test setup. Run available checks and report clearly if required dependencies or project files are missing.

## Build and run

### Backend

The container is the repository’s documented backend build/run path. From the repository root, with Docker available and the configured source repository/ref reachable, build the image:

```sh
docker build -t albayda-court-api .
```

Run it with the required backend environment configured. For local development, set the values from `.env.example` (use strong, unique secrets and never commit real values), then start the ASGI app with Uvicorn, for example:

```sh
uvicorn api:app --host 0.0.0.0 --port 8000
```

The API defaults to `APP_DATABASE_PATH=./data/app.sqlite3` and port `8000`; deployment should use HTTPS and persistent storage. The Dockerfile starts Uvicorn and uses `PORT` when set.

### Android

The Android project is under `android/`. It requires a compatible JDK/Android SDK and Gradle. No Gradle wrapper is present in the repository, so use an installed compatible Gradle distribution. Set the API URL through the `API_BASE_URL` project property (the current fallback is intentionally a non-routable placeholder), then build a debug APK:

```sh
gradle -p android assembleDebug -PAPI_BASE_URL=https://<your-api-host>/
```

Install/run the resulting APK on an emulator or device using Android Studio or `adb`. Configure a real HTTPS API URL before expecting the client to connect.
