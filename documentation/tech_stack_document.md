# Checky Tech Stack Document

This document explains the technologies behind Checky in simple terms. Each section shows the tools we’ve chosen and why they help deliver a smooth, reliable experience.

## 1. Frontend Technologies

Checky’s user interface is what you see in your browser—pages like the Dashboard, API Explorer, Examples, and Account Settings. Here’s what makes it work:

- **React**
  - A popular JavaScript library for building interactive web pages.
  - Lets us break the interface into reusable pieces (components) so it’s easy to maintain and update.
- **React Router**
  - Handles switching between pages (e.g., Dashboard, API Explorer) without reloading the browser.
- **Axios**
  - A simple library to send and receive data from the backend API.
  - Makes it easy to submit checks and display results instantly.
- **Tailwind CSS**
  - A set of styling utilities that speeds up design and keeps our layouts consistent.
  - Helps ensure the site looks good on desktops, tablets, and phones.
- **Context API (React)**
  - A built-in React feature to share data (like your API token or theme settings) across pages without extra setup.

These choices give Checky a fast, responsive, and easy-to-use interface while keeping our code organized.

## 2. Backend Technologies

The backend is the engine that powers Checky’s features—processing validation requests, generating explanations, and playing sounds. Here’s what we use:

- **Python 3.10+**
  - A versatile, widely adopted programming language.
- **FastAPI**
  - A modern web framework for building speedy, secure REST APIs in Python.
  - Automatically validates input data (so you get clear error messages if you send the wrong format).
- **Uvicorn**
  - A server that runs FastAPI applications, optimized for performance and scalability.
- **Rule Engine (Custom Python Modules)**
  - Our core logic that defines what to check and how to decide pass/fail.
  - Easy to extend by adding new rule files or plugins.
- **Retrieval-Augmented Generation (RAG)**
  - Uses a lightweight search library (like Whoosh) over a local text file (`rag-content.txt`).
  - Enriches failure explanations with context and remediation tips.
- **Audio Playback**
  - Python’s `playsound` (or `pygame`) module plays `.wav` or `.mp3` alert tones on success or failure.
- **Testing with Pytest**
  - A straightforward framework to write and run tests, ensuring our checks and endpoints behave correctly.
- **Documentation with Sphinx**
  - Converts text files into a browsable website hosted on Read the Docs.
  - Keeps API references and usage guides in sync with the code.

Together, these components handle incoming requests, apply validation rules, look up context for explanations, and return structured results to the frontend.

## 3. Infrastructure and Deployment

To keep Checky available, up-to-date, and easy to manage, we rely on:

- **Version Control: Git & GitHub**
  - Tracks every change in our code and docs.
  - Supports collaboration, pull requests, and code reviews.
- **Continuous Integration/Continuous Deployment (CI/CD): GitHub Actions**
  - Automatically runs linters (Black, Flake8), tests, and documentation builds on every code change.
  - When code passes all checks, it deploys updated services.
- **Docker**
  - Packages the backend (and optional frontend) into containers so it runs the same way everywhere.
- **Hosting Platform: AWS Elastic Beanstalk (or EC2)**
  - Automatically scales to handle more traffic.
  - Manages underlying servers, so we focus on writing code.
- **Read the Docs**
  - Hosts our Sphinx-generated documentation at no extra charge.

This setup ensures reliability (99.9% uptime), easy rollbacks, and fast updates without manual intervention.

## 4. Third-Party Integrations

Checky connects to a few external services to extend functionality:

- **OpenAI API (Optional)**
  - For advanced, GPT-powered explanations in the RAG component.
  - Enhances context and provides more natural language guidance.
- **Read the Docs**
  - Publishes and hosts our user manuals and API references.
- **Sentry (Optional)**
  - Monitors errors and performance in real time.
  - Alerts the team if something goes wrong in production.
- **Google Analytics (Optional)**
  - Tracks user interactions on the frontend.
  - Helps us improve usability based on real usage patterns.

These integrations help us offer richer explanations, maintain high-quality docs, and spot issues before they impact users.

## 5. Security and Performance Considerations

Keeping data safe and the app fast are top priorities.

Security Measures:
- **API Token Authentication**
  - Every request to `/v1/check` or `/v1/status` requires a valid token in the header.
- **HTTPS/TLS Encryption**
  - All data in transit is encrypted to prevent eavesdropping.
- **Input Validation**
  - FastAPI’s built-in checks guard against malformed or malicious data.
- **Rate Limiting (Middleware)**
  - Prevents abuse by capping requests per minute per token.

Performance Optimizations:
- **Asynchronous Server (Uvicorn)**
  - Handles many requests concurrently for low response times (< 200ms for simple checks).
- **In-Memory Caching**
  - Stores frequently used RAG search results for faster lookups.
- **Audio Playback Offload**
  - Plays sound files in a separate thread so the API response isn’t delayed.

Together, these strategies keep Checky secure, responsive, and reliable under load.

## 6. Conclusion and Overall Tech Stack Summary

Checky’s technology choices balance simplicity, performance, and a great user experience:

- Frontend built with React, React Router, Axios, and Tailwind CSS for a sleek, responsive UI.
- Backend powered by Python 3.10+, FastAPI, and Uvicorn for fast, well-structured APIs.
- A modular rule engine and RAG component to deliver clear, context-rich validation reports.
- Audio playback with `playsound`/`pygame` for real-time alerts.
- CI/CD via GitHub Actions, containerized deployment with Docker, and hosting on AWS for scalability.
- Sphinx and Read the Docs for high-quality, up-to-date documentation.
- Optional integrations like OpenAI, Sentry, and Google Analytics to enhance functionality and support.

Together, these technologies ensure Checky meets its goals: seamless API integration, accurate and context-aware explanations, and reliable audio feedback in any environment.