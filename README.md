# homecloud-drive
# Home Network Storage System

A self-hosted cloud storage system designed to run on a home server and provide file storage and management to devices connected to the local network.

The project combines **systems engineering and full-stack software development**, with an emphasis on Linux server administration, networking, authentication, storage, and database management.

## Features

* User registration and authentication
* Session-token based authorisation
* Upload, download, view, and delete files
* Create and manage folders
* Per-user file permissions
* PostgreSQL storage for user and file metadata
* Trash system with 30-day file recovery
* Web-based client interface
* Designed for access over a local home network
* Headless Linux server accessible through SSH

## Architecture

The application is tested and deployed on a repurposed **Dell OptiPlex** running Ubuntu Server. Clients communicate with the FastAPI backend over the home network.

## Technologies Used

### Backend

* **Python**
* **FastAPI** — REST API and backend services
* **Psycopg** — PostgreSQL database interface
* **PostgreSQL** — user accounts and file metadata

### Frontend

* **Svelte** — web client and user interface

### Server / Systems

* **Ubuntu Server** — home server operating system
* **OpenSSH** — remote server administration
* **Linux filesystem** — file storage
* **Dell OptiPlex** — repurposed home server hardware

### Potential Future Technology

* **C / FUSE** — potential experimental custom filesystem implementation for further exploration of Linux filesystem and operating-system concepts.

## Project Structure

The project consists of three main components:

* **Client** — Svelte-based interface for users to interact with their files.
* **Backend** — FastAPI application responsible for authentication, file management, permissions, and database communication.
* **Home Server** — Ubuntu Server machine hosting the application, PostgreSQL database, and stored files.
