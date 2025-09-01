# Backend Structure Document

This document explains the backend setup for Checky in clear, everyday language. It covers how the system is built, where it runs, how data is handled, and all the pieces that make it reliable, secure, and easy to maintain.

## 1. Backend Architecture

- **Core Framework**: Checky uses Python 3.10+ and FastAPI to create a RESTful API. FastAPI automatically checks incoming data and generates interactive API docs.
- **Server**: Uvicorn runs the FastAPI app, handling many requests at once in an asynchronous way for fast responses.
- **Modular Design**:
  - **Rule Engine Modules**: Separate Python files define different checks. You can add new rules by dropping in new modules.
  - **RAG Component**: A small search index (built with Whoosh or similar) looks up context from a text file (`rag-content.txt`) to enrich explanations.
  - **Audio Playback**: A dedicated module invokes `playsound` or `pygame` to play alert tones without slowing down the API response.
- **Why It Works**:
  - **Scalability**: Asynchronous Uvicorn workers and a modular rule engine let you handle more checks by adding server instances.
  - **Maintainability**: Clear separation between API routes, business logic, RAG lookup, and audio playback makes the code easy to update.
  - **Performance**: FastAPI’s validation and Uvicorn’s async I/O keep response times under 200 ms for simple checks.

## 2. Database Management

- **No External Database (v1)**: Checky keeps data in memory or in simple files. This avoids database setup for the first release.
- **In-Memory Store**:
  - Active check results and metadata live in a Python dictionary while the app runs.
  - A periodic or on-shutdown task can dump results to a JSON file if persistent storage is needed.
- **RAG Data File**:
  - The `rag-content.txt` file contains lines of contextual text used by the RAG module.
  - A lightweight search index is built on startup for quick lookups.
- **Data Access**:
  - The API directly reads from the in-memory store and the RAG index, avoiding database queries.
  - Simple file I/O for loading and saving state when needed.

## 3. Database Schema (Non-SQL)

Because Checky doesn’t use a traditional database in v1, here’s how key data is organized:

- **Check Result Object**:
  • `id`: unique string identifier for the check (e.g., UUID)  
  • `status`: “pending”, “success”, or “failure”  
  • `input`: the original data or payload submitted  
  • `rules_applied`: list of rule names checked  
  • `explanation`: text summary of why the check passed or failed (enriched by RAG)  
  • `timestamp`: ISO 8601 string of when the check ran
- **RAG Index**:
  • Built from `rag-content.txt` on startup  
  • Allows quick searches by keyword or phrase to retrieve relevant context snippets
- **User Sessions & Tokens** (in memory or secure file):
  • `user_id`: internal user reference  
  • `api_token`: secret string for authenticating API calls  
  • `created_at`: timestamp for token creation  
  • `expires_at` (optional): timestamp for token expiration

## 4. API Design and Endpoints

Checky offers clear, RESTful routes protected by API tokens.

- **Authentication Endpoints**:
  • `POST /auth/signup`  
    – Registers a new user with email and password  
  • `POST /auth/login`  
    – Returns an API token for valid credentials  
  • `POST /auth/password-reset`  
    – Sends an email link to reset the password
- **Check Endpoints**:
  • `POST /v1/check`  
    – Submit data to be validated  
    – Headers: `Authorization: Bearer <token>`  
    – Body: JSON payload with the data to check  
    – Returns: `id`, `status`, and immediate result if fast
  • `GET /v1/status/{id}`  
    – Retrieve the result of a previously submitted check  
    – Headers: `Authorization: Bearer <token>`  
    – Returns: full `Check Result Object`
- **Documentation & Health**:
  • `GET /docs` and `/redoc`  
    – Auto-generated OpenAPI docs from FastAPI  
  • `GET /health`  
    – Basic health check (returns “OK”)

## 5. Hosting Solutions

- **Containerization**: Docker images include the FastAPI app, dependencies, and rule engine modules. Same image runs everywhere.
- **Cloud Provider**: AWS Elastic Beanstalk (or EC2)
  - Automatically manages load balancers and scaling.
  - Handles rolling deployments, so updates have minimal downtime.
- **Documentation Hosting**: Read the Docs serves Sphinx-generated docs at no cost.
- **Why This Setup**:
  - **Reliability**: AWS monitors instance health and replaces unhealthy nodes.
  - **Scalability**: Auto-scaling triggers more instances when traffic spikes.
  - **Cost-Effectiveness**: Pay-as-you-go on AWS, free docs hosting.

## 6. Infrastructure Components

- **Load Balancer**:
  - Distributes incoming HTTP requests across multiple Docker containers on AWS.
- **Caching**:
  - In-memory cache inside each container for RAG lookups.
  - Future option: add Redis for cross-instance caching.
- **Content Delivery Network (CDN)**:
  - Serve static assets (audio files, docs, frontend bundles) via AWS CloudFront or equivalent for low latency.
- **Container Registry**:
  - Docker images stored in AWS ECR or Docker Hub for easy deployments.
- **CI/CD Pipeline**:
  - GitHub Actions builds code, runs tests, builds Docker image, and deploys to AWS.

## 7. Security Measures

- **Authentication & Authorization**:
  - API token required on every `/v1/*` call via `Authorization` header.
  - Tokens stored securely and rotated by users in Account Settings.
- **Encryption**:
  - HTTPS/TLS for all traffic to protect data in transit.
- **Input Validation**:
  - FastAPI pydantic models automatically validate request bodies.
- **Rate Limiting**:
  - Middleware caps requests per minute per token to prevent abuse.
- **Secret Management**:
  - Environment variables store sensitive settings (DB credentials, API keys).
  - AWS Secrets Manager or Parameter Store can be plugged in later.
- **Secure Defaults**:
  - Audio playback calls run in a safe subprocess with limited permissions.

## 8. Monitoring and Maintenance

- **Logging**:
  - Uvicorn logs request times and status codes to stdout.
  - Containers send logs to AWS CloudWatch for centralized viewing.
- **Error Tracking**:
  - Sentry integration (optional) captures exceptions and performance bottlenecks.
- **Metrics**:
  - Built-in FastAPI metrics or Prometheus exporter track request rates and latencies.
- **Automated Testing**:
  - Pytest suite covers unit and integration tests.
  - GitHub Actions runs tests on every pull request.
- **Documentation Checks**:
  - CI job builds Sphinx docs and checks for broken links.
- **Maintenance Strategy**:
  - Regular dependency updates via a scheduled GitHub Action.
  - Rule engine modules and RAG file reviewed and updated quarterly.

## 9. Conclusion and Overall Backend Summary

Checky’s backend is a clean, modular FastAPI service powered by Python and Uvicorn. It stores check results in memory, enriches explanations with a simple RAG index, and plays alert sounds without delaying API responses. Hosted on AWS in Docker containers, it auto-scales behind a load balancer and uses Read the Docs for documentation. Security measures like API tokens, HTTPS, input validation, and rate limiting keep things safe. Monitoring via logs, Sentry (optional), and CI tests ensure the service stays healthy and reliable. Altogether, this setup delivers a fast, maintainable, and scalable validation engine that meets Checky’s goals and provides a seamless experience for developers.